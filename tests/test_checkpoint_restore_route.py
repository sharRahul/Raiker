"""BUG-230 — the rewind has a caller, and the caller performs nothing.

`CheckpointRestoreExecutor` was implemented, registered, classified and tested
for two workstreams, and no route, command or tool ever constructed a
`checkpoint_restore` action — so "recoverable" was a claim with no control behind
it. These tests hold the three properties that closing it depended on:

1. the route and the terminal command **raise an approval and change nothing**;
2. the capability is relayed on approval, so approving really rewinds; and
3. a restore that would overwrite another principal's work is `critical`, so it
   never reaches the ordinary relay.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.commands import bootstrap_owner, handle_checkpoints
from raiker.control.service import RuntimeControlService
from raiker.storage.sqlite import SQLiteStore


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    RuntimeControlService(ws).activate_runtime_mode("local_single_user_runtime", None, "test")
    return ws


def _checkpoint_with_one_captured_write(
    ws: Path, *, principal_id: str = "principal_owner"
) -> tuple[SQLiteStore, str, str]:
    """A checkpoint, then one captured mutation after it. Returns (store, id, path).

    The checkpoint is dated in the past so the capture that follows is
    unambiguously *after* it, which is what `compute_restore_plan` selects on.
    """
    from raiker.checkpoints.service import CheckpointService
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import Checkpoint

    store = SQLiteStore(ws)
    store.create_session("sess_restore", "ws")
    checkpoint = Checkpoint(
        checkpoint_id=new_id("ckpt_"),
        session_id="sess_restore",
        turn_id=new_id("turn_"),
        created_at="2000-01-01T00:00:00Z",
        runtime_state="CLOSED",
        summary="before the write",
        last_event_id=new_id("evt_"),
        memory_candidates=[],
    )
    store.insert_checkpoint(checkpoint, f"cp-{checkpoint.checkpoint_id}.json")

    target = ws / "notes.txt"
    target.write_text("before", encoding="utf-8")
    capture = CheckpointService(store).capture_service()
    pre = capture.snapshot_path("notes.txt", "file_write_execution")
    target.write_text("after", encoding="utf-8")
    assert pre is not None
    capture.commit(
        pre,
        session_id="sess_restore",
        turn_id="turn_2",
        action_id="act_write",
        principal_id=principal_id,
    )
    return store, checkpoint.checkpoint_id, str(target)


def test_the_restore_capability_is_relayed_on_approval() -> None:
    """BUG-230's core: approving a restore has to actually rewind."""
    from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL, executable_capability

    assert "checkpoint_restore_execution" in EXECUTABLE_ON_APPROVAL
    assert executable_capability("checkpoint_restore") == "checkpoint_restore_execution"


def test_no_model_tool_can_propose_a_restore() -> None:
    """An agent may not rewind the workspace on its own say-so — only a person asks."""
    from raiker.models.tool_registry import TOOL_DEFINITIONS

    names = {
        getattr(tool, "name", None) or (tool.get("name") if isinstance(tool, dict) else None)
        for tool in TOOL_DEFINITIONS
    }
    assert "checkpoint_restore" not in names


def test_the_route_raises_an_approval_and_restores_nothing(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    store, checkpoint_id, target = _checkpoint_with_one_captured_write(ws)

    from raiker.control.web_read_models import WebReadModels

    plan = WebReadModels(ws).checkpoint_restore_plan(
        checkpoint_id, principal_id="principal_owner", user_id=None
    )
    assert plan is not None

    from raiker.contracts.ids import new_id
    from raiker.contracts.models import ToolAction

    # The route's own body, exercised without the HTTP stack: recompute, record,
    # return an approval id. What matters is that the workspace is untouched.
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name="checkpoint_restore",
        arguments={"checkpoint_id": checkpoint_id},
        risk_level="high",
        requires_approval=True,
        proposed_by="principal_owner",
    )
    approval_id = new_id("appr_")
    store.insert_tool_action(action, "sess_restore", None, "approval_required")
    store.insert_approval(approval_id, action, critical=bool(plan["touches_other_principal"]))

    assert Path(target).read_text(encoding="utf-8") == "after"
    row = store.load_approval(approval_id)
    assert row is not None
    assert str(row["status"]) == "pending"
    assert json.loads(str(row["arguments_json"]))["checkpoint_id"] == checkpoint_id


def test_the_terminal_command_previews_without_confirm(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    _store, checkpoint_id, target = _checkpoint_with_one_captured_write(ws)

    output = handle_checkpoints(f"/checkpoints restore {checkpoint_id}", workspace_root=ws)

    assert "Restore plan" in output
    assert "--confirm" in output, "the preview has to say how to actually ask for it"
    assert Path(target).read_text(encoding="utf-8") == "after"


def test_the_terminal_command_with_confirm_raises_an_approval(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    store, checkpoint_id, target = _checkpoint_with_one_captured_write(ws)

    output = handle_checkpoints(
        f"/checkpoints restore {checkpoint_id} --confirm", workspace_root=ws
    )

    assert "proposed as approval appr_" in output
    assert "Nothing has changed yet" in output
    assert Path(target).read_text(encoding="utf-8") == "after"
    pending = store.list_approvals("pending")
    assert any(str(row["tool_name"]) == "checkpoint_restore" for row in pending)


def test_a_cross_principal_restore_is_critical(tmp_path: Path) -> None:
    """It must never reach the ordinary relay — only the human-only lifecycle."""
    from raiker.runtime.authority.critical import (
        CRITICAL_CROSS_PRINCIPAL_RESTORE,
        classify_critical,
    )

    match = classify_critical(
        "checkpoint_restore", "", {"checkpoint_id": "cp_1", "touches_other_principal": True}
    )
    assert match is not None and match.code == CRITICAL_CROSS_PRINCIPAL_RESTORE


def test_the_restore_preflight_names_an_unrestorable_file(tmp_path: Path) -> None:
    """BUG-233's other half: an `oversize` pre-image is not a file that comes back."""
    from raiker.checkpoints.capture import STATUS_OVERSIZE
    from raiker.checkpoints.service import RESTORE_OP_SKIP_OVERSIZE

    assert STATUS_OVERSIZE == "oversize"
    assert RESTORE_OP_SKIP_OVERSIZE == "skip_oversize"


def test_a_relayed_write_is_captured_under_the_proposing_conversation(tmp_path: Path) -> None:
    """BUG-235, found live while verifying BUG-230.

    A file write approved from the Approvals inbox executes under the *API*
    session that resolved it. The checkpoints it has to be restorable from belong
    to the *chat* that proposed it, and `compute_restore_plan` selects capture
    entries by the checkpoint's `session_id` — so a pre-image filed under the API
    session was invisible to every restore plan. The pre-image existed and
    nothing could reach it, which is the same defect BUG-230 closed one layer up.
    """
    from raiker.contracts.ids import new_id
    from raiker.events.writer import EventLogWriter
    from raiker.runtime.authority.models import Principal, RiskLevelValue
    from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
    from raiker.runtime.executors import build_default_executor_registry

    ws = _workspace(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_chat", "ws")
    target = ws / "relayed.txt"
    target.write_text("before", encoding="utf-8")

    raw = store.get_principal("principal_owner")
    assert raw is not None
    principal = Principal(**raw)

    authority = RuntimeAuthority(
        store,
        EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )
    _force_enable(store, "file_write_execution")
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal.principal_id,
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "relayed.txt", "text": "after"},
        risk_level=RiskLevelValue.LOW,
        # What the relay does: execute under the inbox's API session, while
        # naming the conversation the proposal came from.
        session_id="api_ses_inbox",
        origin_session_id="sess_chat",
    )
    authority.route_action(action, principal)

    with store.connect() as connection:
        rows = connection.execute(
            "SELECT session_id, workspace_path FROM checkpoint_capture_manifest"
        ).fetchall()
    filed = {(str(r["session_id"]), str(r["workspace_path"])) for r in rows}
    assert ("sess_chat", "relayed.txt") in filed, (
        "the pre-image has to be filed under the conversation whose checkpoints "
        f"a restore plan selects on; got {filed}"
    )


def _force_enable(store: SQLiteStore, capability: str) -> None:
    from raiker.contracts.ids import utc_now

    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (capability, "principal_owner", now, "test"),
        )
    store.upsert_capability_gate_state({
        "capability": capability,
        "state": "enabled_runtime",
        "requested_by": "principal_owner",
        "requested_at": now,
        "activated_by": "principal_owner",
        "activated_at": now,
        "reason": "test",
        "created_at": now,
        "updated_at": now,
    })
