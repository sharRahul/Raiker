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
  "rule_id": "perm_001",
  "scope": "project",
  "effect": "allow",
  "tool": "read_file",
  "argument_match": {
    "path": "docs/**"
  },
  "conditions": {
    "workspace_only": true,
    "max_bytes": 200000
  },
  "expires_at": null,
  "reason": "Allow reading documentation files"
}
```

Rules must support exact tool names, wildcard tool groups, path glob patterns, command prefix patterns, network host allowlists, max output size, timeout, workspace-only restriction, expiry, and reason string.

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
  "policy_reasons": ["shell_requires_approval"],
  "expected_effect": "Runs tests in the current workspace.",
  "choices": ["approve_once", "approve_session", "deny", "defer"],
  "expires_at": null
}
```

Approvals must be bound to exact `action_id`. Reusing approval for a changed command is forbidden.

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
