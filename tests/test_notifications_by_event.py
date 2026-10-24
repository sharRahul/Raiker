"""Notifications by event (Quiet UI 06, QUI-F05).

Five switches — Approval needed, Input needed, Response ready, Task failed,
Background task finished — beside the security and extension ones. Muting is
never approving: a muted notice is still recorded and counted. *Approval
needed* and *Input needed* reach the desktop alert only, because inside Raiker
work waiting on the owner always shows (DEC-21a). A critical approval has no
switch at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from raiker.contracts.models import TaskRecord
from raiker.notify import delivery_policy as policy
from raiker.notify.approval_notifier import notify_approval_pending
from raiker.notify.task_notifier import TASK_FAILED_KIND, TASK_FINISHED_KIND, notify_task_finished
from raiker.storage.sqlite import SQLiteStore

NOON = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_the_five_event_switches_are_offered_in_order() -> None:
    labels = list(policy.MUTABLE_CATEGORIES.values())
    assert labels[:5] == [
        "Approval needed",
        "Input needed",
        "Response ready",
        "Task failed",
        "Background task finished",
    ]
    assert "decisions" not in policy.MUTABLE_CATEGORIES


def test_approval_and_input_switches_reach_the_desktop_only() -> None:
    for kind, category in (("approval_pending", "approvals"), ("question_pending", "input")):
        decision = policy.decide({policy.category_key(category): False}, kind=kind, now=NOON, fallback_zone="UTC")
        assert (decision.in_app, decision.desktop) == ("interrupt", "muted")


def test_a_critical_approval_cannot_be_muted_by_any_switch() -> None:
    settings = {policy.category_key(name): False for name in policy.MUTABLE_CATEGORIES}
    decision = policy.decide(settings, kind="critical_approval_pending", now=NOON, fallback_zone="UTC")
    assert (decision.in_app, decision.desktop) == ("interrupt", "interrupt")


def test_task_failed_and_task_finished_are_switched_apart() -> None:
    off = {policy.category_key("failed"): False}
    failed = policy.decide(off, kind="task_failed", now=NOON, fallback_zone="UTC")
    finished = policy.decide(off, kind="task_finished", now=NOON, fallback_zone="UTC")
    assert (failed.in_app, failed.desktop) == ("muted", "muted")
    assert (finished.in_app, finished.desktop) == ("interrupt", "interrupt")
    # A routine stopped by its own failures is a failure, not a finish.
    assert policy.category_of("task_paused") == "failed"


def _owner(store: SQLiteStore) -> str:
    from raiker.auth.accounts import AccountService

    return AccountService(store.paths.workspace_root).register("owner", "a-long-password-1")


def test_a_question_is_announced_as_input_needed(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    owner = _owner(store)
    notify_approval_pending(store, acting_principal_id=owner, approval_id="apr_q", tool_name="ask_owner_question")
    notify_approval_pending(store, acting_principal_id=owner, approval_id="apr_w", tool_name="write_file")
    rows = {row["subject_id"]: row for row in store.list_notifications(owner)}
    assert (rows["apr_q"]["kind"], rows["apr_q"]["title"]) == ("question_pending", "Input needed")
    assert (rows["apr_w"]["kind"], rows["apr_w"]["title"]) == ("approval_pending", "Approval needed")


def test_a_background_task_that_did_not_finish_has_its_own_kind(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    owner = _owner(store)

    def task(task_id: str) -> TaskRecord:
        return TaskRecord(
            task_id=task_id, session_id=f"sess_inbox_{owner}", title="Morning brief",
            objective="o", status="running", created_at="2026-10-24T07:00:00Z",
            updated_at="2026-10-24T07:00:00Z", scheduled_at="2026-10-24T07:00:00Z",
        )

    notify_task_finished(store, task("t_ok"), outcome="completed", was_background=True)
    notify_task_finished(store, task("t_bad"), outcome="failed", was_background=True)
    kinds = {row["subject_id"]: row["kind"] for row in store.list_notifications(owner)}
    assert kinds == {"t_ok": TASK_FINISHED_KIND, "t_bad": TASK_FAILED_KIND}
