"""Owner interrupts applied at a safe boundary — and carried down delegation.

DEC-12 step 7 — a task that delegated work is the owner's one handle on all of
it. Pausing or stopping the parent used to settle the parent's row and leave
every child it had delegated running on, so "stop this" stopped the part the
owner could see. A pause, stop or resume now reaches every unfinished task
delegated below the one it names, each with its own event naming the task the
decision came from. ``stop-all`` already sweeps every task, so it does not ask
for the cascade a second time.
"""

from __future__ import annotations

from raiker.contracts.models import InterruptAction, TaskRecord
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


class InterruptController:
    def __init__(self, store: SQLiteStore, writer: EventLogWriter | None = None) -> None:
        self.store = store
        self.writer = writer

    #: Which delegated tasks each decision reaches. A child that already ended
    #: is history and is never touched; resume reaches only a paused child.
    _CASCADE_FROM: dict[str, frozenset[str]] = {
        "pause": frozenset(
            {"queued", "running", "continuing", "waiting_for_approval", "waiting_for_children"}
        ),
        "resume": frozenset({"paused"}),
        "cancel": frozenset(
            {
                "queued", "running", "continuing", "paused",
                "waiting_for_approval", "waiting_for_children",
            }
        ),
    }

    def apply_at_safe_boundary(
        self,
        action: InterruptAction,
        *,
        propagate: bool = True,
        user_id: str | None = None,
    ) -> str:
        result = self._apply_one(action)
        if propagate and action.action_type in self._CASCADE_FROM:
            self.propagate_to_children(action, user_id=user_id)
        return result

    def propagate_to_children(
        self, action: InterruptAction, *, user_id: str | None = None
    ) -> list[TaskRecord]:
        """Carry *action* to every unfinished task delegated below its task."""
        reach = self._CASCADE_FROM.get(action.action_type)
        if reach is None:
            return []
        reached: list[TaskRecord] = []
        for child in self.store.descendant_tasks(action.task_id, user_id=user_id):
            if child.status not in reach:
                continue
            reason = f"Delegated by a task the owner {self._VERB[action.action_type]}: {action.reason}"
            self._apply_one(
                InterruptAction(
                    action_id=action.action_id,
                    task_id=child.task_id,
                    session_id=child.session_id,
                    action_type=action.action_type,
                    reason=reason,
                    steer_text=None,
                ),
                propagated_from=action.task_id,
            )
            reached.append(child)
        return reached

    _VERB = {"pause": "paused", "resume": "resumed", "cancel": "stopped"}

    def _apply_one(self, action: InterruptAction, *, propagated_from: str | None = None) -> str:
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
            self._task_event(action, "task_paused", propagated_from)
            return "paused"
        if action.action_type == "cancel":
            self.store.cancel_task(action.task_id, action.reason)
            self._task_event(action, "task_cancelled", propagated_from)
            return "cancelled"
        if action.action_type == "resume":
            self.store.update_task_status(action.task_id, "running")
            self._task_event(action, "task_resumed", propagated_from)
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

    def _task_event(
        self, action: InterruptAction, event_type: str, propagated_from: str | None = None
    ) -> None:
        if self.writer:
            payload: dict[str, object] = {"task_id": action.task_id, "reason": action.reason}
            if propagated_from is not None:
                payload["propagated_from"] = propagated_from
            self.writer.append(make_event(session_id=action.session_id, turn_id=None, event_type=event_type, actor="runtime", payload=payload))
