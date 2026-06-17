# Tools And Permissions Specification

This document defines Raiker's tool system, permission model, approval modes, and safety requirements.

The tool broker is the only path to agent-controlled actions. Runtime code, clients, plugins, hooks, models, and subagents must not execute tools directly.

---

## Tool Broker Responsibilities

The broker must:

1. receive a `ToolAction` proposal;
2. validate tool name and argument schema;
3. normalise paths and arguments;
4. classify risk;
5. request policy decision;
6. request user approval when required;
7. execute only allowed actions;
8. apply timeout, output limits, and cancellation;
9. redact secrets from logs;
10. emit lifecycle events;
11. return a structured `ToolResult`.

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

| Decision | Meaning |
|---|---|
| `allow` | Execute immediately. |
| `deny` | Do not execute. Return denied result. |
| `needs_approval` | Pause and request approval. |
| `defer` | Put action into deferred queue. |
| `allow_once` | Allow one exact action ID only. |
| `allow_for_session` | Allow matching action pattern for current session. |
| `allow_for_project` | Allow matching action pattern for current project config. |
| `allow_managed` | Allow by administrator/managed policy. |

Phase 1 may implement only `allow`, `deny`, and `needs_approval`, but the contracts must allow future decisions.

---

## Permission Scopes

| Scope | File/location | Shareable | Priority |
|---|---|---:|---:|
| managed | enterprise/admin policy | yes | highest |
| user | user config | no | high |
| project | committed project config | yes | medium |
| local | gitignored local project config | no | medium-high |
| plugin | plugin manifest and settings | yes | lower than explicit user/project policy |
| session | runtime approval | no | temporary |
| action | exact action approval | no | one-shot |

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

Rules must support:

- exact tool names;
- wildcard tool groups;
- path glob patterns;
- command prefix patterns;
- network host allowlists;
- max output size;
- timeout;
- workspace-only restriction;
- expiry;
- reason string.

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

### Filesystem Tools

| Tool | Purpose | Default policy |
|---|---|---|
| `read_file` | Read text file inside workspace | allow if inside workspace |
| `write_file` | Create or replace file | needs approval or deny in Phase 1 |
| `edit_file` | Patch or edit existing file | needs approval or deny in Phase 1 |
| `delete_file` | Delete file | deny by default |
| `list_directory` | List entries | allow inside workspace |
| `stat_path` | Get metadata | allow inside workspace |
| `copy_path` | Copy file/dir | needs approval |
| `move_path` | Rename/move | needs approval |
| `diff_files` | Compare files | allow inside workspace |
| `apply_patch` | Apply unified patch | needs approval |

### Search Tools

| Tool | Purpose | Default policy |
|---|---|---|
| `glob` | Find files by pattern | allow inside workspace |
| `grep` | Search text | allow inside workspace |
| `semantic_search` | Vector search | future phase |
| `symbol_search` | LSP/code symbols | future phase |
| `graph_query` | Query code graph | future phase |
| `web_search` | Search internet | deny unless enabled |
| `web_fetch` | Fetch URL | deny unless enabled |

### Execution Tools

| Tool | Purpose | Default policy |
|---|---|---|
| `shell` | Run shell command | needs approval |
| `powershell` | Run PowerShell command | needs approval |
| `python_exec` | Run isolated Python snippet | needs approval |
| `git` | Git operation wrapper | scoped policy by subcommand |
| `docker` | Docker command wrapper | future phase |
| `ssh` | Remote command | future phase |
| `modal_job` | Cloud job | future phase |

### Agent Tools

| Tool | Purpose | Default policy |
|---|---|---|
| `ask_user` | Ask clarification | allow |
| `side_question` | Ask non-blocking clarification while work continues | allow with task binding |
| `spawn_subagent` | Start subagent | needs approval until configured |
| `create_task` | Create background task | needs approval for long-running work |
| `cancel_task` | Cancel background task | allow for task owner |
| `handoff_task` | Delegate to other agent/channel | needs approval |

### Memory Tools

| Tool | Purpose | Default policy |
|---|---|---|
| `memory_search` | Search governed memory | allow for current project/profile scope |
| `memory_candidate` | Propose memory write | allow |
| `memory_write` | Persist memory | needs approval/governance |
| `memory_update` | Update memory | needs approval/governance |
| `memory_forget` | Delete memory | allow with audit |
| `memory_export` | Export memory | needs approval |

---

## Shell Command Policy

Shell policy must classify commands into categories:

| Category | Examples | Default |
|---|---|---|
| safe read-only | `pwd`, `ls`, `git status` | needs approval in Phase 1; allowlist later |
| tests/build | `pytest`, `npm test`, `ruff check` | needs approval, can be session-allowed |
| package install | `pip install`, `npm install` | needs approval with dependency warning |
| file mutation | `rm`, `mv`, `sed -i` | needs approval or deny |
| network | `curl`, `wget`, package downloads | deny unless network enabled |
| privilege escalation | `sudo`, admin PowerShell | deny by default |
| destructive | `rm -rf`, disk format, registry deletion | deny by default |
| secret access | env dumps, credential files | deny or high-risk approval |

---

## Output Limits

Every tool result must support:

- `max_bytes`;
- `max_lines`;
- `max_items`;
- truncation indicator;
- artifact path for large output;
- redaction status;
- elapsed time;
- cancellation status.

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

---

## Tool Testing Requirements

Tests must prove:

- no tool executes without policy;
- unknown tools fail safely;
- denied action does not execute;
- shell requires approval;
- approval is action-bound;
- path traversal is blocked;
- output truncation works;
- timeout/cancellation is logged;
- plugin tools cannot bypass broker;
- hooks cannot silently approve disallowed actions unless policy permits hook decision authority.
