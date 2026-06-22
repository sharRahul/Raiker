from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class PluginInstallExecutor:
    """Plugin install. Sandboxing, signature/checksum verification, and a
    permission-diff approval flow are not implemented yet, so this fails closed
    rather than claiming an unverified plugin was installed."""

    capability = "plugin_install"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)


class PluginExecutionCapExecutor:
    """Plugin code execution. Requires sandbox isolation + revocation before it
    can run untrusted plugin code; fails closed until then."""

    capability = "plugin_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)