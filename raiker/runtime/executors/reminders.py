from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_TITLE_LEN = 500
_MAX_NOTES_LEN = 4000
_MAX_RETRIES = 10
_DELIVER_BATCH = 100


class ReminderRuntimeExecutor:
    """Real, local-only executor for ``reminder_runtime``.

    Supported ``action`` argument values: ``create`` (default), ``list``,
    ``deliver_due``, ``pause``, ``cancel``, and ``retry``.
    Artifacts are metadata only (ids/counts), never reminder titles or notes.
    """

    capability = "reminder_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        op = str(action.arguments.get("action", "create")).strip()
        if op == "create":
            return self._create(action, principal)
        if op == "list":
            return self._list(action)
        if op == "deliver_due":
            return self._deliver_due(action)
        if op == "pause":
            return self._pause(action)
        if op == "cancel":
            return self._cancel(action)
        if op == "retry":
            return self._retry(action)
        return self._failed(action.action_id, f"unknown_action:{op}")

    def _create(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        title = action.arguments.get("title")
        if not isinstance(title, str) or not title.strip():
            return self._failed(action.action_id, "missing_argument:title")
        if len(title) > _MAX_TITLE_LEN:
            return self._failed(action.action_id, "title_too_long")
        due_at = action.arguments.get("due_at")
        notes = action.arguments.get("notes")
        if due_at is not None and not isinstance(due_at, str):
            return self._failed(action.action_id, "invalid_argument:due_at")
        if notes is not None and (not isinstance(notes, str) or len(notes) > _MAX_NOTES_LEN):
            return self._failed(action.action_id, "invalid_argument:notes")
        max_retries = action.arguments.get("max_retries")
        if max_retries is not None:
            try:
                mr = int(max_retries)
            except (TypeError, ValueError):
                return self._failed(action.action_id, "invalid_argument:max_retries")
            if mr < 0 or mr > _MAX_RETRIES:
                return self._failed(action.action_id, f"max_retries_out_of_range:0-{_MAX_RETRIES}")
        else:
            mr = 3

        now = utc_now()
        reminder_id = new_id("rem_")
        self._store.insert_reminder({
            "reminder_id": reminder_id,
            "title": title.strip(),
            "due_at": due_at,
            "notes": notes,
            "status": "active",
            "created_by": principal.principal_id,
            "created_at": now,
            "updated_at": now,
        })
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Reminder recorded locally; no external notification was sent.",
            artifacts={
                "reminder_id": reminder_id,
                "status": "active",
                "has_due_at": due_at is not None,
                "max_retries": mr,
            },
        )

    def _list(self, action: GovernedAction) -> ExecutionResult:
        reminders = self._store.list_reminders()
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Listed reminders; titles/notes are not included in runtime artifacts.",
            artifacts={
                "count": len(reminders),
                "reminder_ids": [str(r["reminder_id"]) for r in reminders],
                "content_redacted": True,
            },
        )

    def _deliver_due(self, action: GovernedAction) -> ExecutionResult:
        due_before = str(action.arguments.get("due_before", utc_now()))
        reminders = self._store.list_due_reminders(due_before)[:_DELIVER_BATCH]
        now = utc_now()
        ok_all = True
        first_failure: str | None = None
        for rem in reminders:
            self._store.update_reminder_status(
                rem["reminder_id"], "delivered",
                delivery_status="delivered", delivered_at=now, updated_at=now,
            )
            r_ok, reason = True, None
            if not r_ok:
                ok_all = False
                first_failure = first_failure or reason
        return ExecutionResult(
            ok=ok_all,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=first_failure,
            summary=f"Delivered {len(reminders)} due reminder(s).",
            artifacts={"delivered_count": len(reminders)},
        )

    def _pause(self, action: GovernedAction) -> ExecutionResult:
        reminder_id = str(action.arguments.get("reminder_id", "")).strip()
        if not reminder_id:
            return self._failed(action.action_id, "missing_argument:reminder_id")
        ok = self._store.update_reminder_status(reminder_id, "paused", delivery_status="paused", updated_at=utc_now())
        if not ok:
            return self._failed(action.action_id, "reminder_not_found")
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Reminder paused.", artifacts={"reminder_id": reminder_id, "status": "paused"},
        )

    def _cancel(self, action: GovernedAction) -> ExecutionResult:
        reminder_id = str(action.arguments.get("reminder_id", "")).strip()
        if not reminder_id:
            return self._failed(action.action_id, "missing_argument:reminder_id")
        ok = self._store.update_reminder_status(reminder_id, "cancelled", delivery_status="cancelled", updated_at=utc_now())
        if not ok:
            return self._failed(action.action_id, "reminder_not_found")
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Reminder cancelled.", artifacts={"reminder_id": reminder_id, "status": "cancelled"},
        )

    def _retry(self, action: GovernedAction) -> ExecutionResult:
        reminder_id = str(action.arguments.get("reminder_id", "")).strip()
        if not reminder_id:
            return self._failed(action.action_id, "missing_argument:reminder_id")
        rem = self._store.list_reminders()
        match = [r for r in rem if r["reminder_id"] == reminder_id]
        if not match:
            return self._failed(action.action_id, "reminder_not_found")
        row = match[0]
        retry_count = int(row.get("retry_count", 0))
        max_retries_setting = int(row.get("max_retries", 3))
        if retry_count >= max_retries_setting:
            return self._failed(action.action_id, "max_retries_exceeded")
        now = utc_now()
        self._store.update_reminder_status(reminder_id, "active", delivery_status="active", retry_count=retry_count + 1, updated_at=now)
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Reminder reset for retry.", artifacts={"reminder_id": reminder_id, "retry_count": retry_count + 1},
        )

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Reminder runtime failed closed.",
            artifacts={},
        )
