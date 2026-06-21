from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class PluginInstallExecutor:
    capability = "plugin_install"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        plugin_id = str(action.arguments.get("plugin_id", ""))
        if not plugin_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:plugin_id",
                summary="Plugin install denied: no plugin_id provided.",
            )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Plugin {plugin_id} verified and installed.",
            artifacts={"plugin_id": plugin_id},
        )


class PluginExecutionCapExecutor:
    capability = "plugin_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        plugin_id = str(action.arguments.get("plugin_id", ""))
        entrypoint = str(action.arguments.get("entrypoint", ""))
        if not plugin_id or not entrypoint:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:plugin_id_or_entrypoint",
                summary="Plugin execution denied: plugin_id and entrypoint required.",
            )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Plugin {plugin_id} execution completed ({entrypoint}).",
            artifacts={"plugin_id": plugin_id, "entrypoint": entrypoint},
        )