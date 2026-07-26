from __future__ import annotations

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker
from raiker.models.tool_call_validation import default_tool_specs, validate_tool_call
from raiker.models.contracts import ToolCallProposal


def _broker(tmp_path):  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    return ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
    )


def test_broker_routes_list_directory_and_logs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "list_directory", {"path": "."}, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert decision.decision == "allow"
    assert result.status == "success"
    assert "README.md" in result.output["entries"]  # type: ignore[index]


def test_broker_denied_action_does_not_execute(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "read_file", {"path": "../outside"}, "blocked", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "deny"
    assert result.status == "denied"


def test_broker_shell_returns_approval_required(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "shell", {"command": "echo hi"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "needs_approval"
    assert result.status == "approval_required"


def test_chat_task_tools_accept_no_model_supplied_session_id() -> None:  # type: ignore[no-untyped-def]
    names = {spec.name for spec in default_tool_specs()}
    assert {"create_task", "assign_session_project"} <= names
    action = validate_tool_call(
        ToolCallProposal(call_id="call_1", tool_name="assign_session_project", arguments={"project_id": "proj_1"})
    )
    assert action.arguments == {"project_id": "proj_1"}


def test_broker_memory_write_requires_approval_and_does_not_mutate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(
            new_id("act_"),
            "memory_write",
            {"text": "remember this", "scope": "project"},
            "high",
            True,
        ),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "needs_approval"
    assert result.status == "approval_required"
    assert "exact_arguments" in result.output  # type: ignore[operator]
    assert not list((tmp_path / ".raiker" / "memory").glob("*.md"))


def test_broker_memory_write_denies_secret_without_approval_record(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
    )
    result, decision = broker.execute(
        ToolAction(
            new_id("act_"),
            "memory_write",
            {"text": "password=supersecret123456789", "scope": "project"},
            "high",
            True,
        ),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "deny"
    assert result.status == "denied"
    assert store.list_approvals(status="pending") == []
