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
_MAX_BODY_LEN = 20000


class CalendarRuntimeExecutor:
    """Real, local-only executor for ``calendar_runtime``.

    Creates or lists rows in the workspace ``calendar_events`` table. It is a
    **local calendar**: no external calendar (Google/Microsoft/CalDAV) sync, no
    invites, and no notifications. Those require a real integration + egress
    allowlist and stay out of scope. Actions: ``create`` (default), ``list``.
    Artifacts are metadata only (ids/counts) — titles/notes/locations never enter
    runtime events.
    """

    capability = "calendar_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        op = action.arguments.get("action", "create")
        if op == "create":
            return self._create(action, principal)
        if op == "list":
            reminders = self._store.list_calendar_events(status="scheduled")
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary="Listed scheduled calendar events; details are not included in runtime artifacts.",
                artifacts={
                    "count": len(reminders),
                    "event_ids": [str(r["event_id"]) for r in reminders],
                    "content_redacted": True,
                },
            )
        return self._failed(action.action_id, f"unknown_action:{op}")

    def _create(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        title = action.arguments.get("title")
        if not isinstance(title, str) or not title.strip():
            return self._failed(action.action_id, "missing_argument:title")
        if len(title) > _MAX_TITLE_LEN:
            return self._failed(action.action_id, "title_too_long")
        for key in ("starts_at", "ends_at", "location", "notes"):
            val = action.arguments.get(key)
            if val is not None and not isinstance(val, str):
                return self._failed(action.action_id, f"invalid_argument:{key}")
        now = utc_now()
        event_id = new_id("cal_")
        self._store.insert_calendar_event({
            "event_id": event_id,
            "title": title.strip(),
            "starts_at": action.arguments.get("starts_at"),
            "ends_at": action.arguments.get("ends_at"),
            "location": action.arguments.get("location"),
            "notes": action.arguments.get("notes"),
            "status": "scheduled",
            "created_by": principal.principal_id,
            "created_at": now,
            "updated_at": now,
        })
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Calendar event recorded locally; no external calendar was synced and no invite was sent.",
            artifacts={
                "event_id": event_id,
                "status": "scheduled",
                "has_start": action.arguments.get("starts_at") is not None,
            },
        )

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action_id,
            reason_code=reason_code, summary="Calendar runtime failed closed.", artifacts={},
        )


class EmailRuntimeExecutor:
    """Real, local-only executor for ``email_runtime``.

    Composes/lists drafts in the workspace ``email_drafts`` table and lets a
    human *queue* a draft to be sent. It **never transmits email itself** — there
    is no SMTP/provider call — because delivery is an outbound-network action
    that needs a connector + owner egress allowlist + its own threat model.

    Actions:

    - ``draft`` (default) / ``list`` — local draft state.
    - ``send`` — does **not** deliver; it marks a draft ``queued_for_send`` so a
      human can send it (from their own mail client, or via a future governed
      connector). Because ``email_runtime`` defaults to the ``ask`` decision
      mode, an AI-proposed ``send`` first asks the human for approval — so the
      two paths are "Raiker asks before queuing a send" and "the human sends it
      when they want". No message leaves the machine here.

    Artifacts are metadata only — subject/recipients/body never enter events.
    """

    capability = "email_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        op = action.arguments.get("action", "draft")
        if op == "draft":
            return self._draft(action, principal)
        if op == "list":
            drafts = self._store.list_email_drafts(status="draft")
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary="Listed local email drafts; contents are not included in runtime artifacts.",
                artifacts={
                    "count": len(drafts),
                    "draft_ids": [str(r["draft_id"]) for r in drafts],
                    "content_redacted": True,
                },
            )
        if op == "send":
            return self._queue_send(action)
        return self._failed(action.action_id, f"unknown_action:{op}")

    def _queue_send(self, action: GovernedAction) -> ExecutionResult:
        draft_id = action.arguments.get("draft_id")
        if not isinstance(draft_id, str) or not draft_id.strip():
            return self._failed(action.action_id, "missing_argument:draft_id")
        draft = self._store.get_email_draft(draft_id)
        if draft is None:
            return self._failed(action.action_id, "draft_not_found")
        if draft.get("status") == "queued_for_send":
            return self._failed(action.action_id, "already_queued")
        updated = self._store.update_email_draft_status(
            draft_id, "queued_for_send", updated_at=utc_now()
        )
        if not updated:
            return self._failed(action.action_id, "draft_not_found")
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=(
                "Draft queued for sending. Raiker did not transmit anything — email delivery "
                "requires a mail connector (not yet integrated); a human sends the queued draft."
            ),
            artifacts={
                "draft_id": draft_id,
                "status": "queued_for_send",
                "transmitted": False,
            },
        )

    def _draft(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        subject = action.arguments.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            return self._failed(action.action_id, "missing_argument:subject")
        if len(subject) > _MAX_TITLE_LEN:
            return self._failed(action.action_id, "subject_too_long")
        body = action.arguments.get("body")
        recipients = action.arguments.get("recipients")
        if body is not None and (not isinstance(body, str) or len(body) > _MAX_BODY_LEN):
            return self._failed(action.action_id, "invalid_argument:body")
        if recipients is not None and not isinstance(recipients, str):
            return self._failed(action.action_id, "invalid_argument:recipients")
        now = utc_now()
        draft_id = new_id("eml_")
        self._store.insert_email_draft({
            "draft_id": draft_id,
            "subject": subject.strip(),
            "recipients": recipients,
            "body": body,
            "status": "draft",
            "created_by": principal.principal_id,
            "created_at": now,
            "updated_at": now,
        })
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Email draft saved locally; nothing was sent.",
            artifacts={
                "draft_id": draft_id,
                "status": "draft",
                "has_recipients": recipients is not None,
            },
        )

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action_id,
            reason_code=reason_code, summary="Email runtime failed closed.", artifacts={},
        )
