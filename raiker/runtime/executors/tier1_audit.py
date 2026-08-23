"""BUG-231 — the audit log, taken out of the product.

Raiker keeps an append-only, account-scoped audit log and calls it evidence.
Evidence that cannot leave the product is evidence that cannot be used anywhere
it matters: a review, an incident write-up, a second tool. Everything needed to
produce one already existed — ``raiker.events.export.generate_export`` writes a
redacted JSONL beside the log and records a manifest — and ``audit_export`` was
a capability in ``ALL_CAPABILITIES`` with **no executor**, so it was one of the
capabilities that could not be activated at all.

Three properties this executor keeps, because they are what make an export
usable as evidence rather than a liability:

* **The same redaction the on-screen record passes.** ``redact=True`` is not a
  caller-supplied option here; the export path in :mod:`raiker.events.export`
  applies ``redact_event_payload`` to every payload it writes.
* **Scoped to the acting principal's own account.** The row filter is the
  principal's ``delegated_by_user_id`` with the user-visibility filter on, so an
  export can never widen who can read what.
* **Audited itself.** The action reaches this executor through
  ``route_action``, so the export is an event in the log it exported.

The manifest carries a content hash over the exact event ids and scope, which is
what lets a reader outside Raiker say whether the file they were handed is the
one the product produced.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore


class AuditExportExecutor:
    capability = "audit_export"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.events.export import generate_export

        session_id = str(action.arguments.get("session_id", "")).strip() or None
        project_id = str(action.arguments.get("project_id", "")).strip() or None
        # The account the export is scoped to is the acting principal's, never an
        # argument. A caller cannot name someone else's log.
        user_id = principal.delegated_by_user_id
        try:
            manifest = generate_export(
                self._store,
                session_id,
                project_id=project_id,
                user_id=user_id,
                apply_user_visibility_filter=user_id is not None,
                redact=True,
                exported_by=principal.principal_id,
            )
        except OSError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"audit_export_failed:{type(exc).__name__}",
                summary="Audit export failed: the export file could not be written.",
            )
        if manifest.event_count == 0:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="audit_export_empty",
                summary="Nothing to export: no audit events are in scope for this account.",
            )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=(
                f"Exported {manifest.event_count} audit events "
                f"({manifest.first_timestamp} → {manifest.last_timestamp}), redacted."
            ),
            artifacts={
                "export_id": manifest.export_id,
                "manifest_hash": manifest.manifest_hash,
                "event_count": manifest.event_count,
                "redacted": manifest.redacted,
                "first_event_id": manifest.first_event_id,
                "last_event_id": manifest.last_event_id,
                "export_path": manifest.export_path,
            },
        )
