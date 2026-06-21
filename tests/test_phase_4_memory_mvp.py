from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.memory.store import get_memory, list_memory, memory_status, search_memory
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker
from raiker.tools.memory_tools import memory_forget, memory_search, memory_write


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = Path(d)
        (path / ".raiker").mkdir(parents=True, exist_ok=True)
        yield path


class AllowMemoryPolicyEngine(PolicyEngine):
    def review(self, action: ToolAction, user_id: str | None = None) -> PolicyDecision:
        if action.tool_name in {"memory_write", "memory_forget"}:
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="allow",
                reasons=["test_memory_allow"],
                requires_user_approval=False,
            )
        return super().review(action, user_id=user_id)


def _governed_broker(workspace: Path) -> ToolBroker:
    store = SQLiteStore(workspace)
    return ToolBroker(
        workspace_root=workspace,
        policy_engine=AllowMemoryPolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=EventLogWriter(store),
    )


def _memory_write_action(text: str, **overrides: object) -> ToolAction:
    arguments: dict[str, object] = {
        "text": text,
        "scope": "project",
        "tags": ["test"],
        "source": "tests",
        "source_event_id": "evt_test_memory",
        "source_session_id": "sess_test_memory",
        "source_turn_id": "turn_test_memory",
        "source_type": "local_user",
        "confidence": 0.9,
        "trust_score": 0.9,
        "retention": "until_forget",
        "approval_state": "approved_after_test_governance",
        "created_by": "tests",
    }
    arguments.update(overrides)
    return ToolAction(
        action_id=new_id("act_"),
        tool_name="memory_write",
        arguments=arguments,
        risk_level="high",
        requires_approval=True,
        proposed_by="tests",
    )


def _memory_forget_action(memory_id: str, **overrides: object) -> ToolAction:
    arguments: dict[str, object] = {
        "memory_id": memory_id,
        "source_event_id": "evt_test_forget",
        "source_session_id": "sess_test_memory",
        "source_turn_id": "turn_test_memory",
        "source_type": "local_user",
        "deleted_by": "tests",
    }
    arguments.update(overrides)
    return ToolAction(
        action_id=new_id("act_"),
        tool_name="memory_forget",
        arguments=arguments,
        risk_level="high",
        requires_approval=True,
        proposed_by="tests",
    )


def test_direct_memory_tool_write_and_forget_are_denied(workspace: Path) -> None:
    assert memory_write(workspace, "normal project note")["status"] == "denied"
    assert memory_forget(workspace, "mem_123")["status"] == "denied"


def test_governed_memory_write_and_read(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    result, decision = broker.execute(
        _memory_write_action("This is a governed memory about project Raiker."),
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert decision.decision == "allow"
    assert result.status == "success"
    memory_id = str(result.output["memory_id"])  # type: ignore[index]
    retrieved = get_memory(memory_id, workspace_root=workspace)
    assert retrieved is not None
    assert retrieved.text == "This is a governed memory about project Raiker."
    assert retrieved.retention == "until_forget"
    assert retrieved.approval_state == "approved_after_test_governance"
    assert retrieved.provenance["source_session_id"] == "sess_test_memory"


def test_governed_memory_write_requires_governance_metadata(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    action = _memory_write_action("missing metadata", approval_state="")
    result, _ = broker.execute(
        action,
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
    )
    assert result.status == "failed"
    assert result.error == {"type": "missing_memory_metadata:approval_state"}


def test_search_memory_keyword(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    for text in (
        "The llama.cpp provider is the native default.",
        "OpenAI compatible providers use httpx.",
        "SQLite is used for metadata storage.",
    ):
        result, _ = broker.execute(
            _memory_write_action(text),
            session_id="sess_test_memory",
            turn_id="turn_test_memory",
        )
        assert result.status == "success"

    results = search_memory("llama", workspace_root=workspace)
    assert any("llama.cpp" in r.text for r in results)
    results = search_memory("httpx", workspace_root=workspace)
    assert any("httpx" in r.text for r in results)


def test_forget_memory_tombstones_record(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    write_result, _ = broker.execute(
        _memory_write_action("Temporary note to be forgotten."),
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
    )
    memory_id = str(write_result.output["memory_id"])  # type: ignore[index]
    forget_result, decision = broker.execute(
        _memory_forget_action(memory_id),
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
    )
    assert decision.decision == "allow"
    assert forget_result.status == "success"
    assert get_memory(memory_id, workspace_root=workspace) is None
    assert all(entry.memory_id != memory_id for entry in list_memory(workspace_root=workspace))


def test_forget_nonexistent_memory(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    result, _ = broker.execute(
        _memory_forget_action("nonexistent_id"),
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
    )
    assert result.status == "failed"
    assert result.error == {
        "type": "not_found",
        "message": "Memory 'nonexistent_id' not found.",
    }


def test_list_memory(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    for text, scope in (
        ("Memory A", "project"),
        ("Memory B", "project"),
        ("Personal note", "personal"),
    ):
        result, _ = broker.execute(
            _memory_write_action(text, scope=scope),
            session_id="sess_test_memory",
            turn_id="turn_test_memory",
        )
        assert result.status == "success"
    all_entries = list_memory(workspace_root=workspace)
    assert len(all_entries) >= 3
    project_entries = list_memory(workspace_root=workspace, scope="project")
    assert len(project_entries) >= 2
    assert all(entry.scope == "project" for entry in project_entries)


def test_memory_status(workspace: Path) -> None:
    status = memory_status(workspace_root=workspace)
    assert status["approved_memory_count"] == 0
    broker = _governed_broker(workspace)
    result, _ = broker.execute(
        _memory_write_action("Test memory"),
        session_id="sess_test_memory",
        turn_id="turn_test_memory",
    )
    assert result.status == "success"
    status = memory_status(workspace_root=workspace)
    approved_memory_count = status["approved_memory_count"]
    assert isinstance(approved_memory_count, int)
    assert approved_memory_count >= 1
    tags = status["tags"]
    assert isinstance(tags, list)
    assert "test" in tags


def test_memory_write_policy_blocks_secrets(workspace: Path) -> None:
    assert memory_write(
        workspace,
        "The password=supersecret123! and api_key=abc123def456ghi789jkl",
    )["status"] == "denied"


def test_memory_write_policy_blocks_credentials(workspace: Path) -> None:
    assert memory_write(
        workspace,
        "Bearer token: abcdefghijklmnopqrstuvwxyz123456",
    )["status"] == "denied"


def test_memory_search_via_tool(workspace: Path) -> None:
    broker = _governed_broker(workspace)
    for text in (
        "Raiker uses SQLite for metadata persistence.",
        "The agent gateway routes prompts to the model provider.",
    ):
        tool_result, _ = broker.execute(
            _memory_write_action(text),
            session_id="sess_test_memory",
            turn_id="turn_test_memory",
        )
        assert tool_result.status == "success"
    search_result = memory_search(workspace, "SQLite")
    assert search_result["status"] == "success"
    assert search_result["count"] >= 1


def test_classify_memory_sensitivity() -> None:
    assert classify_memory_sensitivity("public documentation about the API") == MemorySensitivity.PUBLIC
    assert classify_memory_sensitivity("project raiker workspace repo") == MemorySensitivity.PROJECT
    assert classify_memory_sensitivity("my email is user@example.com") == MemorySensitivity.PERSONAL
    assert classify_memory_sensitivity("-----BEGIN RSA PRIVATE KEY-----") == MemorySensitivity.CREDENTIAL_LIKE
    assert classify_memory_sensitivity("abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmn") == MemorySensitivity.SECRET_LIKE
    assert classify_memory_sensitivity("") == MemorySensitivity.UNKNOWN


def test_memory_write_empty_denied(workspace: Path) -> None:
    assert memory_write(workspace, "")["status"] == "failed"
    assert memory_write(workspace, "   ")["status"] == "failed"
