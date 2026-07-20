from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult, Executor, not_implemented
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.runtime.executors.sandbox import SandboxError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore
from raiker.runtime.executors.channels import ChannelApprovalRelayExecutor, ExternalChannelExecutor
from raiker.runtime.executors.connectors import (
    GcalConnectorExecutor,
    GithubConnectorExecutor,
    GmailConnectorExecutor,
    SlackConnectorExecutor,
)
from raiker.runtime.executors.containers import ContainerExecutionExecutor
from raiker.runtime.executors.mcp import McpBuilderExecutor, McpConnectorExecutor
from raiker.runtime.executors.models_runtime import (
    AdvisorModelRuntimeExecutor,
    HostedModelRuntimeExecutor,
    ModelProviderExecutor,
    PrivateNetworkModelRuntimeExecutor,
)
from raiker.runtime.executors.orchestration import MultiAgentTeamExecutor, SubagentExecutor
from raiker.runtime.executors.reminders import ReminderRuntimeExecutor
from raiker.runtime.executors.scheduled import ScheduledRoutinesExecutor
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.runtime.executors.tier1_checkpoint import CheckpointRestoreExecutor
from raiker.runtime.executors.tier1_files import FileWriteExecutor, PatchApplyExecutor
from raiker.runtime.executors.tier1_memory import MemoryForgetExecutor, MemoryWriteExecutor
from raiker.runtime.executors.tier2_shell import ProcessExecutor, ShellExecutor
from raiker.runtime.executors.tier2_web import NetworkExecutor, WebFetchExecutor
from raiker.runtime.executors.tier3_core import (
    GraphIndexingExecutor,
    SemanticMemoryExecutor,
    VectorEmbeddingExecutor,
)
from raiker.runtime.executors.tier4_plugins import (
    PluginExecutionCapExecutor,
    PluginInstallExecutor,
    PluginRevocationExecutor,
    PluginRuntimeExecutor,
    PluginSandboxedRuntimeExecutor,
    PluginSandboxImagePullExecutor,
)
from raiker.runtime.executors.tier5_network import (
    CloudExecutionExecutor,
    RemoteExecutionExecutor,
)
from raiker.runtime.executors.tier6_domains import (
    CctvRuntimeExecutor,
    FinanceRuntimeExecutor,
    HardwareOperatorRuntimeExecutor,
    HomeSecurityRuntimeExecutor,
    InvestmentRuntimeExecutor,
    MedicalRuntimeExecutor,
    PregnancyBabyRuntimeExecutor,
)
from raiker.runtime.executors.tier6_local import (
    CalendarRuntimeExecutor,
    EmailRuntimeExecutor,
)

__all__ = [
    "Executor", "ExecutionResult", "ExecutorRegistry", "SandboxError", "not_implemented",
    "REAL_EXECUTOR_CAPABILITIES", "build_default_executor_registry",
    "ApprovalExecutionRelay", "CheckpointRestoreExecutor", "FileWriteExecutor", "PatchApplyExecutor",
    "MemoryWriteExecutor", "MemoryForgetExecutor",
    "ShellExecutor", "ProcessExecutor", "WebFetchExecutor", "NetworkExecutor",
    "GraphIndexingExecutor", "SemanticMemoryExecutor", "VectorEmbeddingExecutor", "ModelProviderExecutor",
    "SubagentExecutor", "MultiAgentTeamExecutor",
    "PluginInstallExecutor", "PluginExecutionCapExecutor", "PluginRevocationExecutor",
    "PluginRuntimeExecutor", "PluginSandboxedRuntimeExecutor", "PluginSandboxImagePullExecutor",
    "ExternalChannelExecutor", "ChannelApprovalRelayExecutor",
    "RemoteExecutionExecutor", "ContainerExecutionExecutor", "CloudExecutionExecutor",
    "HostedModelRuntimeExecutor", "PrivateNetworkModelRuntimeExecutor",
    "AdvisorModelRuntimeExecutor", "GithubConnectorExecutor", "GmailConnectorExecutor",
    "GcalConnectorExecutor", "SlackConnectorExecutor", "ScheduledRoutinesExecutor",
    "EmailRuntimeExecutor", "CalendarRuntimeExecutor", "ReminderRuntimeExecutor",
    "FinanceRuntimeExecutor", "InvestmentRuntimeExecutor", "MedicalRuntimeExecutor",
    "PregnancyBabyRuntimeExecutor", "CctvRuntimeExecutor", "HomeSecurityRuntimeExecutor",
    "HardwareOperatorRuntimeExecutor",
    "McpBuilderExecutor", "McpConnectorExecutor",
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
    # Workstream B — reversible checkpoint restore. Rewinds workspace files to a
    # checkpoint using B1 pre-image blobs; writes its own pre-image first, so a
    # restore is itself reversible. Approval-required governed mutation.
    "checkpoint_restore_execution",
    # Tier 2 — sandboxed local execution / allowlisted egress
    "shell_execution",
    "process_execution",
    "web_fetch",
    "network_execution",
    # Tier 3 — local code-intelligence runtime
    "graph_indexing_runtime",
    "semantic_memory_runtime",
    # Tier 3 — local deterministic embedding (hashing trick; no model download /
    # no network).
    "vector_embedding_runtime",
    # Tier 3 — provider-backed semantic embedding through an LLM provider; layered
    # egress + hosted/private gate + API-key gating (owner env creds only).
    "model_provider_runtime",
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
    # Control Deck task 4 — governed local stdio MCP builder + connector. The
    # builder writes a reviewed dependency-free stdio server template to a
    # workspace-relative path; the connector runs a bounded JSON-RPC stdio
    # session (initialize / tools/list / tools/call) against an owner-configured
    # local server whose interpreter is allowlisted and whose args are
    # workspace-relative. Redacted, metadata-only events. Remote transport,
    # OAuth discovery, and unreviewed-tool execution stay fail-closed.
    "mcp_builder_runtime",
    "mcp_connector_runtime",
    # Phase 4 slice 7 — hosted / private-network model runtime (owner egress
    # allowlist, metadata-only connectivity probe; chat path re-checks the
    # same allowlist in the provider factory)
    "hosted_model_runtime",
    "private_network_model_runtime",
    # Web-app task 2 — advisor model for local-model turns (default-ask consult
    # of the owner-picked advisor profile; provider policy — hosted/private gate,
    # owner egress allowlist, env-only key — re-checked per call).
    "advisor_model_runtime",
    # Web-app task 4 — GitHub read-only connector (reference slice). A model may
    # read a GitHub issue/PR through the brokered `github_read` tool; default-ask
    # decision mode withholds, the owner credential is env-only
    # (`RAIKER_GITHUB_TOKEN`), and `api.github.com` must be on the owner connector
    # egress allowlist. Reads only — send/modify actions are not implemented.
    "connector_github_runtime",
    # Web-app task 4 — Gmail read-only connector (second read connector). A model
    # may read a Gmail message/thread through the brokered `gmail_read` tool;
    # default-ask decision mode withholds, the owner credential is env-only
    # (`RAIKER_GMAIL_TOKEN`), and `gmail.googleapis.com` must be on the owner
    # connector egress allowlist. Reads only — send/modify are not implemented.
    "connector_gmail_runtime",
    # Web-app task 4 — Google Calendar + Slack read-only connectors (same pattern
    # as GitHub/Gmail). `gcal_read` reads an event/calendar (env `RAIKER_GCAL_TOKEN`,
    # host `www.googleapis.com`); `slack_read` reads a channel's info/history (env
    # `RAIKER_SLACK_TOKEN`, host `slack.com`). Default-ask withholds; reads only.
    "connector_gcal_runtime",
    "connector_slack_runtime",
    # Tier 4 — local manifest validation + brokered read-only plugin tool
    # invocation + revocation off-switch + bounded subprocess code runtime for an
    # owner-allowlisted installed plugin (slice 14) + network-isolated container
    # runtime (slice 16). In-process import isolation remains out of scope.
    "plugin_install",
    "plugin_execution_cap",
    "plugin_revocation_cap",
    "plugin_runtime_cap",
    "plugin_sandboxed_runtime_cap",
    "plugin_sandbox_image_pull_cap",
    # Tier 6 — local-only personal-data stores (no network / no external
    # integration): reminders, a local calendar (no external sync/invites), and
    # local email drafts (never sends). The remaining Tier-6 domains
    # (finance/investment/medical/pregnancy/cctv/home-security/hardware) stay
    # fail-closed until a real integration + threat model lands.
    "reminder_runtime",
    "calendar_runtime",
    "email_runtime",
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
    registry.register("checkpoint_restore_execution", CheckpointRestoreExecutor(ws, store))
    registry.register("memory_write_execution", MemoryWriteExecutor(ws, store))
    registry.register("memory_forget_execution", MemoryForgetExecutor(ws))
    registry.register("shell_execution", ShellExecutor(ws))
    registry.register("process_execution", ProcessExecutor(ws))
    registry.register("web_fetch", WebFetchExecutor(ws))
    registry.register("network_execution", NetworkExecutor(ws))
    registry.register("graph_indexing_runtime", GraphIndexingExecutor(ws))
    registry.register("semantic_memory_runtime", SemanticMemoryExecutor(ws))
    registry.register("vector_embedding_runtime", VectorEmbeddingExecutor(ws, store))
    registry.register("model_provider_runtime", ModelProviderExecutor(ws, store))
    registry.register("subagents", SubagentExecutor(ws, store))
    registry.register("multi_agent_teams", MultiAgentTeamExecutor(ws, store))
    registry.register("external_channel_runtime", ExternalChannelExecutor(ws, store))
    registry.register("channel_approval_relay", ChannelApprovalRelayExecutor(ws, store))
    registry.register("container_execution_cap", ContainerExecutionExecutor(ws))
    registry.register("scheduled_routines", ScheduledRoutinesExecutor(ws, store))
    registry.register("mcp_builder_runtime", McpBuilderExecutor(ws, store))
    registry.register("mcp_connector_runtime", McpConnectorExecutor(ws, store))
    registry.register("hosted_model_runtime", HostedModelRuntimeExecutor(ws))
    registry.register("private_network_model_runtime", PrivateNetworkModelRuntimeExecutor(ws))
    registry.register("advisor_model_runtime", AdvisorModelRuntimeExecutor(ws, store))
    registry.register("connector_github_runtime", GithubConnectorExecutor(ws, store))
    registry.register("connector_gmail_runtime", GmailConnectorExecutor(ws, store))
    registry.register("connector_gcal_runtime", GcalConnectorExecutor(ws, store))
    registry.register("connector_slack_runtime", SlackConnectorExecutor(ws, store))
    registry.register("plugin_install", PluginInstallExecutor(ws, store))
    registry.register("plugin_execution_cap", PluginExecutionCapExecutor(ws, store))
    registry.register("plugin_revocation_cap", PluginRevocationExecutor(ws, store))
    registry.register("plugin_runtime_cap", PluginRuntimeExecutor(ws, store))
    registry.register("plugin_sandboxed_runtime_cap", PluginSandboxedRuntimeExecutor(ws, store))
    registry.register("plugin_sandbox_image_pull_cap", PluginSandboxImagePullExecutor(ws))
    registry.register("reminder_runtime", ReminderRuntimeExecutor(ws, store))
    registry.register("calendar_runtime", CalendarRuntimeExecutor(ws, store))
    registry.register("email_runtime", EmailRuntimeExecutor(ws, store))
    assert registry.capabilities() == REAL_EXECUTOR_CAPABILITIES, (
        "default executor registry drifted from REAL_EXECUTOR_CAPABILITIES"
    )
    return registry
