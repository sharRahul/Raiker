"""One published lifecycle for a task (UX-TASK-05).

A task carries one of twelve runtime statuses, and each surface used to decide
for itself what an owner could do with which of them. The board offered *Run
now* on a parked task and *Stop* on everything active; Home said *Cancel* for
the same request on a scheduled row and *Stop* everywhere else; nothing said
what *Stop* means for a run that has not started, or whether a finished one can
be run again.

So the statuses are grouped into the phases the release review names, and the
phase is served with the task rather than re-derived per surface:

``not_started`` → ``scheduled`` / ``queued`` → ``running`` → ``waiting`` →
``completed`` / ``failed`` / ``stopped``

* **not_started** — created and parked until the owner runs it (BUG-64: a
  model-proposed task never schedules itself).
* **scheduled** — will be claimed at a future slot.
* **queued** — due now; the next host tick claims it.
* **running** — a turn is in flight, including the replay of a granted approval
  and the safe-boundary stop an owner has asked for.
* **waiting** — parked until something outside the run moves it: a decision, an
  answer, delegated work, or a pause.
* **completed / failed / stopped** — terminal. A terminal task is never re-run
  in place; running it again files new work with its own history, so nothing a
  finished run did is replayed by pressing a button.

The rules for retry and idempotency that follow from this are stated once, in
``docs/guide/tasks-and-projects.md``, and the web module
``web/src/lib/taskPhase.ts`` holds the actions each phase offers.
"""

from __future__ import annotations

from datetime import UTC, datetime

TASK_PHASES = (
    "not_started",
    "scheduled",
    "queued",
    "running",
    "waiting",
    "completed",
    "failed",
    "stopped",
)

#: Every status, and the phase it is in when its schedule does not decide it.
STATUS_PHASES: dict[str, str] = {
    "queued": "queued",
    "running": "running",
    "continuing": "running",
    "cancelling": "running",
    "waiting_for_approval": "waiting",
    "waiting_for_user_answer": "waiting",
    "waiting_for_children": "waiting",
    "paused": "waiting",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "stopped",
}


def task_phase(status: str, scheduled_at: str | None, now: datetime | None = None) -> str:
    """The phase a task is in. An unknown status reads as ``waiting``, never as done."""
    phase = STATUS_PHASES.get(status, "waiting")
    if phase != "queued":
        return phase
    if not scheduled_at:
        return "not_started"
    try:
        due = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        return "queued"
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return "scheduled" if due > (now or datetime.now(UTC)) else "queued"
