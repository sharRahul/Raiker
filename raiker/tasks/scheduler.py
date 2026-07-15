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
                    user=UserMetadata(id=principal_id), prompt=PromptPayload(text=prompt), options=PromptOptions(),
                )
            )
            manager = TaskManager(self.store, EventLogWriter(self.store))
            # A user may have stopped the task while its governed turn was
            # reaching a safe boundary; never overwrite that cancellation.
            current = self.store.load_task(task.task_id)
            if current is None or current.status == "cancelled":
                continue
            if task.recurrence == "daily" and task.scheduled_at:
                next_run = _next_daily(task.scheduled_at)
                manager.store.reschedule_task(task.task_id, next_run, response.message[:500])
            elif response.status == "completed":
                manager.complete_task(task.task_id, response.message[:500])
            else:
                manager.fail_task(task.task_id, response.message[:500])
        return len(tasks)


def _next_daily(iso: str) -> str:
    next_run = datetime.fromisoformat(iso.replace("Z", "+00:00")) + timedelta(days=1)
    now = datetime.now(UTC)
    while next_run <= now:
        next_run += timedelta(days=1)
    return next_run.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
