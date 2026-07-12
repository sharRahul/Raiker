from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StaticPolicyConfig:
    workspace_root: Path
    policy_id: str = "phase1-static"
    policy_version: str = "phase1-static-v1"
    allowed_read_actions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "read_file",
                "list_directory",
                "glob",
                "grep",
                "stat_path",
                "diff_files",
                "git_status",
                "git_diff",
                "git_log",
                "memory_search",
                "memory_list",
                "memory_get",
                "vector_get",
                # The consult itself is gated inside the tool (advisor gate +
                # decision mode + provider policy); the proposal is read-shaped.
                "consult_advisor",
                # Governed inside the tool (connector gate + decision mode +
                # owner credential + egress allowlist); the proposal is read-shaped.
                "github_read",
                "gmail_read",
                "gcal_read",
                "slack_read",
                "user_create",
                "user_deactivate",
                "role_create",
                "role_grant",
                "role_revoke",
                "approval_execution_relay",
            }
        )
    )
    approval_required_actions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "shell", "write_file", "edit_file", "apply_patch",
            "memory_write", "memory_forget",
            "process", "network", "web_fetch",
            "graph_indexing", "semantic_memory", "vector_embedding", "model_provider",
            "plugin_install", "plugin_execution_cap", "plugin_revocation_cap",
            "plugin_runtime_cap", "plugin_sandboxed_runtime_cap",
            "external_channel_runtime", "channel_approval_relay",
            "remote_execution_cap", "container_execution_cap", "cloud_execution_cap",
            "hosted_model_runtime", "private_network_model_runtime", "advisor_model_runtime",
            "connector_github_runtime", "connector_gmail_runtime",
            "connector_gcal_runtime", "connector_slack_runtime",
            "scheduled_routines",
            "subagents", "multi_agent_teams",
            "email_runtime", "calendar_runtime", "reminder_runtime",
            "finance_runtime", "investment_runtime", "medical_runtime",
            "pregnancy_baby_runtime", "cctv_runtime", "home_security_runtime",
            "hardware_operator_runtime",
        })
    )
    denied_actions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "write_file",
                "edit_file",
                "delete_file",
                "network_request",
                "web_fetch",
                "plugin_execute",
                "remote_execute",
                "process",
                "network",
            }
        )
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())
