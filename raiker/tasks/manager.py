from __future__ import annotations

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import TaskRecord
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore

# What a task's outcome says when the run that ended it left no words of its own.
# A terminal task must always carry a reason: an empty summary is what made a
# failed background run unreadable in the UI and the audit log (BUG-09).
NO_STATED_FAILURE_REASON = "The run ended without a stated reason."
NO_STATED_APPROVAL_REASON = "The run is waiting for your approval to continue."
NO_STATED_CANCEL_REASON = "The run was stopped without a stated reason."


def _stated(reason: str | None, fallback: str) -> str:
    """The reason to record — never blank, never a lie about what happened."""
    return (reason or "").strip() or fallback


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
        priority: str | None = None,
        scheduled_at: str | None = None,
        recurrence: str | None = None,
        reminder_at: str | None = None,
        project_id: str | None = None,
        model_profile: str | None = None,
        model: str | None = None,
        attachments: list[dict[str, object]] | None = None,
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
            priority=priority,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
            reminder_at=reminder_at,
            project_id=project_id,
            model_profile=model_profile,
            model=model,
            attachments=list(attachments or []),
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
                "attachments": task.attachments,
            },
        )
        self.writer.append(event)
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.store.load_task(task_id)

    def list_tasks(
        self, session_id: str | None = None, status: str | None = None
    ) -> list[TaskRecord]:
        return self.store.list_tasks(session_id=session_id, status=status)

    def update_progress(
        self, task_id: str, *, current_step: str, progress_percent: int
    ) -> TaskRecord | None:
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
        stated = _stated(reason, NO_STATED_FAILURE_REASON)
        self.store.fail_task(task_id, stated)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_failed",
                actor="task_manager",
                payload={"task_id": task_id, "reason": stated},
            )
            self.writer.append(event)
        return task

    def block_task_on_approval(self, task_id: str, reason: str) -> TaskRecord | None:
        """Park a task that stopped at an approval boundary.

        The run neither finished nor failed; it is waiting for a decision, and
        both the task card and the audit log say so.
        """
        stated = _stated(reason, NO_STATED_APPROVAL_REASON)
        self.store.block_task_on_approval(task_id, stated)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_blocked",
                actor="task_manager",
                payload={"task_id": task_id, "reason": stated, "status": task.status},
            )
            self.writer.append(event)
        return task

    def mark_task_continuing(self, task_id: str, tool_name: str = "") -> TaskRecord | None:
        """A granted approval is being replayed into this task's parked turn.

        The card moves off *waiting for approval* the moment the continuation
        starts, so the owner sees the decision take effect rather than watching
        an unchanged card and wondering whether approving did anything (BUG-25).
        From here the run lands on running, completed or failed like any other.
        """
        step = (
            f"Continuing after approval of {tool_name}" if tool_name.strip()
            else "Continuing after approval"
        )
        self.store.resume_task_after_approval(task_id, step)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_resume_started",
                actor="task_scheduler",
                payload={"task_id": task_id, "tool_name": tool_name, "status": task.status},
            )
            self.writer.append(event)
        return task

    def report_resume_blocked(self, task_id: str, reason: str) -> TaskRecord | None:
        """An automatic continuation could not proceed, and the card says why.

        The task stays parked rather than being failed: nothing about the work
        went wrong, and the owner still has a decision or a retry available.
        """
        stated = _stated(reason, NO_STATED_APPROVAL_REASON)
        self.store.block_task_on_approval(task_id, stated)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_resume_blocked",
                actor="task_scheduler",
                payload={"task_id": task_id, "reason": stated, "status": task.status},
            )
            self.writer.append(event)
        return task

    def cancel_task(self, task_id: str, reason: str) -> TaskRecord | None:
        stated = _stated(reason, NO_STATED_CANCEL_REASON)
        self.store.cancel_task(task_id, stated)
        task = self.get_task(task_id)
        if task is not None:
            event = make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_cancelled",
                actor="task_manager",
                payload={"task_id": task_id, "reason": stated},
            )
            self.writer.append(event)
        return task
