from __future__ import annotations

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import (
    ToolCallRejected,
    default_tool_specs,
    validate_tool_call,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


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


def test_write_file_proposal_states_that_approving_writes_the_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """BUG-06 — the proposal must not promise metadata-only once it is not true.

    The broker used to tell the model and the transcript "Approval resolution is
    metadata-only and does not execute the action" for every non-connector tool.
    With approval resolution wired to the execution relay that sentence became a
    lie for file mutations, so it is now derived from the same check the resolve
    endpoint makes.
    """
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "notes.md", "text": "hi"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "needs_approval"
    assert result.status == "approval_required"
    assert result.output["expected_effect"] == (  # type: ignore[index]
        "Approving writes this exact change to notes.md, once."
    )


def test_shell_proposal_still_states_metadata_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, _decision = broker.execute(
        ToolAction(new_id("act_"), "shell", {"command": "ls"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert "metadata-only" in result.output["expected_effect"]  # type: ignore[index]


def test_a_write_into_the_governance_directory_fails_instead_of_being_proposed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, _decision = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": ".raiker/hooks.json", "text": "{}"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    preview = result.output["proposal_preview"]  # type: ignore[index]
    assert preview == {"status": "failed", "error": {"type": "protected_workspace_path"}}
    assert not (tmp_path / ".raiker" / "hooks.json").exists()


def test_edit_file_requires_exact_old_text_and_previews_its_candidate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "note.txt").write_text("old\n", encoding="utf-8")
    broker = _broker(tmp_path)

    action = validate_tool_call(
        ToolCallProposal(
            call_id="call_edit",
            tool_name="edit_file",
            arguments={"path": "note.txt", "old_text": "old\n", "new_text": "new\n"},
        )
    )
    result, decision = broker.execute(
        action,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )

    assert decision.decision == "needs_approval"
    preview = result.output["proposal_preview"]  # type: ignore[index]
    assert preview["before_snapshot"] == "old\n"
    assert preview["proposed_text"] == "new\n"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "old\n"


def test_edit_file_validation_requires_old_text() -> None:
    with pytest.raises(ToolCallRejected, match="missing_argument:old_text"):
        validate_tool_call(
            ToolCallProposal(
                call_id="call_missing_old",
                tool_name="edit_file",
                arguments={"path": "note.txt", "new_text": "new\n"},
            )
        )
