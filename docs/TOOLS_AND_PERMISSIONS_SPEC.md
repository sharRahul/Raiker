# Tools And Permissions Specification

This document defines Raiker's tool system, permission model, approval modes, and safety requirements.

The tool broker is the only path to agent-controlled actions. Runtime code, clients, plugins, hooks, models, and subagents must not execute tools directly.

---

## Tool Broker Responsibilities

The broker must receive `ToolAction` proposals, validate tool name and arguments, normalise paths and arguments, classify risk, request policy decision, request user approval when required, execute only allowed actions, apply timeout/output/cancellation limits, redact secrets from logs, emit lifecycle events, and return structured `ToolResult` objects.

---

## Tool Lifecycle

```text
model/runtime proposes ToolAction
  -> action_proposed event
  -> argument validation
  -> risk classification
  -> policy review
  -> policy_decision event
  -> approval_requested event if needed
  -> approval_received or approval_denied
  -> tool_started event if allowed
  -> tool_completed or tool_failed event
  -> result passed to verifier/runtime
```

A tool must never execute before `policy_decision` exists.

---

## Permission Decision Values

| Decision | Meaning | First build phase |
|---|---|---:|
| `allow` | Execute immediately. | Phase 1 |
| `deny` | Do not execute. Return denied result. | Phase 1 |
| `needs_approval` | Pause and request approval. | Phase 1 |
| `defer` | Put action into deferred queue. | Phase 2 |
| `allow_once` | Allow one exact action ID only. | Phase 2 |
| `allow_for_session` | Allow matching action pattern for current session. | Phase 2 |
| `allow_for_project` | Allow matching action pattern for current project config. | Phase 2 |
| `allow_managed` | Allow by administrator/managed policy. | Phase 5 |

Phase 1 implements `allow`, `deny`, and `needs_approval`; later build phases add the remaining decision values without changing the base contract.

---

## Permission Scopes

| Scope | File/location | Shareable | Priority | First build phase |
|---|---|---:|---:|---:|
| managed | enterprise/admin policy | yes | highest | Phase 5 |
| user | user config | no | high | Phase 2 |
| project | committed project config | yes | medium | Phase 2 |
| local | gitignored local project config | no | medium-high | Phase 2 |
| plugin | plugin manifest and settings | yes | lower than explicit policy | Phase 3 |
| session | runtime approval | no | temporary | Phase 1 |
| action | exact action approval | no | one-shot | Phase 1 |

Conflict rule:

```text
explicit deny > managed policy > session/action approval > project/user allow > plugin suggestion > default policy
```

---

## Permission Rule Schema

```json
{
  "schema_version": "1.0",
  "rule_id": "perm_002",
  "scope": "project",
  "effect": "allow",
  "tool": "python_exec",
  "argument_match": {
    "workspace_only": true
  },
  "conditions": {
    "environment": "dev",
    "session_type": "interactive",
    "max_latency_ms": 30000,
    "max_cost": 0.10,
    "max_reasoning_effort": "medium",
    "requires_snapshot": false,
    "requires_dlp_check": true,
    "requires_audit_log": true,
    "allow_external_data_movement": false
  },
  "expires_at": null,
  "reason": "Allow bounded Python execution in interactive development sessions."
}
```

Rules must support exact tool names, wildcard tool groups, path glob patterns, command prefix patterns, network host allowlists, max output size, timeout, workspace-only restriction, expiry, and reason string.

Permission rule conditions should additionally support:

- `user_role`
- `session_type`
- `environment`
- `time_window`
- `max_cost`
- `max_latency_ms`
- `max_reasoning_effort`
- `requires_snapshot`
- `requires_dlp_check`
- `requires_audit_log`
- `allow_external_data_movement`

These conditions allow policies to adapt based on user role, runtime context, environment, cost, latency, data movement, and safety requirements.

---

## Approval Request Schema

```json
{
  "schema_version": "1.0",
  "approval_id": "appr_01H...",
  "action_id": "act_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "tool_name": "shell",
  "arguments_preview": {
    "command": "pytest tests/test_policy_engine.py"
  },
  "risk_level": "high",
  "policy_reasons": [
    "shell_requires_approval"
  ],
  "expected_effect": "Runs tests in the current workspace.",
  "confidence_score": 0.86,
  "uncertainty_flags": [
    "command_has_workspace_side_effects"
  ],
  "safe_alternatives": [
    "Run read-only diagnostics first",
    "Run a narrower test file"
  ],
  "rollback_available": false,
  "snapshot_id": null,
  "estimated_cost": null,
  "estimated_latency": "medium",
  "data_classification": "workspace_internal",
  "external_data_movement": false,
  "choices": [
    "approve_once",
    "approve_session",
    "deny",
    "defer"
  ],
  "expires_at": null
}
```

Approvals must be bound to exact `action_id`. Reusing approval for a changed command is forbidden.

Approval requests should additionally support the following optional metadata:

- `confidence_score`
- `uncertainty_flags`
- `safe_alternatives`
- `rollback_available`
- `snapshot_id`
- `estimated_cost`
- `estimated_latency`
- `data_classification`
- `external_data_movement`

These fields help users make informed approval decisions. Approval metadata must be descriptive and user-safe, but must not reveal private chain-of-thought or confidential policy internals.

---

## Tool Catalogue

This section defines the core Raiker tool families. The expanded phase-by-phase Raiker-native inventory is maintained in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](RAIKER_TOOL_AND_PLUGIN_CATALOG.md). Future builders must update both this canonical permission spec and that catalog when adding, renaming, activating, or removing a tool.

### Filesystem Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `read_file` | Read text file inside workspace | allow if inside workspace | Phase 1 |
| `write_file` | Create or replace file | needs approval | Phase 2 |
| `edit_file` | Patch or edit existing file | needs approval | Phase 2 |
| `delete_file` | Delete file | deny by default, scoped approval only | Phase 2 |
| `list_directory` | List entries | allow inside workspace | Phase 1 |
| `stat_path` | Get metadata | allow inside workspace | Phase 2 |
| `copy_path` | Copy file/dir | needs approval | Phase 2 |
| `move_path` | Rename/move | needs approval | Phase 2 |
| `diff_files` | Compare files | allow inside workspace | Phase 2 |
| `apply_patch` | Apply unified patch | needs approval and snapshot | Phase 2 |
| `notebook_edit` | Modify notebook cells without treating the notebook as plain text | needs approval and notebook validation | Phase 3 |

### Search Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `glob` | Find files by pattern | allow inside workspace | Phase 1 |
| `grep` | Search text | allow inside workspace | Phase 1 |
| `semantic_search` | Vector search | sensitivity-filtered | Phase 3 |
| `symbol_search` | LSP/code symbols | workspace scoped | Phase 3 |
| `graph_query` | Query code graph | workspace/project scoped | Phase 3 |
| `web_search` | Search internet | disabled until egress policy enabled | Phase 3 |
| `web_fetch` | Fetch URL | disabled until egress policy enabled | Phase 3 |

### Code Intelligence Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `lsp_diagnostics` | Read language-server diagnostics | allow only after workspace/plugin trust | Phase 3 |
| `lsp_definition` | Resolve symbol definition | read-only, workspace scoped | Phase 3 |
| `lsp_references` | Find references | read-only, workspace scoped | Phase 3 |
| `lsp_type_info` | Read type information | read-only, workspace scoped | Phase 3 |
| `lsp_call_hierarchy` | Trace call hierarchy | read-only, bounded output | Phase 3 |

### Execution Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `shell` | Run local command | needs approval | Phase 1 |
| `powershell` | Run PowerShell command | needs approval | Phase 2 |
| `python_exec` | Run isolated Python snippet | needs approval | Phase 2 |
| `git` | Git operation wrapper | scoped policy by subcommand | Phase 2 |
| `monitor` | Watch background command/log/status stream and emit events | disabled until background lifecycle policy exists | Phase 4 |
| `docker` | Container command wrapper | disabled until execution profile configured | Phase 4 |
| `ssh` | Remote command | disabled until execution profile configured | Phase 4 |
| `modal_job` | Cloud/GPU job | disabled until budget and egress policy configured | Phase 5 |

### Agent and Task Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `ask_user` | Ask clarification | allow | Phase 1 |
| `side_question` | Ask non-blocking clarification while work continues | allow with task binding | Phase 2 |
| `enter_plan_mode` | Switch to planning-only mode | allow, no execution | Phase 2 |
| `exit_plan_mode` | Present plan for approval | approval required for risky plan | Phase 2 |
| `spawn_subagent` | Start subagent | needs approval until configured | Phase 4 |
| `send_agent_message` | Send or resume message to subagent/team member | needs approval and parent/child event linkage | Phase 4 |
| `create_task` | Create background task metadata | needs approval for long-running work | Phase 2 |
| `get_task` | Retrieve one task | allow for task owner | Phase 2 |
| `list_tasks` | List tasks | allow for workspace/session scope | Phase 2 |
| `update_task` | Update task state/details/dependencies | allow for task owner, event logged | Phase 2 |
| `cancel_task` | Cancel background task | allow for task owner | Phase 2 |
| `handoff_task` | Delegate to other agent/channel | needs approval | Phase 4 |
| `workflow_run` | Run coordinated multi-agent workflow | disabled until team/budget/audit controls exist | Phase 4 to Phase 5 |

### Automation and Notification Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `schedule_create` | Create one-shot or recurring local scheduled task/prompt | needs approval for recurrence | Phase 3 |
| `schedule_list` | List scheduled tasks | read-only | Phase 3 |
| `schedule_delete` | Cancel scheduled task | owner/session scoped | Phase 3 |
| `schedule_wakeup` | Internal self-paced loop wakeup | bounded and cancellable | Phase 3 to Phase 4 |
| `notify_user` | Local notification or mobile/channel notification | local-only first; hosted push disabled | Phase 4 to Phase 5 |
| `routine_remote_trigger` | Hosted routine create/update/run/list | disabled until hosted privacy/auth/billing controls exist | Phase 5 |

### MCP and External Resource Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `mcp_list_resources` | List resources exposed by trusted MCP servers | disabled until MCP trust policy exists | Phase 3 |
| `mcp_read_resource` | Read one MCP resource URI | disabled until MCP trust policy exists | Phase 3 |
| `mcp_wait_for_server` | Wait for MCP server readiness | bounded and cancellable | Phase 3 to Phase 4 |
| `tool_search` | Discover/load deferred tool definitions | discovery only, no permission grant | Phase 3 to Phase 5 |

### Memory Tools

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---:|
| `memory_search` | Search governed memory | allow for current project/profile scope | Phase 2 |
| `memory_candidate` | Propose memory write | allow | Phase 1 |
| `memory_write` | Persist memory | needs approval/governance | Phase 2 |
| `memory_update` | Update memory | needs approval/governance | Phase 2 |
| `memory_forget` | Delete memory | allow with audit | Phase 2 |
| `memory_export` | Export memory | needs approval | Phase 2 |
| `eidetic_observation` | Record raw observation metadata/artifact | governed retention policy | Phase 2 |
| `gist_memory_create` | Create compressed memory from raw observation | governed retention policy | Phase 2 |

---

### Cognitive and Orchestration Control Tools

Cognitive and orchestration control tools guide intent classification, reasoning depth, planning, tool selection, uncertainty handling, policy preview, and user-safe explanation. These tools must not directly mutate files, execute commands, access networks, or call external resources unless routed through the Tool Broker.

Cognitive tools must never expose private chain-of-thought. They may return concise summaries, selected reasoning mode, confidence signals, risk flags, policy preview results, and recommended next actions.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `intent_classify` | Classify user intent, task type, risk level, and likely tool families. | allow | Phase 2 |
| `reasoning_mode_select` | Select direct, stepwise, adaptive, reflective, comparative, or constraint-based reasoning mode. | allow | Phase 2 |
| `effort_control` | Select low, medium, high, or maximum reasoning effort based on task complexity, latency, cost, and risk. | allow with policy bounds | Phase 3 |
| `self_check` | Validate a proposed answer, plan, or ToolResult against user constraints, safety rules, and known facts before return. | allow | Phase 2 |
| `uncertainty_estimate` | Estimate confidence, ambiguity, missing inputs, and whether fallback or clarification is needed. | allow | Phase 2 |
| `context_summarise` | Produce bounded summaries of active task context to reduce drift and support long-running workflows. | allow | Phase 2 |
| `explanation_generate` | Generate a user-safe explanation of decisions, tool choices, or policy outcomes without exposing private reasoning. | allow | Phase 2 |

---

### Policy Simulation and Permission Preview Tools

Policy simulation tools evaluate proposed actions without executing them. They are used for planning, user approval previews, dry-runs, and debugging policy behaviour.

Simulation tools must not execute ToolActions, mutate state, access external systems, or silently grant permissions. Their output is advisory only; the Tool Broker must still request a fresh policy decision before any real execution.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `policy_simulate` | Evaluate whether a proposed ToolAction would be allowed, denied, deferred, or require approval without executing it. | allow | Phase 2 |
| `tool_permission_preview` | Show the effective permission result for a tool and argument sample. | allow | Phase 2 |
| `risk_explain` | Explain why an action has been classified as low, medium, high, or critical risk. | allow | Phase 2 |
| `approval_preview` | Generate the user-facing approval explanation, expected effect, risks, and available choices before requesting approval. | allow | Phase 2 |
| `policy_diff` | Compare two policy configurations and show permission changes. | needs approval for sensitive scopes | Phase 3 |

---

### Data Governance and DLP Tools

Data governance tools classify, redact, and validate information before it is logged, stored, exported, used in memory, or sent to external systems.

These tools support secret handling, PII detection, governed memory writes, safe logging, and enterprise data loss prevention controls. They do not themselves approve data movement; approval remains the responsibility of the policy engine and Tool Broker.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `classify_data` | Detect secrets, credentials, PII, regulated data, sensitive business data, or other protected content. | allow | Phase 2 |
| `secret_scan` | Scan files, command output, memory candidates, tool results, or generated artifacts for secrets. | allow inside workspace | Phase 2 |
| `redact_data` | Mask or remove sensitive values before logging, persistence, memory write, or user-visible output. | allow | Phase 2 |
| `dlp_check` | Check whether data can be exported, logged, persisted, sent to a plugin, sent to MCP, or transmitted externally. | managed/project policy | Phase 3 |
| `retention_classify` | Determine retention category for observations, memory artifacts, logs, and generated files. | allow | Phase 3 |

---

### Tool Introspection Tools

Tool introspection tools describe available tools, schemas, risks, required permissions, examples, and effective availability.

These tools help agents and users understand what can be done before attempting execution. Introspection does not grant permission and must not bypass policy evaluation.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `tool_describe` | Return schema, purpose, risk profile, expected effects, limits, and examples for one tool. | allow | Phase 2 |
| `tool_capabilities` | List available capabilities by project, session, managed policy, plugin trust, and runtime environment. | allow | Phase 2 |
| `tool_schema_validate` | Validate proposed tool arguments against the registered tool schema without executing. | allow | Phase 2 |
| `tool_risk_profile` | Return configured risk categories, permission requirements, and approval requirements for a tool. | allow | Phase 2 |

---

### Environment and Resource Inspection Tools

Environment and resource inspection tools provide read-only information about the local or hosted execution environment.

These tools must not expose secrets, credentials, environment variables containing sensitive values, private network details, or unmanaged host information unless explicitly allowed by policy.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `env_inspect` | Inspect runtime environment, OS, shell availability, language runtimes, and workspace configuration. | allow with redaction | Phase 2 |
| `dependency_graph` | Build or read a project dependency graph from supported manifests. | allow inside workspace | Phase 3 |
| `resource_limits_read` | Read configured CPU, memory, timeout, storage, token, budget, and concurrency limits. | allow | Phase 3 |
| `execution_profile_read` | Read active execution profile for shell, Python, Docker, SSH, cloud jobs, or hosted routines. | allow for project/session scope | Phase 3 |

---

### Transaction and Rollback Tools

Transaction and rollback tools provide safer handling for multi-step changes, generated patches, dependency updates, and automated workflows.

Any transaction that may mutate files, execute commands, alter configuration, update memory, or affect external systems must be governed by the Tool Broker. Rollback metadata must be bounded, auditable, and scoped to the current workspace, task, session, or managed policy.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `snapshot_create` | Create a restorable snapshot before risky mutation. | allow or needs approval depending scope | Phase 2 |
| `snapshot_list` | List available snapshots for the current workspace, session, task, or transaction. | allow for owner/session scope | Phase 2 |
| `snapshot_restore` | Restore a previous snapshot or change set. | needs approval unless restoring own failed transaction | Phase 3 |
| `transaction_begin` | Begin grouped multi-action execution with rollback metadata. | needs approval | Phase 3 |
| `transaction_commit` | Commit grouped actions and mark rollback boundary. | needs approval | Phase 3 |
| `transaction_rollback` | Roll back grouped actions to a previous snapshot or checkpoint. | allow for owner/session scope, approval for wider scope | Phase 3 |

---

### Observability and Audit Tools

Observability and audit tools provide controlled access to tool lifecycle events, policy decisions, approvals, failures, cancellations, truncation, and runtime metrics.

These tools must respect ownership, project scope, managed policy, and audit sensitivity. They must not replay actions in a way that causes side effects unless explicitly routed through the Tool Broker as a new ToolAction.

| Tool | Purpose | Default policy | First build phase |
|---|---|---|---|
| `trace_query` | Query tool lifecycle traces by session, turn, action, task, or workflow. | allow for owner/session scope | Phase 3 |
| `audit_log_read` | Read security-relevant tool, approval, policy, plugin, memory, and execution events. | managed/admin only | Phase 4 |
| `metrics_read` | Read tool usage, latency, failure rate, approval rate, cancellation rate, and truncation metrics. | managed/project scoped | Phase 4 |
| `event_replay` | Replay prior lifecycle events for debugging without re-executing tools. | needs approval or admin scope | Phase 4 |
| `incident_export` | Export bounded audit bundle for investigation or support. | managed/admin approval | Phase 5 |

---

## Command Policy

Local command policy must classify commands into categories:

| Category | Examples | Default |
|---|---|---|
| safe read-only | `pwd`, `ls`, `git status` | needs approval in Phase 1; scoped allowlist in Phase 2 |
| tests/build | `pytest`, `npm test`, `ruff check` | needs approval, can be session-allowed |
| package install | `pip install`, `npm install` | needs approval with dependency warning |
| file mutation | `rm`, `mv`, `sed -i` | needs approval or deny |
| network | `curl`, `wget`, package downloads | deny unless network enabled |
| privilege escalation | admin/root-level commands | deny by default |
| destructive | recursive delete, disk format, registry deletion | deny by default |
| secret access | env dumps, credential files | deny or high-risk approval |

---

## Output Limits

Every tool result must support max bytes, max lines, max items, truncation indicator, artifact path for large output, redaction status, elapsed time, and cancellation status.

---

Every ToolResult must support:

- `action_id`
- `tool_name`
- `status`
- `decision`
- `risk_level`
- `policy_applied`
- `policy_reasons`
- `max_bytes`
- `max_lines`
- `max_items`
- `truncated`
- `artifact_path`
- `redaction_status`
- `elapsed_ms`
- `cancelled`
- `retryable`
- `confidence_score`
- `uncertainty_flags`
- `safe_explanation`


Large outputs must be truncated according to configured limits. When truncation occurs, the result must include a truncation indicator and, where appropriate, an artifact path for the full bounded output.

ToolResult metadata must not expose private chain-of-thought. `safe_explanation` may contain a concise user-facing explanation of the result, policy decision, uncertainty, or recommended next action.

---

## Tool Events

Required events:

- `action_proposed`
- `action_validated`
- `policy_decision`
- `approval_requested`
- `approval_received`
- `approval_denied`
- `approval_deferred`
- `tool_started`
- `tool_stdout_chunk`
- `tool_stderr_chunk`
- `tool_completed`
- `tool_failed`
- `tool_cancelled`
- `tool_result_truncated`

Additional phase-scheduled tool families must define event names before implementation. This includes notebook edits, LSP/code-intelligence calls, monitors, schedules, MCP resource reads, deferred tool discovery, notifications, team/workflow tools, hosted routines, and marketplace-backed plugin operations.

---

## Tool Testing Requirements

Tests must prove:

- no tool executes without policy;
- unknown tools fail safely;
- denied action does not execute;
- local command execution requires approval;
- approval is action-bound;
- path traversal is blocked;
- output truncation works;
- timeout/cancellation is logged;
- plugin tools cannot bypass broker;
- hooks cannot silently approve disallowed actions unless policy permits hook decision authority;
- scheduled tasks are bounded, cancellable, and cannot create hidden infinite loops;
- monitors are cancellable and rate-limited;
- LSP/MCP/plugin-server tools require explicit trust and cannot start from an untrusted project;
- hosted routines, hosted push, marketplace installs, and cloud jobs are denied until Phase 5 policy exists.
