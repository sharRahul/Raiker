from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, Executor, not_implemented
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.runtime.executors.sandbox import SandboxError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore
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
    ChannelApprovalRelayExecutor,
    CloudExecutionExecutor,
    ContainerExecutionExecutor,
    ExternalChannelExecutor,
    HostedModelExecutor,
    PrivateNetworkModelExecutor,
    RemoteExecutionExecutor,
    ScheduledRoutinesExecutor,
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
    "PluginInstallExecutor", "PluginExecutionCapExecutor",
    "ExternalChannelExecutor", "ChannelApprovalRelayExecutor",
    "RemoteExecutionExecutor", "ContainerExecutionExecutor", "CloudExecutionExecutor",
    "HostedModelExecutor", "PrivateNetworkModelExecutor", "ScheduledRoutinesExecutor",
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
# Sensitive/external domains (finance, medical, cctv, remote/container/cloud,
# channels, hosted models, plugins, …) are deliberately excluded until each has
# a real executor plus a per-domain threat model.

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
    assert registry.capabilities() == REAL_EXECUTOR_CAPABILITIES, (
        "default executor registry drifted from REAL_EXECUTOR_CAPABILITIES"
    )
    return registry