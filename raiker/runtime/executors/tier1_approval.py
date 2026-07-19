from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.runtime.authority.models import Principal
from raiker.runtime.executors.base import ExecutionResult
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import resolve_workspace_path

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class ApprovalExecutionRelay:
    capability = "approval_execution_relay"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        approval_id = str(action.arguments.get("approval_id", ""))
        if not approval_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:approval_id",
                summary="Approval relay denied: no approval_id provided.",
            )

        approval = self._store.load_approval(approval_id)
        if approval is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_not_found",
                summary=f"Approval {approval_id} not found.",
            )
        if approval.get("status") != "pending":
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_already_resolved",
                summary=f"Approval {approval_id} already resolved.",
            )

        # TTL check first: an expired approval resolves to `expired` and never
        # executes. `expires_at` is stored in the same canonical UTC ISO-8601
        # format as `utc_now()`, so a lexicographic comparison is chronological.
        now = utc_now()
        expires_at = approval.get("expires_at")
        if expires_at is not None and str(expires_at) and now > str(expires_at):
            self._store.expire_approval(approval_id)
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_expired",
                summary=f"Approval {approval_id} expired at {expires_at}; not executed.",
            )

        # TOCTOU defense: the immutable intent hash was captured at approval
        # creation. Recompute it from the tool action as it stands now; if the
        # arguments (or tool/risk) drifted since approval, refuse — the human
        # approved a different action than the one about to run.
        stored_hash = approval.get("action_payload_sha256")
        if stored_hash is not None:
            current_hash = self._store.tool_action_payload_sha256(
                str(approval.get("tool_name", "")),
                str(approval.get("arguments_json", "{}")),
                str(approval.get("risk_level", "")),
            )
            if str(stored_hash) != current_hash:
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code="approval_payload_tampered",
                    summary=(
                        f"Approval {approval_id} arguments changed since approval; refused."
                    ),
                )

        arguments_json = str(approval.get("arguments_json", "{}"))
        try:
            tool_args: dict[str, Any] = json.loads(arguments_json)
        except json.JSONDecodeError:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="invalid_arguments_json",
                summary="Approval relay denied: invalid arguments JSON.",
            )

        self._store.resolve_approval(
            approval_id, status="approved", resolved_by=principal.principal_id,
            resolved_at=utc_now(),
        )

        path = str(tool_args.get("path", ""))
        text = str(tool_args.get("text", ""))
        if not path:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:path",
                summary="Approval relay denied: no file path in approved action.",
            )
        try:
            resolved = resolve_workspace_path(self._workspace_root, path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(text, encoding="utf-8")
            rel = str(resolved.relative_to(self._workspace_root))
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=f"Approval executed: wrote {resolved.stat().st_size} bytes to {rel}.",
                artifacts={
                    "approval_id": approval_id,
                    "path": rel,
                    "size_bytes": resolved.stat().st_size,
                },
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"execution_failed:{exc}",
                summary="Approval relay execution failed.",
            )