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
                # B9 — reading the repository code map. Read-shaped for the same
                # reason `connector_read` is: what governs it is enforced inside
                # the tool — the `code_map_indexing` capability gate and the
                # decision mode — and it returns coordinates into files the agent
                # may already open with `read_file`, so it adds no authority.
                "code_map_search",
                # Reading an installed skill is a local, owner-scoped read of
                # the owner's own instruction document. Nothing is executed.
                "skill_load",
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
                # Governed inside the tool (connector gate + decision mode +
                # owner credential + egress allowlist + manifest-driven
                # operation allowlist); the proposal is read-shaped.
                "connector_read",
                # B12/C7 — the agent's own web reads. Read-shaped here for the
                # same reason `connector_read` is: what governs them is enforced
                # inside the tool — the `web_fetch` capability gate, the decision
                # mode (default `ask` withholds), the owner egress allowlist, and
                # HTTPS-only, public-address, re-governed-redirect URL checks.
                #
                # `web_fetch` names a *tool* here and a *capability* in
                # `CAPABILITY_GATE_MAP`; the two vocabularies share the string on
                # purpose, because one gate governs both paths. It is deliberately
                # not also listed in `approval_required_actions` below: with the
                # same name in both sets the read branch would silently win, which
                # is the "two lists that have to agree" defect this codebase keeps
                # finding. The capability path is unchanged by that — `route_action`
                # gates it on the capability gate and on the decision mode, whose
                # default `ask` forces approval for any AI-proposed action.
                "web_fetch",
                "web_search",
                "create_document",
                "run_command",
                # B6 — recording the agent's plan writes one owner-scoped row of
                # the model's own intentions. It executes nothing, so it is
                # read-shaped here; every step it names is governed when it is
                # actually attempted.
                "update_plan",
                # B7 — spawning a bounded subagent. Read-shaped for the same
                # reason `connector_read` is: the subagent's steps are each
                # re-brokered through this engine, and its delegable tool set is
                # read-only with no egress, so the spawn adds no authority.
                "spawn_subagent",
                "user_create",
                "user_deactivate",
                "role_create",
                "role_grant",
                "role_revoke",
                "approval_execution_relay",
                "principal_create",
            }
        )
    )
    approval_required_actions: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "shell", "write_file", "edit_file", "apply_patch",
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
            "process", "network",
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
