from __future__ import annotations

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import TaskRecord
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import HookInput
from raiker.hooks.dispatcher import HookDispatcher
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
    """Creates, advances and ends tasks, and tells hooks about the two ends of one.

    A task is the unit of work the owner sees on a card, and it outlives the turn
    that started it: a scheduled run has no turn at all. `TaskCreated` and
    `TaskCompleted` are therefore dispatched here rather than from any caller,
    because here is the only place that sees every task regardless of who asked
    for it (BUG-223).

    The dispatcher is optional and built lazily from the workspace when it is not
    supplied, so a caller that never had one — the scheduler, a CLI command —
    still fires the hooks, with the owner's off switch already applied by
    :func:`~raiker.hooks.factory.dispatcher_for_workspace`.
    """

    def __init__(
        self,
        store: SQLiteStore,
        writer: EventLogWriter,
        hook_dispatcher: HookDispatcher | None = None,
    ) -> None:
        self.store = store
        self.writer = writer
        self._hook_dispatcher = hook_dispatcher
        self._hook_dispatcher_resolved = hook_dispatcher is not None

    def _hooks(self) -> HookDispatcher | None:
        """The dispatcher for this workspace, built once and reused.

        Built lazily rather than in ``__init__`` because a ``TaskManager`` is
        constructed on paths that never touch a task — reading the hooks config
        from disk to answer a question nobody asked would be a file read per
        construction.
        """
        if not self._hook_dispatcher_resolved:
            self._hook_dispatcher_resolved = True
            try:
                from raiker.hooks.factory import dispatcher_for_workspace

                self._hook_dispatcher = dispatcher_for_workspace(
                    self.store, writer=self.writer
                )
            except Exception:  # noqa: BLE001 — hooks never break task bookkeeping
                self._hook_dispatcher = None
        return self._hook_dispatcher

    def _dispatch_task_hook(
        self, event_name: str, task: TaskRecord, extra: dict[str, object]
    ) -> None:
        """Observation only. Neither event can refuse or alter the task.

        A task is created because something already decided to do the work; the
        place to refuse that is the tool call it will make, under `PreToolUse`,
        where a refusal is enforced by the broker rather than by bookkeeping.

        The outcome *text* is not passed, only its length. A chat turn completes
        its task with the assistant's reply as the summary, and a `command`
        handler is a subprocess — one a repository's own `config/hooks.json` can
        introduce. A rule reacting to a task ending needs to know which task and
        how it ended; a handler that needs what was said can read the audit trail
        under its own authority.
        """
        dispatcher = self._hooks()
        if dispatcher is None or not dispatcher.is_active():
            return
        try:
            dispatcher.dispatch(
                HookInput(
                    event_name=event_name,
                    tool_name=None,
                    tool_input={},
                    context={
                        "task_id": task.task_id,
                        "title": task.title,
                        "status": task.status,
                        **extra,
                    },
                    session_id=task.session_id,
                    turn_id=task.parent_turn_id,
                ),
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
            )
        except Exception:  # noqa: BLE001 — a hook failure never loses a task record
            return

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
        thread_session_id: str | None = None,
        surface: str = "chat",
    ) -> TaskRecord:
        now = utc_now()
        task = TaskRecord(
            task_id=new_id("task_"),
            session_id=session_id,
            thread_session_id=thread_session_id,
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
            surface=surface,
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
                # Backlog #23 — which working method this task's cycles run
                # under, recorded so the audit trail states it rather than
                # leaving it to be inferred from the standing instructions.
                "surface": task.surface,
                "attachments": task.attachments,
            },
        )
        self.writer.append(event)
        self._dispatch_task_hook(
            "TaskCreated",
            task,
            {"parent_task_id": task.parent_task_id, "surface": task.surface},
        )
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
        """Finish a task - unless it delegated work that has not finished.

        BUG-220 - ``parent_task_id`` recorded the structure and nothing owned
        it, so a task that split its work into children reported ``completed``
        the moment its own run ended, while a child sat parked on an approval.
        That is a false completion: it tells the owner the work is done and
        removes it from everything that counts unfinished work.

        The parent is parked instead, and :meth:`_settle_parent` moves it when
        the last child lands. Nothing is inherited in the other direction - a
        child carries its own approvals, because a parent's decision standing in
        for its children's is exactly what the per-turn capability envelope
        exists to prevent.
        """
        if self._unfinished_children(task_id):
            return self._hold_for_children(task_id, summary)
        # C10 — read before the write, because the write is what changes it. A
        # parent settling out of `waiting_for_children` is `completed` by the
        # time the notice is sent, and asking then would answer about the wrong
        # moment.
        was_background = self._was_unwatched(task_id)
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
            self._dispatch_task_hook(
                "TaskCompleted", task, {"outcome": "completed", "summary_length": len(summary or "")}
            )
            self._notify_owner(task, outcome="completed", was_background=was_background)
            self._settle_parent(task)
        return task

    def fail_task(self, task_id: str, reason: str) -> TaskRecord | None:
        stated = _stated(reason, NO_STATED_FAILURE_REASON)
        was_background = self._was_unwatched(task_id)
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
            # Terminal is terminal. A rule that cleans up after a task must run
            # when the task failed too, or it only ever tidies the happy path.
            self._dispatch_task_hook(
                "TaskCompleted", task, {"outcome": "failed", "summary_length": len(stated)}
            )
            self._notify_owner(task, outcome="failed", was_background=was_background)
            self._settle_parent(task)
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

    # ── Telling the owner it ended (GAP-CHAT C10) ───────────────────────────

    def _was_unwatched(self, task_id: str) -> bool:
        """True when this task was parked for delegated children before it ended.

        The one background condition that is *lost* by the write about to
        happen. The schedule-carrying case survives it and is read from the
        record itself, in the notifier.
        """
        current = self.get_task(task_id)
        return current is not None and current.status == "waiting_for_children"

    def _notify_owner(self, task: TaskRecord, *, outcome: str, was_background: bool) -> None:
        """Tell the owner that work they were not watching has ended.

        Isolated for the same reason the hook dispatch is: a notice is a
        courtesy on top of a record that already exists, and it must never be
        able to fail the task it is about.
        """
        try:
            from raiker.notify.task_notifier import notify_task_finished

            notify_task_finished(
                self.store, task, outcome=outcome, was_background=was_background
            )
        except Exception:  # noqa: BLE001 - the task's outcome is already recorded
            return

    # ── Delegation ownership (BUG-220) ──────────────────────────────────────

    def _unfinished_children(self, task_id: str) -> list[str]:
        """Delegated tasks that have not reached a terminal state."""
        return [
            state
            for state in self.store.child_task_states(task_id)
            if state not in self.store.TERMINAL_TASK_STATES
        ]

    def _hold_for_children(self, task_id: str, summary: str | None) -> TaskRecord | None:
        self.store.hold_task_for_children(task_id, summary)
        task = self.get_task(task_id)
        if task is not None:
            self.writer.append(
                make_event(
                    session_id=task.session_id,
                    turn_id=task.parent_turn_id,
                    event_type="task_waiting_for_children",
                    actor="task_manager",
                    payload={
                        "task_id": task_id,
                        "unfinished_children": len(self._unfinished_children(task_id)),
                        "summary": summary or "",
                    },
                )
            )
        return task

    def _settle_parent(self, child: TaskRecord) -> None:
        """Move a parent that was only waiting on this child.

        Deliberately narrow: it moves a parent that is *parked for its children*
        and nothing else. A parent still running has its own work to finish and
        its own outcome to report, and a parent that already reached a terminal
        state is not reopened by a late child - a terminal state that can be
        walked back is not one an audit record can rely on.
        """
        parent_id = child.parent_task_id
        if not parent_id:
            return
        parent = self.get_task(parent_id)
        if parent is None or parent.status != "waiting_for_children":
            return
        if self._unfinished_children(parent_id):
            return
        states = self.store.child_task_states(parent_id)
        failed = [state for state in states if state in ("failed", "cancelled")]
        if failed:
            self.fail_task(
                parent_id,
                f"{len(failed)} of {len(states)} delegated tasks did not complete.",
            )
        else:
            self.complete_task(
                parent_id, f"All {len(states)} delegated tasks completed."
            )

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
            self._dispatch_task_hook(
                "TaskCompleted", task, {"outcome": "cancelled", "summary_length": len(stated)}
            )
            self._settle_parent(task)
        return task
