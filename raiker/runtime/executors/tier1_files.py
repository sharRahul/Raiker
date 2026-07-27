from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult
from raiker.tools.filesystem import resolve_writable_workspace_path

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class FileWriteExecutor:
    capability = "file_write_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        path = str(action.arguments.get("path", ""))
        text = str(action.arguments.get("text", ""))
        if not path:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:path",
                summary="File write denied: no path provided.",
            )
        try:
            resolved = resolve_writable_workspace_path(self._workspace_root, path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(text, encoding="utf-8")
            rel = str(resolved.relative_to(self._workspace_root))
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=f"Wrote {resolved.stat().st_size} bytes to {rel}.",
                artifacts={"path": rel, "size_bytes": resolved.stat().st_size},
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"write_failed:{exc}",
                summary="File write failed.",
            )


class PatchApplyExecutor:
    capability = "patch_apply_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        path = str(action.arguments.get("path", ""))
        new_text = str(action.arguments.get("new_text", ""))
        if not path:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:path",
                summary="Patch apply denied: no path provided.",
            )
        try:
            resolved = resolve_writable_workspace_path(self._workspace_root, path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(new_text, encoding="utf-8")
            rel = str(resolved.relative_to(self._workspace_root))
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=f"Applied patch to {rel} ({resolved.stat().st_size} bytes).",
                artifacts={"path": rel, "size_bytes": resolved.stat().st_size},
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"patch_failed:{exc}",
                summary="Patch apply failed.",
            )