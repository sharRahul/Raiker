from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class ExternalChannelExecutor:
    capability = "external_channel_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        channel = str(action.arguments.get("channel", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"External channel '{channel}' message routed.",
            artifacts={"channel": channel},
        )


class ChannelApprovalRelayExecutor:
    capability = "channel_approval_relay"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        channel = str(action.arguments.get("channel", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Approval relayed on channel '{channel}'.",
            artifacts={"channel": channel},
        )


class RemoteExecutionExecutor:
    capability = "remote_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        target = str(action.arguments.get("target", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Remote execution on '{target}' completed.",
            artifacts={"target": target},
        )


class ContainerExecutionExecutor:
    capability = "container_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        image = str(action.arguments.get("image", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Container execution with image '{image}' completed.",
            artifacts={"image": image},
        )


class CloudExecutionExecutor:
    capability = "cloud_execution_cap"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        provider = str(action.arguments.get("provider", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Cloud execution on '{provider}' completed.",
            artifacts={"provider": provider},
        )


class HostedModelExecutor:
    capability = "hosted_model_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        model = str(action.arguments.get("model", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Hosted model '{model}' request completed.",
            artifacts={"model": model},
        )


class PrivateNetworkModelExecutor:
    capability = "private_network_model_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        endpoint = str(action.arguments.get("endpoint", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Private network model call to '{endpoint}' completed.",
            artifacts={"endpoint": endpoint},
        )


class ScheduledRoutinesExecutor:
    capability = "scheduled_routines"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        routine_id = str(action.arguments.get("routine_id", ""))
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Scheduled routine '{routine_id}' executed.",
            artifacts={"routine_id": routine_id},
        )