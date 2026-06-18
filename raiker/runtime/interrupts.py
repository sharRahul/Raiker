from __future__ import annotations

from raiker.contracts.models import InterruptAction
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


class InterruptController:
    def __init__(self, store: SQLiteStore, writer: EventLogWriter | None = None) -> None:
        self.store = store
        self.writer = writer

    def apply_at_safe_boundary(self, action: InterruptAction) -> str:
        if self.writer:
            self.writer.append(
                make_event(
                    session_id=action.session_id,
                    turn_id=None,
                    event_type="interrupt_received",
                    actor="runtime",
                    payload=action.to_dict(),
                )
            )
            self.writer.append(
                make_event(
                    session_id=action.session_id,
                    turn_id=None,
                    event_type="safe_boundary_reached",
                    actor="runtime",
                    payload={"task_id": action.task_id},
                )
            )
        if action.action_type == "pause":
            self.store.update_task_status(action.task_id, "paused")
            return "paused"
        if action.action_type == "cancel":
            self.store.cancel_task(action.task_id, action.reason)
            return "cancelled"
        if action.action_type == "resume":
            self.store.update_task_status(action.task_id, "running")
            return "running"
        self.store.update_task_progress(action.task_id, action.steer_text or action.reason, 0)
        if self.writer:
            self.writer.append(
                make_event(
                    session_id=action.session_id,
                    turn_id=None,
                    event_type="task_steered",
                    actor="runtime",
                    payload={"task_id": action.task_id, "steer_text": action.steer_text},
                )
            )
        return "steered"
