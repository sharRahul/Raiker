from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


class TaskScheduler:
    """Runs due dashboard tasks inside the same always-on Raiker host."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)

    async def run_due(self) -> int:
        tasks = self.store.claim_due_tasks(utc_now())
        for task in tasks:
            principal_id = task.session_id.removeprefix("sess_inbox_")
            if principal_id == task.session_id or self.store.get_principal(principal_id) is None:
                TaskManager(self.store, EventLogWriter(self.store)).fail_task(task.task_id, "Scheduled task has no valid owner.")
                continue
            prompt = task.objective or task.title
            response = await AgentGateway(self.workspace_root, principal_id=principal_id).submit_prompt_async(
                PromptEnvelope(
                    request_id=new_id("req_"), session_id=task.session_id, turn_id=new_id("turn_"),
                    client=ClientMetadata(type="dashboard", name="raiker-scheduler", version="1"),
                    user=UserMetadata(id=principal_id), prompt=PromptPayload(text=prompt),
                    options=PromptOptions(
                        model_profile=task.model_profile or "",
                        model=task.model or "",
                    ),
                )
            )
            manager = TaskManager(self.store, EventLogWriter(self.store))
            # A user may have stopped the task while its governed turn was
            # reaching a safe boundary; never overwrite that cancellation.
            current = self.store.load_task(task.task_id)
            if current is None or current.status == "cancelled":
                continue
            outcome, summary = run_outcome(response.status, response.message)
            interval = RECURRING_INTERVALS.get(task.recurrence or "")
            if interval is not None and task.scheduled_at:
                next_run = next_run_after(task.scheduled_at, interval)
                # A recurring task keeps its slot whatever one cycle did, so the
                # summary has to say which it was — otherwise a cycle that never
                # ran reads exactly like one that succeeded.
                manager.store.reschedule_task(
                    task.task_id,
                    next_run,
                    summary if outcome == "completed" else f"Last run did not complete: {summary}",
                )
            elif outcome == "completed":
                manager.complete_task(task.task_id, summary)
            elif outcome == "waiting_for_approval":
                manager.block_task_on_approval(task.task_id, summary)
            else:
                manager.fail_task(task.task_id, summary)
        return len(tasks)


# How a governed turn's terminal status lands on the task the scheduler ran, and
# what the owner is told when the turn leaves no message of its own (BUG-09).
# Treating every non-`completed` status as a failure was wrong twice over: a run
# parked on an approval had not failed at all, and a blank message produced a
# `Task failed` card and audit line that said nothing about why.
SUMMARY_MAX_CHARS = 500
RUN_OUTCOMES: dict[str, tuple[str, str]] = {
    "completed": ("completed", "The run finished without a summary."),
    "needs_approval": (
        "waiting_for_approval",
        "Waiting for your approval before this run can continue.",
    ),
    "denied": ("failed", "Policy denied an action this run needed."),
    "failed": ("failed", "The run failed without a stated reason."),
}


def run_outcome(status: str, message: str) -> tuple[str, str]:
    """Map one governed turn's result onto ``(task status, stated summary)``.

    An unrecognised status fails closed *and* says so, rather than recording a
    terminal state the owner cannot account for.
    """
    task_status, fallback = RUN_OUTCOMES.get(
        status,
        ("failed", f"The run ended with an unrecognised status: {status or 'unknown'}."),
    )
    return task_status, ((message or "").strip()[:SUMMARY_MAX_CHARS] or fallback)


# Recurring cadences and the gap between one governed cycle and the next. A
# recurring task is re-armed after every cycle rather than closed, so a standing
# agent — "keep improving the landing page", "watch the build" — keeps working
# until the owner stops it. `continuous` is the shortest cadence offered: it is
# still one discrete governed turn per cycle, never an unbounded loop, so every
# cycle passes through policy, gates, and approvals exactly like a typed prompt.
CONTINUOUS_INTERVAL = timedelta(minutes=20)
RECURRING_INTERVALS: dict[str, timedelta] = {
    "continuous": CONTINUOUS_INTERVAL,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def next_run_after(iso: str, interval: timedelta) -> str:
    """The first `iso + n*interval` that is still in the future.

    Stepping forward from the original slot (rather than from "now") keeps a
    schedule anchored to the time the owner picked, and skipping past every
    elapsed slot means a host that was asleep does not wake up owing a backlog
    of identical runs.
    """
    next_run = datetime.fromisoformat(iso.replace("Z", "+00:00")) + interval
    now = datetime.now(UTC)
    while next_run <= now:
        next_run += interval
    return next_run.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_daily(iso: str) -> str:
    return next_run_after(iso, RECURRING_INTERVALS["daily"])
