from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult
from raiker.tools.filesystem import (
    apply_patch_content,
    replace_text_content,
    resolve_writable_workspace_path,
)

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class FileWriteExecutor:
    capability = "file_write_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        path_value = action.arguments.get("path")
        path = str(path_value) if path_value else None
        if not path:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:path",
                summary="File write denied: no path provided.",
            )
        try:
            if action.action_type == "edit_file":
                result = replace_text_content(
                    self._workspace_root,
                    path,
                    str(action.arguments.get("old_text", "")),
                    str(action.arguments.get("new_text", "")),
                )
                if result["status"] != "success":
                    error = result["error"]
                    return ExecutionResult(
                        ok=False, capability=self.capability, action_id=action.action_id,
                        reason_code=f"edit_failed:{error['type']}",
                        summary="File edit rejected; the file was not changed.",
                        artifacts={"path": path, "error": error, "rejected_hunks": result.get("rejected_hunks")},
                    )
                return ExecutionResult(
                    ok=True, capability=self.capability, action_id=action.action_id,
                    summary=f"Edited {result['path']} ({result['size_bytes']} bytes).",
                    artifacts={"path": result["path"], "size_bytes": result["size_bytes"]},
                )
            text = str(action.arguments.get("text", ""))
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
        path_value = action.arguments.get("path")
        path = str(path_value) if path_value else None
        try:
            result = apply_patch_content(
                self._workspace_root, path, str(action.arguments.get("patch", ""))
            )
            if result["status"] != "success":
                error = result["error"]
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code=f"patch_failed:{error['type']}",
                    summary="Patch rejected; the file was not changed.",
                    artifacts={"path": path, "error": error, "rejected_hunks": result.get("rejected_hunks")},
                )
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=f"Applied one patch transaction to {len(result['paths'])} file(s).",
                artifacts={"path": result["path"], "paths": result["paths"], "changes": result["changes"], "size_bytes": result["size_bytes"]},
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"patch_failed:{exc}",
                summary="Patch apply failed.",
            )
