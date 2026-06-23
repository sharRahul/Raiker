from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class _NetworkExecutorBase:
    """Tier-5 outbound / remote executor.

    Channels, relay, remote/container/cloud execution, and hosted/private model
    runtimes require real external infrastructure, secret injection, egress
    allowlists, and budget controls. Until those land, they **fail closed**
    instead of fabricating success.
    """

    capability = ""

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)


class RemoteExecutionExecutor(_NetworkExecutorBase):
    capability = "remote_execution_cap"


class ContainerExecutionExecutor(_NetworkExecutorBase):
    capability = "container_execution_cap"


class CloudExecutionExecutor(_NetworkExecutorBase):
    capability = "cloud_execution_cap"


class HostedModelExecutor(_NetworkExecutorBase):
    capability = "hosted_model_runtime"


class PrivateNetworkModelExecutor(_NetworkExecutorBase):
    capability = "private_network_model_runtime"


class ScheduledRoutinesExecutor(_NetworkExecutorBase):
    capability = "scheduled_routines"
