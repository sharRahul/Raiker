from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.execution.commands.store import CommandStore
from raiker.execution.container_tools import ContainerToolExecutor
from raiker.execution.profiles import ExecutionProfile, ProfileResolution
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import (
    ToolCallRejected,
    default_tool_specs,
    validate_tool_call,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


def _broker(tmp_path):  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    return ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
        principal_id="principal_owner",
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


def test_container_assignment_uses_bridge_without_host_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path)
    profile = ExecutionProfile(
        "container-review",
        "container",
        runtime="docker",
        image="raiker-tools:approved",
        tools=("list_directory",),
        repository_access="read_only",
        writable_output=True,
    )
    broker.executors["list_directory"] = lambda _args: pytest.fail(
        "container assignment fell back to the host handler"
    )
    monkeypatch.setattr(
        broker, "_execution_profile", lambda _name: ProfileResolution(profile)
    )
    monkeypatch.setattr(
        ContainerToolExecutor,
        "execute",
        lambda _self, _name, _arguments, _action_id: {
            "status": "success",
            "path": ".",
            "entries": ["README.md"],
        },
    )

    result, decision = broker.execute(
        ToolAction(new_id("act_"), "list_directory", {"path": "."}, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )

    assert decision.decision == "allow"
    assert result.status == "success"
    assert result.output == {"status": "success", "path": ".", "entries": ["README.md"]}


def test_unavailable_container_assignment_never_falls_back_to_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = _broker(tmp_path)
    broker.executors["grep"] = lambda _args: pytest.fail(
        "unavailable container assignment fell back to the host handler"
    )
    monkeypatch.setattr(
        broker,
        "_execution_profile",
        lambda _name: ProfileResolution(None, "container_runtime_unavailable:podman"),
    )

    result, decision = broker.execute(
        ToolAction(
            new_id("act_"),
            "grep",
            {"query": "needle", "path": "."},
            "medium",
            False,
        ),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )

    assert decision.decision == "allow"
    assert result.status == "failed"
    assert result.error == {"type": "container_runtime_unavailable:podman"}


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


@pytest.mark.parametrize(
    ("suffix", "text"),
    [("md", "# Report"), ("docx", "Report\nComplete"), ("xlsx", "Name,Status\nC1,Ready"), ("pdf", "Report\nComplete")],
)
def test_create_document_generates_and_attaches_without_approval(
    tmp_path: Path, suffix: str, text: str
) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    action = validate_tool_call(
        ToolCallProposal(
            call_id="call_document",
            tool_name="create_document",
            arguments={"path": f"artifacts/report.{suffix}", "text": text},
        )
    )
    result, decision = broker.execute(action, session_id=session_id, turn_id=turn_id)

    assert decision.decision == "allow"
    assert decision.requires_user_approval is False
    assert result.status == "success"
    assert (tmp_path / "artifacts" / f"report.{suffix}").is_file()
    refs = broker.store.list_session_attachment_refs(  # type: ignore[union-attr]
        session_id=session_id, owner_principal_id="principal_owner"
    )
    assert refs == [
        {
            "attachment_id": result.output["attachment_id"],  # type: ignore[index]
            "turn_id": turn_id,
            "created_at": refs[0]["created_at"],
            "source": "generated",
        }
    ]


def test_run_command_returns_feedback_only_for_exact_active_session_grant(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime, timedelta

    broker = _broker(tmp_path)
    session_id = new_id("sess_")
    broker.store.put_session_command_grant(  # type: ignore[union-attr]
        session_id=session_id,
        principal_id="principal_owner",
        # RAIKER-2023: the grant names a command the policy will also allow;
        # `python -c` is an interpreter escape and is refused before any grant
        # is consulted.
        commands=[["git", "--version"]],
        timeout_seconds=5,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    allowed = validate_tool_call(
        ToolCallProposal(
            call_id="call_command",
            tool_name="run_command",
            arguments={"command": "git --version"},
        )
    )
    result, decision = broker.execute(allowed, session_id=session_id, turn_id=new_id("turn_"))
    assert decision.decision == "allow"
    assert result.status == "success"
    assert result.output["returncode"] == 0  # type: ignore[index]
    assert result.output["run_id"].startswith("cmd_")  # type: ignore[index,union-attr]
    runs = CommandStore(broker.store).list_runs("principal_owner")  # type: ignore[arg-type]
    assert [row.run_id for row in runs] == [result.output["run_id"]]  # type: ignore[index,union-attr]

    denied, _ = broker.execute(
        allowed, session_id=new_id("sess_"), turn_id=new_id("turn_")
    )
    assert denied.status == "denied"
    assert denied.error == {"type": "command_grant_required", "fallback_tool": "shell"}


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


def test_shell_proposal_states_that_approving_executes_once(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, _decision = broker.execute(
        ToolAction(new_id("act_"), "shell", {"command": "ls"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert result.output["expected_effect"] == (  # type: ignore[index]
        "Approving executes this exact bounded shell command once."
    )


def test_create_task_proposal_says_creation_does_not_schedule_a_run(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "create_task", {"title": "Draft notes"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )

    assert decision.decision == "needs_approval"
    assert result.output["expected_effect"] == (  # type: ignore[index]
        "Creates one task in Tasks. It will wait until you run or schedule it."
    )


def test_a_write_into_the_governance_directory_fails_instead_of_being_proposed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    broker = _broker(tmp_path)
    result, _decision = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": ".raiker/hooks.json", "text": "{}"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    # BUG-67 — and it fails rather than being proposed. A snapshot that already
    # refused is not a decision the owner has anything to weigh: raising an
    # approval for it would ask them to approve something the runtime has
    # established it will not do, and tell them so only afterwards.
    assert result.status == "failed"
    assert result.error == {"type": "protected_workspace_path"}
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
