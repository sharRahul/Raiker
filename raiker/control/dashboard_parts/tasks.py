# mypy: disable-error-code="misc"
"""Tasks and their detail and history (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from raiker.contracts.ids import new_id, utc_now
from raiker.control.views.tasks import (
    TASK_RECURRENCES,
    PathAttachment,
    TaskDetailView,
    TaskView,
    UploadAttachment,
)
from raiker.events.writer import EventLogWriter
from raiker.models.registry import ModelProfileRegistry
from raiker.tasks.history import derive_attempts
from raiker.tasks.lifecycle import task_phase
from raiker.tasks.manager import TaskManager
from raiker.tasks.schedule import schedule_terms

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class TaskService:

    def list_tasks(
        self: DashboardService,
        session_id: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[TaskView]:
        # The user-facing work queue lists only tasks the user created. Each chat
        # turn also spawns an internal governance task (``parent_turn_id`` set);
        # those are surfaced in Sessions/Audit, not here, so they no longer
        # inflate the open/scheduled/finished counters or appear as selectable
        # "Parent work" (FIX-06). Interrupts operate on the raw store list, so a
        # running chat turn can still be stopped.
        rows = [
            t
            for t in self.store.list_tasks(
                session_id=session_id, status=status, user_id=user_id, project_id=project_id
            )
            if not getattr(t, "parent_turn_id", None)
        ]
        # C11 — one query for the whole list. A card links to its task's own
        # conversation, and whether that thread has anything in it yet is the
        # difference between a link worth pressing and an empty page.
        turns = self.store.count_turns_by_session(
            [t.thread_session_id or "" for t in rows]
        )
        return [
            self._task_view(t, thread_turns=turns.get(t.thread_session_id or "", 0))
            for t in rows
        ]

    #: How many of a task's own governed events one detail read will group.
    #: A bound rather than a page: a task with more transitions than this is
    #: told so by ``truncated`` instead of being silently shortened, and the
    #: whole trail stays readable in the audit log, which is where an
    #: unbounded read belongs.
    TASK_HISTORY_EVENT_LIMIT = 400

    def get_task_detail(
        self: DashboardService, task_id: str, *, user_id: str | None = None
    ) -> TaskDetailView | None:
        """One task's attempts, in order, or ``None`` when it is not visible.

        BUG-299. Read entirely from records the task's lifecycle already wrote:
        the governed events indexed against this ``task_id``, grouped into the
        runs they describe. Ownership is the store's own visibility rule, so a
        task absent from this account's board is absent from its address too.

        A payload that cannot be read back — a rotated log, a line the index
        outlived — does not lose the row: the transition is still shown with the
        sentence its kind carries, because "something happened here and the
        detail is gone" is a truer history than a gap.
        """
        record = self.store.load_task_for_user(task_id, user_id)
        if record is None:
            return None
        rows = self.store.list_event_index(
            task_id=task_id, limit=self.TASK_HISTORY_EVENT_LIMIT + 1
        )
        truncated = len(rows) > self.TASK_HISTORY_EVENT_LIMIT
        rows = rows[: self.TASK_HISTORY_EVENT_LIMIT]
        from raiker.events.query import EventViewer

        viewer = EventViewer(self.store)
        events: list[dict[str, Any]] = []
        # `list_event_index` answers newest first; a history is read oldest
        # first, and an attempt cannot be grouped in reverse.
        for row in reversed(rows):
            payload = viewer.read_event_payload(str(row.get("event_id", "")))
            events.append(
                {
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "timestamp": row.get("timestamp"),
                    "actor": row.get("actor"),
                    "turn_id": row.get("turn_id"),
                    "session_id": row.get("session_id"),
                    "payload": (payload or {}).get("payload", {}) if payload else {},
                }
            )
        turns = self.store.count_turns_by_session([record.thread_session_id or ""])
        approvals = [
            approval
            for approval in self.list_approvals(user_id=user_id)
            if approval.session_id in {record.session_id, record.run_session_id}
        ]
        return TaskDetailView(
            task=self._task_view(
                record, thread_turns=turns.get(record.thread_session_id or "", 0)
            ),
            attempts=derive_attempts(events),
            approvals=approvals,
            truncated=truncated,
        )

    def create_task(
        self: DashboardService,
        *,
        title: str,
        objective: str,
        user_id: str | None,
        principal_id: str,
        priority: str | None = None,
        scheduled_at: str | None = None,
        recurrence: str | None = None,
        reminder_at: str | None = None,
        parent_task_id: str | None = None,
        project_id: str | None = None,
        model_profile: str | None = None,
        model: str | None = None,
        surface: str = "chat",
        attachments: list[dict[str, Any]] | None = None,
        start_immediately: bool = True,
        timezone: str | None = None,
        run_until: str | None = None,
        missed_runs: str | None = None,
    ) -> TaskView:
        """Create a local planning task in the caller's server-owned Inbox session.

        Project-scoped schedules: the task is stamped with ``project_id`` when
        given, else with the active project, so a schedule created inside a
        project stays scoped to it. The stamp is an organizing label — it
        grants nothing.

        ``surface`` (backlog #23) chooses the working method this task's cycles
        run under. A `build` task needs a project, because Build's whole method
        is a repository it can read: without one it would be Chat wearing the
        wrong standing instructions, so it is refused with a stated reason
        rather than accepted and quietly downgraded.
        """
        if recurrence is not None and recurrence not in TASK_RECURRENCES:
            raise ValueError(f"invalid_recurrence:{recurrence}")
        from raiker.contracts.models import PROMPT_SURFACES

        if surface not in PROMPT_SURFACES:
            raise ValueError(f"invalid_surface:{surface}")
        if bool(model_profile) != bool(model):
            raise ValueError("task_model_pair_required")
        if model_profile and model:
            try:
                profile = ModelProfileRegistry.load().resolve_profile_id(model_profile)
            except Exception as exc:  # noqa: BLE001 - unknown choices fail closed
                raise ValueError(f"unknown_profile:{model_profile}") from exc
            if bool(profile.raw.get("test_only", False)):
                raise ValueError(f"test_profile_not_allowed:{model_profile}")
            if not self.store.is_configured_model(principal_id, model_profile, model):
                raise ValueError("model_not_configured_for_task")
        clean_attachments: list[dict[str, Any]] = []
        if len(attachments or []) > 8:
            raise ValueError("too_many_attachments")
        for entry in attachments or []:
            if not isinstance(entry, dict):
                raise ValueError("invalid_attachment")
            kind = entry.get("type")
            if kind == "path" and isinstance(entry.get("path"), str) and entry["path"].strip():
                clean_attachments.append({"type": "path", "path": entry["path"].strip()})
                continue
            attachment_id = entry.get("attachment_id")
            if (
                kind in {"image", "document"}
                and isinstance(attachment_id, str)
                and attachment_id.strip()
            ):
                if (
                    self.store.load_attachment_metadata(
                        attachment_id.strip(), owner_principal_id=principal_id
                    )
                    is None
                ):
                    raise ValueError("attachment_not_found")
                clean_attachments.append({"type": kind, "attachment_id": attachment_id.strip()})
                continue
            raise ValueError("invalid_attachment")
        # BUG-64 — creation and execution are separate decisions for a model-
        # proposed task. Human use of Tasks keeps the established start-now
        # default; approval execution passes false and parks the new row until
        # the owner explicitly runs it. A model-supplied date does not smuggle
        # scheduling authority through a creation approval.
        if not start_immediately:
            scheduled_at = None
        elif scheduled_at is None:
            scheduled_at = utc_now()
        # UX-TASK-02 — the schedule's terms, validated before anything is
        # written. A weekday routine anchored on a Saturday first runs on the
        # Monday, so the stored first slot is the one the scheduler will claim.
        terms = schedule_terms(
            recurrence=recurrence,
            scheduled_at=scheduled_at if start_immediately else None,
            timezone=timezone,
            run_until=run_until,
            missed_runs=missed_runs,
        )
        if terms.first_run is not None:
            scheduled_at = terms.first_run
        if project_id is None:
            project_id = self.store.get_active_project(user_id)
        elif self.store.load_project(project_id, user_id) is None:
            raise ValueError(f"unknown_project:{project_id}")
        # Backlog #23 — Build's method is a repository it can read. A build task
        # with no project would run Build's standing instructions over Chat's
        # scope, which is the kind of half-configured state this product refuses
        # rather than accepts and explains later.
        if surface == "build" and not project_id:
            raise ValueError("build_task_requires_project")
        if parent_task_id is not None:
            parent = self.store.load_task(parent_task_id)
            parent_session = (
                self.store.load_session(parent.session_id) if parent is not None else None
            )
            if (
                parent is None
                or parent_session is None
                or (user_id is not None and parent_session.get("user_id") not in (None, user_id))
            ):
                raise ValueError(f"unknown_parent_task:{parent_task_id}")
        inbox_session_id = f"sess_inbox_{principal_id}"
        # Task origin (BUG-10): the Inbox is a server-owned session that task
        # runs execute in, not a conversation the owner had. Tagging it keeps it
        # out of RECENT CHATS while leaving it fully readable in Sessions.
        self.store.create_session(
            inbox_session_id,
            str(self.store.paths.workspace_root),
            title="Inbox",
            user_id=user_id,
            origin="task",
        )
        self.store.set_session_origin(inbox_session_id, "task")
        # C11 — this task's own conversation, so "what did the overnight run
        # find?" has a thread to be asked in and routines' cycles never
        # interleave in one transcript.
        #
        # Each task gets a durable session of its own, titled after the task,
        # which every cycle runs in. The owner opens it from the task card and
        # replies there, and because the next cycle runs in the same session, the
        # reply is context the next cycle reads — which is what makes a reply
        # steer rather than merely be recorded.
        #
        # `origin="task"` keeps it out of RECENT CHATS: these are threads the
        # owner opens *from their work*, not conversations they started.
        thread_session_id = new_id("sess_")
        self.store.create_session(
            thread_session_id,
            str(self.store.paths.workspace_root),
            title=title,
            user_id=user_id,
            origin="task",
        )
        self.store.set_session_origin(thread_session_id, "task")
        task = TaskManager(self.store, EventLogWriter(self.store)).create_task(
            session_id=inbox_session_id,
            thread_session_id=thread_session_id,
            surface=surface,
            title=title,
            objective=objective,
            priority=priority,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
            reminder_at=reminder_at,
            parent_task_id=parent_task_id,
            project_id=project_id,
            model_profile=model_profile,
            model=model,
            attachments=clean_attachments,
            schedule_timezone=terms.timezone,
            schedule_anchor=terms.anchor,
            schedule_until=terms.until,
            missed_run_policy=terms.missed_run_policy,
        )
        return self._task_view(task)

    def run_task_now(self: DashboardService, task_id: str, *, user_id: str | None) -> TaskView:
        """Schedule one visible, queued, unscheduled task for immediate claim."""
        from raiker.events.types import make_event

        task, reason = self.store.schedule_task_now(task_id, user_id=user_id)
        if task is None:
            raise ValueError(reason or "task_not_runnable")
        EventLogWriter(self.store).append(
            make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_run_requested",
                actor="dashboard",
                payload={"task_id": task.task_id, "scheduled_at": task.scheduled_at},
            )
        )
        return self._task_view(task)

    @staticmethod
    def _task_view(task: Any, *, thread_turns: int = 0) -> TaskView:
        d = asdict(task) if not isinstance(task, dict) else task
        return TaskView(
            task_id=str(d["task_id"]),
            session_id=str(d.get("session_id", "")),
            status=str(d.get("status", "")),
            title=str(d.get("title", "")),
            objective=str(d.get("objective", "")),
            current_step=d.get("current_step"),
            progress_percent=d.get("progress_percent"),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            completed_at=d.get("completed_at"),
            summary=d.get("summary"),
            priority=d.get("priority"),
            scheduled_at=d.get("scheduled_at"),
            recurrence=d.get("recurrence"),
            reminder_at=d.get("reminder_at"),
            parent_task_id=d.get("parent_task_id"),
            project_id=d.get("project_id"),
            model_profile=d.get("model_profile"),
            model=d.get("model"),
            surface=str(d.get("surface") or "chat"),
            thread_session_id=d.get("thread_session_id"),
            thread_turns=thread_turns,
            attachments=[cast(PathAttachment | UploadAttachment, item) for item in d.get("attachments") or []],
            schedule_timezone=d.get("schedule_timezone"),
            schedule_until=d.get("schedule_until"),
            missed_run_policy=d.get("missed_run_policy"),
            phase=task_phase(str(d.get("status", "")), d.get("scheduled_at")),
        )
