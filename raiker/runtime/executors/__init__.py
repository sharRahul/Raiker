from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, Executor, not_implemented
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.runtime.executors.sandbox import SandboxError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore
from raiker.runtime.executors.channels import ChannelApprovalRelayExecutor, ExternalChannelExecutor
from raiker.runtime.executors.containers import ContainerExecutionExecutor
from raiker.runtime.executors.models_runtime import (
    HostedModelRuntimeExecutor,
    PrivateNetworkModelRuntimeExecutor,
)
from raiker.runtime.executors.orchestration import MultiAgentTeamExecutor, SubagentExecutor
from raiker.runtime.executors.scheduled import ScheduledRoutinesExecutor
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.runtime.executors.tier1_files import FileWriteExecutor, PatchApplyExecutor
from raiker.runtime.executors.tier1_memory import MemoryForgetExecutor, MemoryWriteExecutor
from raiker.runtime.executors.tier2_shell import ProcessExecutor, ShellExecutor
from raiker.runtime.executors.tier2_web import NetworkExecutor, WebFetchExecutor
from raiker.runtime.executors.tier3_core import (
    GraphIndexingExecutor,
    ModelProviderExecutor,
    SemanticMemoryExecutor,
    VectorEmbeddingExecutor,
)
from raiker.runtime.executors.tier4_plugins import PluginExecutionCapExecutor, PluginInstallExecutor
from raiker.runtime.executors.tier5_network import (
    CloudExecutionExecutor,
    RemoteExecutionExecutor,
)
from raiker.runtime.executors.tier6_domains import (
    CalendarRuntimeExecutor,
    CctvRuntimeExecutor,
    EmailRuntimeExecutor,
    FinanceRuntimeExecutor,
    HardwareOperatorRuntimeExecutor,
    HomeSecurityRuntimeExecutor,
    InvestmentRuntimeExecutor,
    MedicalRuntimeExecutor,
    PregnancyBabyRuntimeExecutor,
    ReminderRuntimeExecutor,
)

__all__ = [
    "Executor", "ExecutionResult", "ExecutorRegistry", "SandboxError", "not_implemented",
    "REAL_EXECUTOR_CAPABILITIES", "build_default_executor_registry",
    "ApprovalExecutionRelay", "FileWriteExecutor", "PatchApplyExecutor",
    "MemoryWriteExecutor", "MemoryForgetExecutor",
    "ShellExecutor", "ProcessExecutor", "WebFetchExecutor", "NetworkExecutor",
    "GraphIndexingExecutor", "SemanticMemoryExecutor", "VectorEmbeddingExecutor", "ModelProviderExecutor",
    "SubagentExecutor", "MultiAgentTeamExecutor",
    "PluginInstallExecutor", "PluginExecutionCapExecutor",
    "ExternalChannelExecutor", "ChannelApprovalRelayExecutor",
    "RemoteExecutionExecutor", "ContainerExecutionExecutor", "CloudExecutionExecutor",
    "HostedModelRuntimeExecutor", "PrivateNetworkModelRuntimeExecutor", "ScheduledRoutinesExecutor",
    "EmailRuntimeExecutor", "CalendarRuntimeExecutor", "ReminderRuntimeExecutor",
    "FinanceRuntimeExecutor", "InvestmentRuntimeExecutor", "MedicalRuntimeExecutor",
    "PregnancyBabyRuntimeExecutor", "CctvRuntimeExecutor", "HomeSecurityRuntimeExecutor",
    "HardwareOperatorRuntimeExecutor",
]


# ── Default executor registry ────────────────────────────────────────────────
#
# REAL_EXECUTOR_CAPABILITIES is the *only* set of capabilities whose executors
# perform genuine local work today. Every other capability either has no
# executor or a fail-closed one (`not_implemented`). Activation is gated on
# whether a capability has a registered executor (see
# raiker.runtime.authority.activation.has_executor), so a capability absent
# from this set cannot be flipped to a runtime-enabled state through the
# governed control plane.
#
# Sensitive/external domains (finance, medical, cctv, remote/cloud, plugin
# execution, …) are deliberately excluded until each has a real executor plus a
# per-domain threat model.

REAL_EXECUTOR_CAPABILITIES: frozenset[str] = frozenset({
    # Tier 1 — local, reversible
    "approval_execution_relay",
    "file_write_execution",
    "patch_apply_execution",
    "memory_write_execution",
    "memory_forget_execution",
    # Tier 2 — sandboxed local execution / allowlisted egress
    "shell_execution",
    "process_execution",
    "web_fetch",
    "network_execution",
    # Tier 3 — local code-intelligence runtime
    "graph_indexing_runtime",
    "semantic_memory_runtime",
    # Phase 4 — bounded, governed, in-process orchestration (no network / no spawn-out)
    "subagents",
    "multi_agent_teams",
    # Phase 4 — reference channel (bounded outbound webhook + metadata-only relay)
    "external_channel_runtime",
    "channel_approval_relay",
    # Phase 4 — local sandboxed container execution (no network, no host mounts)
    "container_execution_cap",
    # Phase 4 — local on-demand scheduled routines (no daemon)
    "scheduled_routines",
    # Phase 4 slice 7 — hosted / private-network model runtime (owner egress
    # allowlist, metadata-only connectivity probe; chat path re-checks the
    # same allowlist in the provider factory)
    "hosted_model_runtime",
    "private_network_model_runtime",
    # Tier 4 — local manifest validation + brokered read-only plugin tool
    # invocation. Arbitrary plugin code/import/process/network execution remains
    # out of scope.
    "plugin_install",
    "plugin_execution_cap",
})


def build_default_executor_registry(
    workspace_root: str | Path,
    store: SQLiteStore,
) -> ExecutorRegistry:
    """Build a registry containing only genuinely-implemented executors.

    The set registered here is exactly ``REAL_EXECUTOR_CAPABILITIES``. Anything
    not registered fails activation with ``activation_blocked:no_executor`` and,
    if reached at execution time, fails closed with
    ``execution_unavailable:no_executor``.
    """
    ws = Path(workspace_root)
    registry = ExecutorRegistry()
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("memory_write_execution", MemoryWriteExecutor(ws, store))
    registry.register("memory_forget_execution", MemoryForgetExecutor(ws))
    registry.register("shell_execution", ShellExecutor(ws))
    registry.register("process_execution", ProcessExecutor(ws))
    registry.register("web_fetch", WebFetchExecutor(ws))
    registry.register("network_execution", NetworkExecutor(ws))
    registry.register("graph_indexing_runtime", GraphIndexingExecutor(ws))
    registry.register("semantic_memory_runtime", SemanticMemoryExecutor(ws))
    registry.register("subagents", SubagentExecutor(ws, store))
    registry.register("multi_agent_teams", MultiAgentTeamExecutor(ws, store))
    registry.register("external_channel_runtime", ExternalChannelExecutor(ws, store))
    registry.register("channel_approval_relay", ChannelApprovalRelayExecutor(ws, store))
    registry.register("container_execution_cap", ContainerExecutionExecutor(ws))
    registry.register("scheduled_routines", ScheduledRoutinesExecutor(ws, store))
    registry.register("hosted_model_runtime", HostedModelRuntimeExecutor(ws))
    registry.register("private_network_model_runtime", PrivateNetworkModelRuntimeExecutor(ws))
    registry.register("plugin_install", PluginInstallExecutor(ws, store))
    registry.register("plugin_execution_cap", PluginExecutionCapExecutor(ws, store))
    assert registry.capabilities() == REAL_EXECUTOR_CAPABILITIES, (
        "default executor registry drifted from REAL_EXECUTOR_CAPABILITIES"
    )
    return registry
