from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class _NetworkExecutorBase:
    """Tier-5 remote/cloud executor — deliberately fail-closed.

    Remote (SSH), cloud-provider, and hosted/private-network model execution
    require real external infrastructure, secret injection, egress allowlists,
    and budget controls, each with its own threat model. Per the sandboxed-first
    Phase 4 decision they stay fail-closed (no executor) until an explicit
    per-integration opt-in lands; see docs/threat-models/remote-cloud.md.
    """

    capability = ""

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        return not_implemented(self.capability, action.action_id)


class RemoteExecutionExecutor(_NetworkExecutorBase):
    capability = "remote_execution_cap"


class CloudExecutionExecutor(_NetworkExecutorBase):
    capability = "cloud_execution_cap"


# hosted_model_runtime / private_network_model_runtime were promoted to real
# executors in Phase 4 slice 7 — see raiker/runtime/executors/models_runtime.py
# and docs/threat-models/hosted-models.md. Remote/cloud execution above stays
# fail-closed per docs/threat-models/remote-cloud.md.
