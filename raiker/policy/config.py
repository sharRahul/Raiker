from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from raiker.contracts.models import OWNER_QUESTION_TOOL
from raiker.models.tool_registry import READ_SHAPED_TOOL_NAMES


@dataclass(frozen=True)
class StaticPolicyConfig:
    workspace_root: Path
    policy_id: str = "phase1-static"
    policy_version: str = "phase1-static-v1"
    #: What the policy engine treats as read-shaped.
    #:
    #: The tool half is derived: a tool declares `read_shaped` once, in
    #: `raiker.models.tool_registry`, rather than being remembered into this
    #: set as well. What stays written out here are the entries that are not
    #: tools at all — account and role administration, and the approval
    #: execution relay — which have no registry entry to derive from because
    #: no model ever proposes them.
    allowed_read_actions: frozenset[str] = field(
        default_factory=lambda: READ_SHAPED_TOOL_NAMES
        | frozenset(
            {
                "approval_execution_relay",
                "principal_create",
                "role_create",
                "role_grant",
                "role_revoke",
                "user_create",
                "user_deactivate",
            }
        )
    )
    approval_required_actions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "shell", "write_file", "edit_file", "apply_patch",
            # ADD-22 — a question parks the turn through the same transport an
            # approval uses, which is the only thing it borrows. It grants
            # nothing, so it carries no capability and stays in the `low` band;
            # what comes back is an answer, and the routes keep the two kinds
            # from ever resolving each other.
            OWNER_QUESTION_TOOL,
            # B11 — the git write path. A commit rewrites history a file
            # checkpoint does not cover and a pull request leaves the machine,
            # so both wait for the owner. `git_write_execution` is the
            # capability name the runtime authority routes on, listed for the
            # same reason `remote_execution_cap` is: a capability in neither set
            # is hard-denied on its way to the executor that carries it out.
            "git_branch", "git_commit", "git_write_execution", "github_write",
            # BUG-67 — the push, and the capability the runtime authority routes
            # it on. Listed for the same reason the pair above is: a capability
            # in neither set is hard-denied on its way to its own executor.
            "git_push", "git_push_execution",
            "memory_write", "memory_forget",
            # Checkpoint restore (Workstream B / B2) is itself a workspace
            # mutation — approval-required, routed through its own governed gate.
            "checkpoint_restore", "checkpoint_restore_execution",
            # BUG-231 — the redacted, account-scoped audit export.
            "audit_export",
            # Backlog #18 — the same record, over OTLP, to a collector the owner
            # named. Listed here for the same reason every other capability is:
            # one in neither set is hard-denied on its way to its own executor.
            "telemetry_export",
            "process",
            "graph_indexing", "semantic_memory", "vector_embedding", "model_provider",
            "plugin_install", "plugin_execution_cap", "plugin_revocation_cap",
            "plugin_runtime_cap", "plugin_sandboxed_runtime_cap", "plugin_sandbox_image_pull_cap",
            "external_channel_runtime", "channel_approval_relay",
            "remote_execution_cap", "container_execution_cap", "cloud_execution_cap",
            "hosted_model_runtime", "private_network_model_runtime", "advisor_model_runtime",
            "connector_github_runtime", "connector_gmail_runtime",
            "connector_gcal_runtime", "connector_slack_runtime",
            # A manifest-driven connector write (POST/PUT/PATCH/DELETE). The
            # broker stores an immutable intent and the approval resolution
            # path executes the exact approved operation once.
            "connector_write",
            "scheduled_routines",
            # Governed local stdio MCP builder + connector (Control Deck task 4).
            # Governed inside the tool (capability gate + decision mode +
            # interpreter allowlist + workspace-relative path); the executor
            # runs only after the governed path clears.
            "mcp_server_create", "mcp_connect", "mcp_list_tools", "mcp_call_tool",
            "subagents", "multi_agent_teams",
            # Found while implementing B6/B7: both tools were advertised to the
            # model and both were hard-denied here as `unknown_or_denied_tool`,
            # because neither name appeared in either set. They mutate owner
            # data, so they belong on the approval path they were built for.
            "create_task", "assign_session_project",
            # BUG-62 — and the capability names the runtime authority routes on,
            # for the same reason `remote_execution_cap` is listed below: the
            # relay re-governs the target, and a capability in neither set would
            # be hard-denied on its way to the executor that carries it out.
            "task_management_runtime", "project_assignment_runtime",
            # Same finding, same cause: the *tool names* the model proposes.
            # `remote_execution_cap` / `cloud_execution_cap` below are the
            # capability names the runtime authority routes on, which is a
            # different vocabulary — so a model-proposed `remote_execute` fell
            # through to `unknown_or_denied_tool` and never reached the approval
            # the broker already knew how to raise for it. The capability gate,
            # the owner profile, the credential reference and the cost ceiling
            # are all still in front of any actual execution.
            "remote_execute", "cloud_execute",
            "email_runtime", "calendar_runtime", "reminder_runtime",
            "finance_runtime", "investment_runtime", "medical_runtime",
            "pregnancy_baby_runtime", "cctv_runtime", "home_security_runtime",
            "hardware_operator_runtime",
        })
    )
    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())
        overlap = self.allowed_read_actions & self.approval_required_actions
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"policy actions cannot have conflicting verdicts: {names}")
