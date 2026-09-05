from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult, Executor, not_implemented
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.runtime.executors.sandbox import SandboxError

if TYPE_CHECKING:
    from raiker.runtime.executors.orchestration import MultiAgentTeamExecutor, SubagentExecutor
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
from raiker.runtime.executors.reminders import ReminderRuntimeExecutor
from raiker.runtime.executors.scheduled import ScheduledRoutinesExecutor
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.runtime.executors.tier1_audit import AuditExportExecutor
from raiker.runtime.executors.tier1_checkpoint import CheckpointRestoreExecutor
from raiker.runtime.executors.tier1_files import FileWriteExecutor, PatchApplyExecutor
from raiker.runtime.executors.tier1_git import GitPushExecutor, GitWriteExecutor
from raiker.runtime.executors.tier1_memory import MemoryForgetExecutor, MemoryWriteExecutor
from raiker.runtime.executors.tier1_tasks import (
    ProjectAssignmentExecutor,
    TaskManagementExecutor,
)
from raiker.runtime.executors.tier2_image import ImageGenerationExecutor
from raiker.runtime.executors.tier2_shell import ProcessExecutor, ShellExecutor
from raiker.runtime.executors.tier2_telemetry import TelemetryExportExecutor
from raiker.runtime.executors.tier2_web import WebFetchExecutor
from raiker.runtime.executors.tier3_core import (
    CodeMapIndexExecutor,
    GraphIndexingExecutor,
    LanguageIntelligenceExecutor,
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
    "ApprovalExecutionRelay", "AuditExportExecutor", "CheckpointRestoreExecutor",
    "FileWriteExecutor", "PatchApplyExecutor",
    "GitWriteExecutor", "GitPushExecutor",
    "MemoryWriteExecutor", "MemoryForgetExecutor",
    "TaskManagementExecutor", "ProjectAssignmentExecutor",
    "ShellExecutor", "ProcessExecutor", "WebFetchExecutor", "TelemetryExportExecutor",
    "ImageGenerationExecutor",
    "GraphIndexingExecutor", "CodeMapIndexExecutor", "LanguageIntelligenceExecutor",
    "SemanticMemoryExecutor", "VectorEmbeddingExecutor", "ModelProviderExecutor",
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


def __getattr__(name: str) -> object:
    """Load broker-dependent orchestration exports without creating an import cycle."""
    if name in {"SubagentExecutor", "MultiAgentTeamExecutor"}:
        from raiker.runtime.executors import orchestration

        return getattr(orchestration, name)
    raise AttributeError(name)


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
    # B11 — a governed branch or commit in the workspace repository. Local, and
    # bounded by the same workspace confinement the file caps use; repository
    # hooks are disabled for the invocation so an approved commit cannot run
    # workspace code the agent may itself have written.
    "git_write_execution",
    "memory_write_execution",
    "memory_forget_execution",
    # Workstream B — reversible checkpoint restore. Rewinds workspace files to a
    # checkpoint using B1 pre-image blobs; writes its own pre-image first, so a
    # restore is itself reversible. Approval-required governed mutation.
    "checkpoint_restore_execution",
    # BUG-231 — the audit log, taken out of the product. A redacted, account-
    # scoped export of the owner's own record, written locally; it reaches no
    # network and grants nothing. Evidence that cannot leave is not evidence.
    "audit_export",
    # Backlog #18 — the same governed record, over OTLP, to a collector the
    # owner named. Its own capability rather than a corner of `audit_export`,
    # because it differs in the one way that matters: it leaves the machine.
    "telemetry_export",
    # BUG-62 — the two local planning mutations an approval carries out. A task
    # row and a project label are owner-scoped, reversible, and never leave the
    # machine, so approving one performs it rather than recording it.
    "task_management_runtime",
    "project_assignment_runtime",
    # Tier 2 — sandboxed local execution / allowlisted egress
    "shell_execution",
    "process_execution",
    "web_fetch",
    # BUG-67 — the governed push. Egress like the four above it, bounded by the
    # owner's connector egress allowlist and the owner's own credential; it never
    # forces and never deletes a ref.
    "git_push_execution",
    # The Design surface. Egress on the same terms as any other model call: the
    # model egress allowlist, the owner's saved provider credential, and an
    # endpoint built from the configured profile rather than from the request.
    "image_generation",
    # Tier 3 — local code-intelligence runtime
    "graph_indexing_runtime",
    # B9 — the repository code map. A local, read-derived symbol index the owner
    # switches on; it executes nothing outside the workspace and grants nothing.
    "code_map_indexing",
    # B10 — the three language reads beside it. They write nothing at all, not
    # even a derived index, and every answer is a parse of a file the agent may
    # already open with `read_file`.
    "language_intelligence",
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
    "remote_execution_cap",
    "cloud_execution_cap",
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
    *,
    authority: Any = None,
) -> ExecutorRegistry:
    """Build a registry containing only genuinely-implemented executors.

    ``authority`` carries the roots the turn's project may touch, and reaches
    the executors that resolve a filesystem path. Omitted, each builds a
    workspace-only authority, so a registry without one confines exactly as it
    did before attached roots existed.

    The set registered here is exactly ``REAL_EXECUTOR_CAPABILITIES``. Anything
    not registered fails activation with ``activation_blocked:no_executor`` and,
    if reached at execution time, fails closed with
    ``execution_unavailable:no_executor``.
    """
    ws = Path(workspace_root)
    # Orchestration imports the broker. Keep it out of package initialisation so
    # the broker's container executor can itself import this package cleanly.
    from raiker.runtime.executors.orchestration import MultiAgentTeamExecutor, SubagentExecutor

    registry = ExecutorRegistry()
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    registry.register("file_write_execution", FileWriteExecutor(ws, authority=authority))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws, authority=authority))
    registry.register("git_write_execution", GitWriteExecutor(ws, store))
    registry.register("git_push_execution", GitPushExecutor(ws, store))
    registry.register("checkpoint_restore_execution", CheckpointRestoreExecutor(ws, store))
    registry.register("audit_export", AuditExportExecutor(ws, store))
    registry.register("memory_write_execution", MemoryWriteExecutor(ws, store))
    registry.register("memory_forget_execution", MemoryForgetExecutor(ws))
    registry.register("task_management_runtime", TaskManagementExecutor(ws, store))
    registry.register("project_assignment_runtime", ProjectAssignmentExecutor(ws, store))
    registry.register("shell_execution", ShellExecutor(ws))
    registry.register("process_execution", ProcessExecutor(ws))
    registry.register("web_fetch", WebFetchExecutor(ws, store))
    registry.register("telemetry_export", TelemetryExportExecutor(ws, store))
    registry.register("image_generation", ImageGenerationExecutor(ws, store))
    registry.register("graph_indexing_runtime", GraphIndexingExecutor(ws))
    registry.register("code_map_indexing", CodeMapIndexExecutor(ws, store))
    registry.register("language_intelligence", LanguageIntelligenceExecutor(ws, store))
    registry.register("semantic_memory_runtime", SemanticMemoryExecutor(ws))
    registry.register("vector_embedding_runtime", VectorEmbeddingExecutor(ws, store))
    registry.register("model_provider_runtime", ModelProviderExecutor(ws, store))
    registry.register("subagents", SubagentExecutor(ws, store))
    registry.register("multi_agent_teams", MultiAgentTeamExecutor(ws, store))
    registry.register("external_channel_runtime", ExternalChannelExecutor(ws, store))
    registry.register("channel_approval_relay", ChannelApprovalRelayExecutor(ws, store))
    registry.register("container_execution_cap", ContainerExecutionExecutor(ws))
    registry.register("remote_execution_cap", RemoteExecutionExecutor(ws, store))
    registry.register("cloud_execution_cap", CloudExecutionExecutor(ws, store))
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
