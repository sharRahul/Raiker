from __future__ import annotations

from pathlib import Path

import pytest

from raiker.approvals import ApprovalInbox
from raiker.checkpoints.service import CheckpointService
from raiker.cli.commands import handle_approval_resolution, handle_approvals, handle_slash_command
from raiker.contracts.ids import new_id
from raiker.contracts.models import InterruptAction, SideQuestionTurn, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.memory.candidates import create_deferred_candidate, governed_memory_status
from raiker.models.health import check_local_provider
from raiker.phase_gates import assert_capability_disabled, list_disabled_capabilities
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.interrupts import InterruptController
from raiker.runtime.side_questions import SideQuestionRuntime
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tools.broker import ToolBroker
from raiker.tools.filesystem import diff_files, proposed_write_snapshot, stat_path
from raiker.tools.git import run_git


def test_side_question_contract_and_read_only_runtime(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    runtime = SideQuestionRuntime(EventLogWriter(store))
    turn = runtime.answer_read_only(
        session_id="sess", parent_turn_id="parent", question="q", answer="a"
    )
    assert isinstance(turn, SideQuestionTurn)
    assert turn.read_only is True
    assert {event["event_type"] for event in store.list_event_index(session_id="sess")} == {
        "side_question_received",
        "side_question_answered",
    }


def test_interrupt_controller_applies_at_safe_boundary(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess", str(tmp_path))
    manager = TaskManager(store, EventLogWriter(store))
    task = manager.create_task(session_id="sess", title="T", objective="O")
    status = InterruptController(store, EventLogWriter(store)).apply_at_safe_boundary(
        InterruptAction(new_id("act_"), task.task_id, "sess", "pause", "user requested")
    )
    assert status == "paused"
    assert store.load_task(task.task_id).status == "paused"  # type: ignore[union-attr]


def test_approval_inbox_and_terminal_resolution(tmp_path: Path) -> None:
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=SQLiteStore(tmp_path),
    )
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "a.txt", "text": "x"}, "high", True),
        session_id="sess",
        turn_id="turn",
    )
    approval_id = str(result.output["approval_id"])  # type: ignore[index]
    assert approval_id in handle_approvals(workspace_root=tmp_path)
    assert ApprovalInbox(broker.store).list_pending()[0]["approval_scope"] == "action"  # type: ignore[arg-type,union-attr]
    resolution_output = handle_approval_resolution(
        f"/approve {approval_id}", workspace_root=tmp_path
    )
    assert "approved" in resolution_output
    assert "Metadata only; no action was executed." in resolution_output
    assert handle_approvals(workspace_root=tmp_path) == "No pending approvals."


def test_terminal_slash_approval_commands(tmp_path: Path) -> None:
    assert handle_slash_command("/approvals", workspace_root=tmp_path) == "No pending approvals."
    assert "Usage:" in handle_slash_command("/approve", workspace_root=tmp_path)


def test_checkpoint_restore_is_executable_governed_plan_fork_still_plan_only(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path)
    service = CheckpointService(store)
    checkpoint, _ = service.write_turn_checkpoint(
        session_id="sess", turn_id="turn", runtime_state="CLOSED", summary="s", last_event_id="evt"
    )
    # B2: restore is now an executable, approval-required governed action (the
    # dry-run plan is metadata-only). Fork (B3) remains plan-only for now.
    restore_plan = service.plan_restore(checkpoint.checkpoint_id)
    assert restore_plan["can_execute"] is True
    assert restore_plan["requires_approval"] is True
    assert service.plan_fork(checkpoint.checkpoint_id)["can_execute"] is False
    assert service.plan_fork(checkpoint.checkpoint_id)["requires_approval"] is True


def test_stat_diff_and_write_proposal_do_not_mutate_without_approval(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("old\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("new\n", encoding="utf-8")
    assert stat_path(tmp_path, "a.txt")["size_bytes"] > 0
    assert diff_files(tmp_path, "a.txt", "b.txt")["diff"]
    proposal = proposed_write_snapshot(tmp_path, "a.txt", "changed")
    assert proposal["before_snapshot"] == "old\n"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "old\n"


def test_git_wrappers_allow_read_only_and_deny_destructive(tmp_path: Path) -> None:
    assert run_git(tmp_path, "status")["status"] in {"success", "failed"}
    assert run_git(tmp_path, "reset")["status"] == "denied"


def test_local_provider_health_check_is_detection_only() -> None:
    health = check_local_provider("llama.cpp")
    assert health.provider == "llama.cpp"
    assert health.enabled_for_runtime is False


def test_memory_candidate_listing_and_status(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    candidate = create_deferred_candidate("evt", "remember maybe")
    store.insert_memory_candidate(candidate)
    candidates = store.list_memory_candidates(decision="deferred")
    assert candidates[0]["candidate_id"] == candidate.candidate_id
    assert governed_memory_status(candidates)["durable_writes_enabled"] is False


def test_phase_3_and_phase_4_gates_are_listable_and_disabled() -> None:
    disabled = list_disabled_capabilities()
    assert "desktop_ui" in disabled["phase_3"]
    # subagents/multi_agent_teams are integrated now (enabled); external_channels
    # is a phase-4 alias with no real executor and stays disabled.
    assert "external_channels" in disabled["phase_4"]
    with pytest.raises(PermissionError):
        assert_capability_disabled("remote_execution")


def test_write_approval_includes_before_snapshot_and_resolution_event(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("before", encoding="utf-8")
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
    )
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "a.txt", "text": "after"}, "high", True),
        session_id="sess",
        turn_id="turn",
    )
    assert decision.reasons == [
        "write_file_requires_approval",
        "phase2_action_bound_approval_required",
    ]
    preview = result.output["proposal_preview"]  # type: ignore[index]
    assert preview["before_snapshot"] == "before"
    approval_id = str(result.output["approval_id"])  # type: ignore[index]
    ApprovalInbox(store, writer).resolve(approval_id, approve=False)
    assert store.list_event_index(session_id="sess", event_type="approval_denied")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "before"


def test_tampered_approval_payload_cannot_be_resolved(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
    )
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "a.txt", "text": "after"}, "high", True),
        session_id="sess",
        turn_id="turn",
    )
    approval_id = str(result.output["approval_id"])  # type: ignore[index]
    with store.connect() as connection:
        connection.execute(
            "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
            ('{"path":"a.txt","text":"tampered"}', result.action_id),
        )
    assert "approval_payload_tampered" in handle_approval_resolution(
        f"/approve {approval_id}", workspace_root=tmp_path
    )


def test_memory_and_doctor_terminal_commands(tmp_path: Path) -> None:
    assert "durable_writes_enabled: False" in handle_slash_command(
        "/memory", workspace_root=tmp_path
    )
    doctor = handle_slash_command("/doctor", workspace_root=tmp_path)
    assert "llama_cpp_runtime_enabled: False" in doctor
    assert "phase_4_disabled:" in doctor
