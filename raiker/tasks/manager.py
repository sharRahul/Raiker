from __future__ import annotations

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import TaskRecord
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


class TaskManager:
    def __init__(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        self.store = store
        self.writer = writer

    def create_task(
        self,
        *,
        session_id: str,
        title: str,
        objective: str,
        parent_turn_id: str | None = None,
        parent_task_id: str | None = None,
    ) -> TaskRecord:
        now = utc_now()
        task = TaskRecord(
            task_id=new_id("task_"),
            session_id=session_id,
            title=title,
            objective=objective,
            status="queued",
            created_at=now,
            updated_at=now,
            parent_turn_id=parent_turn_id,
            parent_task_id=parent_task_id,
        )
        self.store.insert_task(task)
        event = make_event(
            session_id=session_id,
            turn_id=parent_turn_id,
            event_type="task_created",
            actor="task_manager",
            payload={
                "task_id": task.task_id,
                "session_id": session_id,
                "title": title,
                "objective": objective,
                "status": task.status,
            },
        )
        self.writer.append(event)
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.store.load_task(task_id)

    def list_tasks(self, session_id: str | None = None, status: str | None = None) -> list[TaskRecord]:
        return self.store.list_tasks(session_id=session_id, status=status)

    def update_progress(self, task_id: str, *, current_step: str, progress_percent: int) -> TaskRecord | None:
        self.store.update_task_progress(task_id, current_step, progress_percent)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_progress",
                actor="task_manager",
                payload={
                    "task_id": task_id,
                    "current_step": current_step,
                    "progress_percent": progress_percent,
                    "status": task.status,
                },
            )
            self.writer.append(event)
        return task

    def complete_task(self, task_id: str, summary: str | None = None) -> TaskRecord | None:
        self.store.complete_task(task_id, summary)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_completed",
                actor="task_manager",
                payload={"task_id": task_id, "summary": summary or ""},
            )
            self.writer.append(event)
        return task

    def fail_task(self, task_id: str, reason: str) -> TaskRecord | None:
        self.store.fail_task(task_id, reason)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_failed",
                actor="task_manager",
                payload={"task_id": task_id, "reason": reason},
            )
            self.writer.append(event)
        return task

    def cancel_task(self, task_id: str, reason: str) -> TaskRecord | None:
        self.store.cancel_task(task_id, reason)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_cancelled",
                actor="task_manager",
                payload={"task_id": task_id, "reason": reason},
            )
            self.writer.append(event)
        return task