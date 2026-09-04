"""GAP-CHAT C10 — background work that finished, and nobody was told.

A scheduled routine has no turn and no reader. It runs, it ends, and until now
the only trace was a card the owner had to think to go and look at. That is the
half of C10 the plan calls the cheapest and the one that makes routines useful:
work the owner is not watching has to be able to reach them.

Deliberately the smallest thing that closes it, and it reuses what already
exists rather than adding a channel:

* the owner-scoped ``notifications`` table the notification centre already
  renders, so the record lives where every other notice does;
* the browser notice BUG-255 built, which the centre mirrors on its own and only
  while Raiker is not the visible window — no email, no push, no new egress;
* the owner's ``RAIKER_OS_NOTIFY_CMD`` hook, off by default, exactly as an
  approval uses it.

**Only work the owner was not watching.** Every Chat turn is a task, and every
Chat turn completes; notifying for those would put a banner behind a message the
owner just read. A task qualifies when it carries a schedule — the routine case
C10 names — or when it was parked waiting for delegated children, which is work
that outlived the turn that asked for it. Nothing else notifies.

**Metadata, not content.** The body names the task's title and its outcome. A
run's summary is model output about the owner's material and does not belong in
a notice the operating system may render on a lock screen; the thread is one
click away and holds the whole of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from raiker.notify.approval_notifier import (
    dispatch_notification_hook,
    fire_os_notification,
    resolve_owner_principal_id,
)

if TYPE_CHECKING:
    from raiker.contracts.models import TaskRecord
    from raiker.storage.sqlite import SQLiteStore

#: Background work reached a terminal state. Its own kind so the centre can
#: group it and an owner can tell it from an approval, which needs a decision.
TASK_FINISHED_KIND = "task_finished"

#: The longest task title a notice will carry. A title is owner-authored or
#: model-authored text; bounding it keeps a notice readable and keeps a very
#: long one from becoming the whole banner.
_MAX_TITLE = 80


def _is_background(task: TaskRecord) -> bool:
    """True when nobody was watching this run.

    A scheduled or recurring task is C10's own case. A task that was parked as
    ``waiting_for_children`` outlived the turn that created it, which is the
    same condition arrived at differently — the owner has moved on, and the run
    settles later.
    """
    if task.scheduled_at or task.recurrence:
        return True
    return task.status == "waiting_for_children"


def _title(task: TaskRecord) -> str:
    stated = (task.title or "").strip() or "Background task"
    return stated if len(stated) <= _MAX_TITLE else stated[: _MAX_TITLE - 1] + "…"


def notify_task_finished(
    store: SQLiteStore,
    task: TaskRecord,
    *,
    outcome: str,
    was_background: bool,
) -> str | None:
    """Tell the owner that background work ended. Returns the notification id.

    ``was_background`` is read from the task *before* it reached its terminal
    state, because the state is what the caller has just changed: a parent
    settling out of ``waiting_for_children`` is ``completed`` by the time this
    runs, and asking then would answer about the wrong moment.

    Returns ``None`` — without raising — when the run was in the foreground,
    when no owner account exists yet, or when the store refuses the write. A
    notice is a courtesy on top of a record that already exists; failing to send
    one must never fail the task it is about.
    """
    if not (was_background or _is_background(task)):
        return None
    owner = resolve_owner_principal_id(
        store, task.session_id.removeprefix("sess_inbox_") or None
    )
    if not owner:
        return None
    finished = outcome == "completed"
    title = "Background task finished" if finished else "Background task did not finish"
    body = (
        f"“{_title(task)}” {'completed' if finished else 'ended as ' + outcome}."
        + (" Open it to read what it did." if task.thread_session_id else "")
    )
    try:
        notification_id = store.insert_notification(
            principal_id=owner,
            kind=TASK_FINISHED_KIND,
            title=title,
            body=body,
            subject_id=task.task_id,
        )
    except Exception:  # noqa: BLE001 - a notice must not fail the task
        return None
    fire_os_notification(title, body)
    dispatch_notification_hook(
        store,
        owner_principal_id=owner,
        kind=TASK_FINISHED_KIND,
        notification_id=notification_id,
        subject_id=task.task_id,
    )
    return notification_id
