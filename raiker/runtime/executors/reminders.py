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


class ReminderRuntimeExecutor:
    """Real, local-only executor for ``reminder_runtime``.

    Unlike the other Tier-6 domains (email, calendar, finance, medical, cctv,
    home security, hardware) — which need real external integrations before they
    can act and therefore stay fail-closed — a reminder is purely local state:
    creating or listing rows in the workspace ``reminders`` table. There is no
    network, no external side effect, and no device/hardware access, so this is a
    genuine local executor rather than a stub.

    Supported ``action`` argument values: ``create`` (default) and ``list``.
    Artifacts are metadata only (ids/counts), never reminder titles or notes, so
    reminder content is not emitted into runtime events.
    """

    capability = "reminder_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        op = action.arguments.get("action", "create")
        if op == "create":
            return self._create(action, principal)
        if op == "list":
            return self._list(action)
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
            },
        )

    def _list(self, action: GovernedAction) -> ExecutionResult:
        reminders = self._store.list_reminders(status="active")
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Listed active reminders; titles/notes are not included in runtime artifacts.",
            artifacts={
                "count": len(reminders),
                "reminder_ids": [str(r["reminder_id"]) for r in reminders],
                "content_redacted": True,
            },
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
