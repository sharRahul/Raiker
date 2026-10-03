# mypy: disable-error-code="misc"
"""Tasks, routines, delegated work and the local-only planning records (reminders,
calendar events, email drafts) (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.contracts.models import HostedRoutine, SubagentContract, TaskRecord, TeamLedger

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class TaskStore:

    def insert_task(self: SQLiteStore, task: TaskRecord) -> None:
        self._execute(
            """
            INSERT OR IGNORE INTO tasks
            (task_id, session_id, thread_session_id, parent_turn_id, parent_task_id, title, objective, status, current_step, progress_percent, created_at, updated_at, completed_at, priority, scheduled_at, recurrence, reminder_at, project_id, model_profile, model, surface, attachments_json, schedule_timezone, schedule_anchor, schedule_until, missed_run_policy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.task_id,
                task.session_id,
                task.thread_session_id,
                task.parent_turn_id,
                task.parent_task_id,
                task.title,
                task.objective,
                task.status,
                task.current_step,
                task.progress_percent,
                task.created_at,
                task.updated_at,
                task.completed_at,
                task.priority,
                task.scheduled_at,
                task.recurrence,
                task.reminder_at,
                task.project_id,
                task.model_profile,
                task.model,
                task.surface,
                json.dumps(task.attachments, sort_keys=True),
                task.schedule_timezone,
                task.schedule_anchor,
                task.schedule_until,
                task.missed_run_policy,
            ),
        )

    @staticmethod
    def _task_from_row(row: Any) -> TaskRecord:
        data = dict(row)
        raw_attachments = data.pop("attachments_json", "[]")
        try:
            attachments = json.loads(raw_attachments or "[]")
        except (TypeError, ValueError):
            attachments = []
        data["attachments"] = attachments if isinstance(attachments, list) else []
        return TaskRecord(**data)

    def load_task_for_thread_session(self: SQLiteStore, session_id: str) -> TaskRecord | None:
        """The task whose own conversation is *session_id*, if there is one.

        Backlog #23 — this is how a delegating turn's parent is *derived* rather
        than supplied. A cycle runs in its task's thread (C11), so the running
        task is a fact about the session the broker already trusts; taking a
        `parent_task_id` from the model instead would let one turn attach work to
        somebody else's tree.
        """
        row = self._row("SELECT * FROM tasks WHERE thread_session_id = ? LIMIT 1", (session_id,))
        return self._task_from_row(row) if row is not None else None

    def load_task(self: SQLiteStore, task_id: str) -> TaskRecord | None:
        row = self._row("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        if row is None:
            return None
        return self._task_from_row(row)

    def load_task_for_user(self: SQLiteStore, task_id: str, user_id: str | None) -> TaskRecord | None:
        """One task, only if this account may see it (BUG-299).

        The same visibility rule :meth:`list_tasks` applies — the task's owning
        session belongs to this account, or to nobody — rather than a second
        one, so a task that is absent from the board can never be readable at
        its own address. ``user_id`` of ``None`` is the unattributed
        single-owner workspace and reads as :meth:`load_task` does.
        """
        if user_id is None:
            return self.load_task(task_id)
        row = self._row(
            "SELECT * FROM tasks WHERE task_id = ? AND session_id IN "
            "(SELECT session_id FROM sessions WHERE user_id = ? OR user_id IS NULL)",
            (task_id, user_id),
        )
        return self._task_from_row(row) if row is not None else None

    def list_tasks(
        self: SQLiteStore,
        session_id: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[TaskRecord]:
        query = "SELECT * FROM tasks"
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if project_id is not None:
            # Project-scoped schedules: a project's task list shows only the
            # tasks created under that project.
            conditions.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if user_id is not None:
            # Only tasks whose owning session is visible to this account
            # (its own sessions plus legacy/unattributed ones).
            conditions.append(
                "session_id IN (SELECT session_id FROM sessions "
                "WHERE user_id = ? OR user_id IS NULL)"
            )
            params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [self._task_from_row(row) for row in rows]

    def claim_due_tasks(self: SQLiteStore, now: str, limit: int = 10) -> list[TaskRecord]:
        """Atomically claim scheduled work so two host ticks cannot run it twice."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM tasks WHERE status = 'queued' AND scheduled_at IS NOT NULL
                   AND scheduled_at <= ? ORDER BY scheduled_at ASC LIMIT ?""",
                (now, limit),
            ).fetchall()
            claimed: list[TaskRecord] = []
            for row in rows:
                if connection.execute(
                    "UPDATE tasks SET status = 'running', current_step = ?, updated_at = ? WHERE task_id = ? AND status = 'queued'",
                    ("Starting scheduled run", now, row["task_id"]),
                ).rowcount:
                    claimed.append(self._task_from_row(row))
        return claimed

    def schedule_task_now(
        self: SQLiteStore, task_id: str, *, user_id: str | None
    ) -> tuple[TaskRecord | None, str | None]:
        """Atomically make one owner-visible parked task due (BUG-64)."""
        now = utc_now()
        with self.connect() as connection:
            params: list[Any] = [task_id]
            ownership = ""
            if user_id is not None:
                ownership = (
                    " AND session_id IN (SELECT session_id FROM sessions "
                    "WHERE user_id = ? OR user_id IS NULL)"
                )
                params.append(user_id)
            row = connection.execute(
                f"SELECT * FROM tasks WHERE task_id = ?{ownership}", params
            ).fetchone()
            if row is None:
                return None, "task_not_found"
            if row["scheduled_at"] is not None:
                return None, "task_already_scheduled"
            if row["status"] != "queued":
                return None, "task_not_runnable"
            updated = connection.execute(
                "UPDATE tasks SET scheduled_at = ?, updated_at = ?, current_step = ? "
                "WHERE task_id = ? AND status = 'queued' AND scheduled_at IS NULL",
                (now, now, "Ready to start", task_id),
            )
            if updated.rowcount != 1:
                return None, "task_not_runnable"
            scheduled = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(scheduled), None

    def reschedule_task(self: SQLiteStore, task_id: str, scheduled_at: str, summary: str) -> None:
        self._update_task(
            task_id,
            status="queued",
            scheduled_at=scheduled_at,
            current_step="Waiting for next scheduled run",
            progress_percent=0,
            completed_at=None,
            summary=summary,
        )

    def _update_task(self: SQLiteStore, task_id: str, **updates: str | int | None) -> None:
        now = utc_now()
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        self._execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)

    def update_task_progress(self: SQLiteStore, task_id: str, current_step: str, progress_percent: int) -> None:
        self._update_task(task_id, current_step=current_step, progress_percent=progress_percent)

    def complete_task(self: SQLiteStore, task_id: str, summary: str | None = None) -> None:
        now = utc_now()
        self._update_task(task_id, status="completed", completed_at=now, summary=summary)

    def fail_task(self: SQLiteStore, task_id: str, reason: str) -> None:
        now = utc_now()
        self._update_task(task_id, status="failed", completed_at=now, summary=reason)

    def cancel_task(self: SQLiteStore, task_id: str, reason: str) -> None:
        now = utc_now()
        self._update_task(task_id, status="cancelled", completed_at=now, summary=reason)

    def resume_task_after_approval(self: SQLiteStore, task_id: str, current_step: str) -> None:
        """Move a parked task back to running as its continuation starts (BUG-25).

        Guarded on ``waiting_for_approval`` so a task the owner cancelled, or one
        another continuation already picked up, is never dragged back to running.
        """
        self._execute(
            "UPDATE tasks SET status = 'continuing', current_step = ?, summary = NULL, "
            "updated_at = ? WHERE task_id = ? AND status = 'waiting_for_approval'",
            (current_step, utc_now(), task_id),
        )

    def block_task_on_approval(self: SQLiteStore, task_id: str, reason: str) -> None:
        """A run reached an approval boundary: blocked, not finished.

        No ``completed_at`` is stamped — the work is unfinished and the owner's
        decision is what moves it. Recording it as `failed` (BUG-09) told the
        owner the run had gone wrong when nothing had.
        """
        self._update_task(
            task_id,
            status="waiting_for_approval",
            current_step="Waiting for your approval",
            summary=reason,
        )

    #: A task in one of these has stopped for good. Everything else is work the
    #: owner is still owed an outcome for, which is what makes a parent that
    #: reports "done" over one of them a false completion (BUG-220).
    TERMINAL_TASK_STATES = ("completed", "failed", "cancelled")

    def child_task_states(self: SQLiteStore, parent_task_id: str) -> list[str]:
        """The status of every task delegated by *parent_task_id*.

        One row per child rather than a count, because the parent's own outcome
        depends on *which* terminal state the children reached: a parent whose
        child failed did not succeed, and a parent told only "three children,
        none unfinished" could not tell the difference.
        """
        rows = self._rows("SELECT status FROM tasks WHERE parent_task_id = ?", (parent_task_id,))
        return [str(row["status"]) for row in rows]

    def hold_task_for_children(self: SQLiteStore, task_id: str, summary: str | None) -> None:
        """A parent whose own run finished while a child is still open.

        No ``completed_at`` is stamped, for the same reason
        :meth:`block_task_on_approval` stamps none: the delegated work is
        unfinished, and what moves this row is the last child landing.
        """
        self._update_task(
            task_id,
            status="waiting_for_children",
            current_step="Waiting for delegated work",
            summary=summary,
        )

    def count_tasks(self: SQLiteStore, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM tasks"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        row = self._row(query, params)
        return int(row["cnt"]) if row else 0

    def update_task_status(self: SQLiteStore, task_id: str, status: str) -> None:
        self._update_task(task_id, status=status)

    def insert_hosted_routine(self: SQLiteStore, routine: HostedRoutine) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO hosted_routines
            (routine_id, name, routine_type, schedule, endpoint, enabled, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                routine.routine_id,
                routine.name,
                routine.routine_type,
                routine.schedule,
                routine.endpoint,
                int(routine.enabled),
                routine.created_by,
                routine.created_at,
                routine.updated_at,
            ),
        )

    def list_hosted_routines(self: SQLiteStore, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM hosted_routines"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def delete_hosted_routine(self: SQLiteStore, routine_id: str) -> bool:
        changed = self._execute("DELETE FROM hosted_routines WHERE routine_id = ?", (routine_id,))
        return changed > 0


    def insert_scheduled_routine(self: SQLiteStore, routine: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO scheduled_routines
            (routine_id, name, interval_seconds, payload_json, enabled, next_run, last_run, created_by, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                routine["routine_id"],
                routine["name"],
                int(routine["interval_seconds"]),
                routine["payload_json"],
                int(routine.get("enabled", 0)),
                routine["next_run"],
                routine.get("last_run"),
                routine["created_by"],
                routine["created_at"],
                routine.get("status", "scheduled"),
            ),
        )

    def get_scheduled_routine(self: SQLiteStore, routine_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM scheduled_routines WHERE routine_id = ?", (routine_id,))
        return dict(row) if row else None

    def list_scheduled_routines(
        self: SQLiteStore, *, enabled_only: bool = False, due_before: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM scheduled_routines"
        conditions: list[str] = []
        params: list[Any] = []
        if enabled_only:
            conditions.append("enabled = 1")
        if due_before is not None:
            conditions.append("next_run <= ?")
            params.append(due_before)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY next_run ASC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def update_scheduled_routine_run(
        self: SQLiteStore, routine_id: str, *, last_run: str, next_run: str
    ) -> None:
        self._execute(
            "UPDATE scheduled_routines SET last_run = ?, next_run = ? WHERE routine_id = ?",
            (last_run, next_run, routine_id),
        )


    def insert_subagent_contract(self: SQLiteStore, contract: SubagentContract) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO subagent_contracts
            (subagent_id, parent_task_id, name, mode, allowed_tools_json, max_depth, max_runtime_seconds, max_cost, created_by, created_at, status, max_steps, max_tool_calls, max_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract.subagent_id,
                contract.parent_task_id,
                contract.name,
                contract.mode,
                contract.allowed_tools_json,
                contract.max_depth,
                contract.max_runtime_seconds,
                contract.max_cost,
                contract.created_by,
                contract.created_at,
                contract.status,
                contract.max_steps,
                contract.max_tool_calls,
                contract.max_tokens,
            ),
        )

    def list_subagent_contracts(self: SQLiteStore) -> list[dict[str, Any]]:
        rows = self._rows("SELECT * FROM subagent_contracts ORDER BY created_at DESC")
        return [dict(row) for row in rows]


    def insert_team_ledger(self: SQLiteStore, team: TeamLedger) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO team_ledgers
            (team_id, name, mode, members_json, max_depth, max_cost, created_by, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team.team_id,
                team.name,
                team.mode,
                team.members_json,
                team.max_depth,
                team.max_cost,
                team.created_by,
                team.created_at,
                team.status,
            ),
        )

    def list_team_ledgers(self: SQLiteStore) -> list[dict[str, Any]]:
        rows = self._rows("SELECT * FROM team_ledgers ORDER BY created_at DESC")
        return [dict(row) for row in rows]


    def insert_reminder(self: SQLiteStore, record: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO reminders
              (reminder_id, title, due_at, notes, status, created_by,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["reminder_id"],
                record["title"],
                record.get("due_at"),
                record.get("notes"),
                record["status"],
                record["created_by"],
                record["created_at"],
                record["updated_at"],
            ),
        )

    def list_reminders(self: SQLiteStore, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute("SELECT * FROM reminders ORDER BY created_at").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM reminders WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_due_reminders(
        self: SQLiteStore, due_before: str, *, delivery_status: str = "active"
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM reminders WHERE delivery_status = ? AND due_at IS NOT NULL AND due_at <= ? ORDER BY due_at ASC",
            (delivery_status, due_before),
        )
        return [dict(row) for row in rows]

    def update_reminder_status(
        self: SQLiteStore,
        reminder_id: str,
        status: str,
        *,
        delivery_status: str | None = None,
        delivered_at: str | None = None,
        retry_count: int | None = None,
        updated_at: str,
    ) -> bool:
        sets = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, updated_at]
        if delivery_status is not None:
            sets.append("delivery_status = ?")
            params.append(delivery_status)
        if delivered_at is not None:
            sets.append("delivered_at = ?")
            params.append(delivered_at)
        if retry_count is not None:
            sets.append("retry_count = ?")
            params.append(retry_count)
        params.append(reminder_id)
        changed = self._execute(f"UPDATE reminders SET {', '.join(sets)} WHERE reminder_id = ?", params)
        return changed > 0


    def insert_calendar_event(self: SQLiteStore, record: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO calendar_events
              (event_id, title, starts_at, ends_at, location, notes, status,
               created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["event_id"],
                record["title"],
                record.get("starts_at"),
                record.get("ends_at"),
                record.get("location"),
                record.get("notes"),
                record["status"],
                record["created_by"],
                record["created_at"],
                record["updated_at"],
            ),
        )

    def list_calendar_events(self: SQLiteStore, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM calendar_events ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM calendar_events WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]


    def insert_email_draft(self: SQLiteStore, record: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO email_drafts
              (draft_id, subject, recipients, body, status, created_by,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["draft_id"],
                record["subject"],
                record.get("recipients"),
                record.get("body"),
                record["status"],
                record["created_by"],
                record["created_at"],
                record["updated_at"],
            ),
        )

    def list_email_drafts(self: SQLiteStore, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM email_drafts ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM email_drafts WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_email_draft(self: SQLiteStore, draft_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM email_drafts WHERE draft_id = ?", (draft_id,))
        return dict(row) if row else None

    def update_email_draft_status(self: SQLiteStore, draft_id: str, status: str, *, updated_at: str) -> bool:
        changed = self._execute(
            "UPDATE email_drafts SET status = ?, updated_at = ? WHERE draft_id = ?",
            (status, updated_at, draft_id),
        )
        return changed > 0
