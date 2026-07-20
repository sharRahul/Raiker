"""Workstream B / Slice B2 — checkpoint restore executor.

`checkpoint_restore` is an approval-required governed action (it is itself a
mutation). The executor recomputes the metadata-only restore plan from the B1
capture manifest at execution time (never trusting caller-supplied file lists),
then rewinds only the files recorded in that manifest — refusing any path
outside the workspace — and, crucially, captures its *own* pre-image of each
file before overwriting it, so a restore is itself reversible.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.checkpoints.service import (
    RESTORE_OP_CONTENT,
    RESTORE_OP_DELETE,
    CheckpointService,
)
from raiker.runtime.executors.base import ExecutionResult
from raiker.tools.filesystem import FilesystemSafetyError, resolve_workspace_path

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore


class CheckpointRestoreExecutor:
    capability = "checkpoint_restore_execution"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        checkpoint_id = str(action.arguments.get("checkpoint_id", ""))
        if not checkpoint_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:checkpoint_id",
                summary="Checkpoint restore denied: no checkpoint_id provided.",
            )

        service = CheckpointService(self._store)
        try:
            plan = service.compute_restore_plan(checkpoint_id)
        except ValueError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"restore_plan_failed:{exc}",
                summary="Checkpoint restore denied: checkpoint not found.",
            )

        capture = service.capture_service()
        files: list[dict[str, object]] = plan.get("files", [])  # type: ignore[assignment]
        restored = 0
        deleted = 0
        skipped = 0
        for entry in files:
            path = str(entry["workspace_path"])
            op = str(entry["op"])
            if op not in (RESTORE_OP_CONTENT, RESTORE_OP_DELETE) or not entry["changed"]:
                # Oversize (un-captured) files and already-matching files are no-ops.
                skipped += 1
                continue

            # Defense in depth: the manifest is workspace-scoped, but re-verify the
            # path resolves inside the workspace before touching the filesystem.
            try:
                resolved = resolve_workspace_path(self._workspace_root, path)
            except FilesystemSafetyError:
                skipped += 1
                continue

            # Write our own pre-image FIRST so the restore is reversible, tagging
            # it with this restore's action id (capability = checkpoint restore).
            pre = capture.snapshot_path(path, self.capability)
            if pre is not None:
                capture.commit(
                    pre,
                    session_id=action.session_id,
                    turn_id=action.turn_id,
                    action_id=action.action_id,
                    principal_id=principal.principal_id,
                )

            if op == RESTORE_OP_DELETE:
                if resolved.exists():
                    resolved.unlink()
                deleted += 1
                continue

            # RESTORE_OP_CONTENT: rewrite the file from its content-addressed blob.
            sha = entry["pre_image_sha256"]
            data = capture.read_blob(str(sha)) if sha else None
            if data is None:
                # The pre-image object is missing/tampered — fail this file closed
                # rather than restore corrupt content.
                skipped += 1
                continue
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_bytes(data)
            restored += 1

        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=(
                f"Restored checkpoint {checkpoint_id}: "
                f"{restored} rewritten, {deleted} deleted, {skipped} skipped."
            ),
            artifacts={
                "checkpoint_id": checkpoint_id,
                "restored": restored,
                "deleted": deleted,
                "skipped": skipped,
            },
        )
