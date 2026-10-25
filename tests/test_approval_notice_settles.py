"""A decision settles the notice that asked for it.

Found in the Quiet UI features round (RT-QUI-51, RT-QUI-55): *Input needed*
stayed in the corner after the question was answered in Chat, and an
approval's notice stayed unread after its decision, because only opening the
notice or its page marked it read. Every path that decides an approval —
approve, deny, answer, expire — now marks the notice for that approval read,
and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.notify import approval_notifier
from raiker.notify.approval_notifier import notify_approval_pending
from raiker.storage.sqlite import SQLiteStore
from raiker.storage.stores.approvals import ApprovalStore
from tests.factories import tool_action

OWNER = "principal_owner"


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    return store


def _park(store: SQLiteStore, approval_id: str, *, tool_name: str = "write_file") -> str:
    action_id = f"act_{approval_id}"
    store.insert_tool_action(
        tool_action(
            tool_name,
            {"path": "notes.md"},
            action_id=action_id,
            risk_level="low",
            requires_approval=True,
            proposed_by=OWNER,
        ),
        session_id="sess_a",
        turn_id=None,
        status="approval_required",
    )
    store.insert_approval(approval_id, action_id, ttl_hours=24.0)
    notification_id = notify_approval_pending(
        store, acting_principal_id=OWNER, approval_id=approval_id, tool_name=tool_name
    )
    assert notification_id is not None
    return notification_id


def _read(store: SQLiteStore, notification_id: str) -> int:
    row = next(n for n in store.list_notifications(OWNER) if n["notification_id"] == notification_id)
    return int(row["read"])


def test_a_denial_marks_its_notice_read(store: SQLiteStore) -> None:
    notice = _park(store, "appr_deny")
    store.resolve_approval("appr_deny", status="denied", resolved_by=OWNER, resolved_at="2026-10-25T00:00:00Z")
    assert _read(store, notice) == 1


def test_an_approval_claimed_for_execution_marks_its_notice_read(store: SQLiteStore) -> None:
    notice = _park(store, "appr_run")
    assert store.claim_approval_for_execution("appr_run")
    assert _read(store, notice) == 1


def test_an_answered_question_marks_its_notice_read(store: SQLiteStore) -> None:
    from raiker.contracts.models import OWNER_QUESTION_TOOL

    notice = _park(store, "appr_question", tool_name=OWNER_QUESTION_TOOL)
    assert store.answer_owner_question(
        "appr_question", answers_json="[]", answered_by=OWNER, answered_at="2026-10-25T00:00:00Z"
    )
    assert _read(store, notice) == 1


def test_an_expired_approval_marks_its_notice_read(store: SQLiteStore) -> None:
    notice = _park(store, "appr_expire")
    assert store.expire_approval("appr_expire")
    assert _read(store, notice) == 1


def test_a_decision_leaves_every_other_notice_alone(store: SQLiteStore) -> None:
    decided = _park(store, "appr_one")
    waiting = _park(store, "appr_two")
    store.resolve_approval("appr_one", status="denied", resolved_by=OWNER, resolved_at="2026-10-25T00:00:00Z")
    assert _read(store, decided) == 1
    assert _read(store, waiting) == 0


def test_the_store_knows_every_kind_the_notifier_raises_for_a_decision() -> None:
    raised = {
        approval_notifier.APPROVAL_PENDING_KIND,
        approval_notifier.QUESTION_PENDING_KIND,
        approval_notifier.CRITICAL_APPROVAL_PENDING_KIND,
    }
    assert set(ApprovalStore._DECISION_NOTICE_KINDS) == raised


# ── The host sweep settles approvals whose time limit ran out ────────────────


def test_the_sweep_expires_only_approvals_past_their_time_limit(store: SQLiteStore) -> None:
    late = _park(store, "appr_late")
    _park(store, "appr_current")
    store._execute(
        "UPDATE approvals SET expires_at = ? WHERE approval_id = ?", ("2000-01-01T00:00:00Z", "appr_late")
    )
    expired = store.expire_due_approvals()
    assert [row["approval_id"] for row in expired] == ["appr_late"]
    late_row = store.load_approval("appr_late")
    current_row = store.load_approval("appr_current")
    assert late_row is not None and late_row["status"] == "expired"
    assert current_row is not None and current_row["status"] == "pending"
    # Its notice settles with it, and the proposing call's row stops waiting.
    assert _read(store, late) == 1
    action = store.load_tool_action("act_appr_late")
    assert action is not None and action["status"] == "failed"
    # A second sweep has nothing left to do.
    assert store.expire_due_approvals() == []


def test_the_host_pass_records_each_expiry_as_an_event(store: SQLiteStore, tmp_path: Path) -> None:
    from types import SimpleNamespace

    from raiker.api.instance_runtime import InstanceRuntime
    from raiker.events.query import EventViewer

    _park(store, "appr_gone")
    store._execute(
        "UPDATE approvals SET expires_at = ? WHERE approval_id = ?", ("2000-01-01T00:00:00Z", "appr_gone")
    )
    runtime = InstanceRuntime(SimpleNamespace(state=SimpleNamespace(workspace_root=store.paths.workspace_root)))  # type: ignore[arg-type]
    runtime._expire_approvals()
    viewer = EventViewer(store)
    events = viewer.list_events(event_type="approval_expired", limit=10)
    assert len(events) == 1
    record = viewer.read_event_payload(events[0]["event_id"])
    assert record is not None
    assert record["payload"]["approval_id"] == "appr_gone"
    assert record["payload"]["tool_name"] == "write_file"
