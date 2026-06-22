# Hooks Specification

> Current truth (2026-06-21): the launchable local UIs are the plain local terminal client and the local web dashboard (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only; read-only governed views + governed prompt/turn/approval/runtime-mutation flows where approval resolution is metadata-only; adds no authority of its own). Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Runtime execution remains disabled for plugin execution, graph indexing, semantic/vector writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, remote/container/cloud/process/shell/network execution.


> **Code status: implemented (core).** `raiker/hooks/` is a working dispatcher wired through the
> tool broker and gateway. Implemented now:
> - **Handler types:** `builtin` (in-process, trusted) and `command` (subprocess). `http`,
>   `mcp_tool`, `prompt`, and `agent` handlers remain specified-not-implemented (they need
>   network/model/subagent surfaces that are still gated).
> - **Wired events:** `SessionStart`, `UserPromptSubmit` (gateway), and `PreToolUse`,
>   `PermissionRequest`, `PermissionDenied`, `PostToolUse`, `PostToolUseFailure` (tool broker).
>   Other events in this spec are not dispatched yet.
> - **Decision authority:** `PreToolUse` can make an action stricter only — a hook `deny`
>   short-circuits to a denied `PolicyDecision`; a hook `ask` upgrades an otherwise-allowed action
>   to `needs_approval`. Hooks never allow a denied action; managed-scope deny wins
>   (`raiker/hooks/decision.py`).
> - **Config sources & scope:** `config/managed-hooks.json` (managed) > `config/hooks.json`
>   (project) > `.raiker/hooks.json` (local), loaded by `raiker/hooks/registry.py`.
> - **Command-hook safety:** argv list only (no shell), program must resolve **inside the
>   workspace** (reuses `raiker/tools/filesystem.resolve_workspace_path`), bounded `timeout_ms`,
>   truncated output, minimal environment. Non-zero exit blocks by convention; JSON stdout
>   `{"decision": ...}` is honored. Timeouts/errors emit `hook_timeout`/`hook_failed` and fail
>   open (the action falls through to normal policy).
> - **Events:** `hook_matched`, `hook_executed`, `hook_decision`, `hook_failed`, `hook_timeout`.
> - **No hooks configured → no-op:** the dispatcher is inactive and the runtime is unchanged.
>
> See `tests/test_hooks.py` for the acceptance tests and `docs/EXTENSIBILITY_MODEL.md` for how
> hooks sit alongside the other extension surfaces. Sections below are the full design target;
> not every event/handler is wired yet (see the list above).
>
> **Reference alignment (Claude Code `hooks`):** the reference documents ~31 events and 5
> handler types (`command`, `http`, `mcp_tool`, `prompt`, `agent`) using a three-level
> `EventName → matcher → hooks[]` config with an optional `if` condition (e.g. `Bash(git *)`).
> Raiker's event list and handler types are intentionally a superset; the matcher/`if`/
> decision-authority semantics follow that reference.

Hooks let users, projects, plugins, administrators, and skills run controlled logic at lifecycle points in Raiker.

Hooks are powerful and dangerous. They must be explicit, scoped, policy-aware, event-logged, timeout-bounded, and testable.

---

## Hook Goals

Raiker hooks must support lifecycle automation, policy enforcement, validation and linting, prompt/context augmentation, notification and telemetry, tool result inspection, async background reactions, plugin/skill-provided behaviour, and enterprise-managed controls.

---

## Hook Handler Types

| Type | Description | Default trust |
|---|---|---|
| `command` | Local command or script | untrusted unless scoped |
| `http` | HTTP endpoint | denied unless network enabled |
| `mcp_tool` | MCP server tool | untrusted, brokered |
| `prompt` | LLM prompt hook | untrusted model output |
| `agent` | Subagent hook | untrusted until policy-reviewed |
| `builtin` | Raiker built-in handler | trusted internal code |

---

## Hook Scopes

| Scope | Location | Shareable | Notes |
|---|---|---:|---|
| managed | enterprise policy | yes | highest priority |
| user | user config | no | applies across projects |
| project | committed project config | yes | review before committing |
| local | gitignored project config | no | personal overrides |
| plugin | plugin package | yes | enabled with plugin |
| skill | skill manifest/frontmatter | yes | active only while skill active |
| agent | subagent manifest | yes | active only while agent active |
| session | runtime session config | no | temporary |

---

## Hook Configuration Schema

```json
{
  "schema_version": "1.0",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "shell|powershell",
        "if": "shell(rm -rf *)",
        "handlers": [
          {
            "id": "block-destructive-command",
            "type": "command",
            "command": "./.raiker/hooks/block_destructive.sh",
            "args": [],
            "timeout_ms": 3000,
            "async": false,
            "decision_authority": true
          }
        ]
      }
    ]
  }
}
```

---

## Matcher Rules

Hook matchers must support `*` for all, exact tool/event names, `|` separated exact alternatives, regular expressions when explicitly marked, argument-pattern expressions, path globs for file events, subagent name matching, command name matching, and channel name matching.

If a matcher is unsupported for an event, configuration validation must warn or fail. It must not silently ignore mistakes.

---

## Hook Lifecycle Events

### Session Events

| Event | Fires when |
|---|---|
| `SessionStart` | New session starts or resumes |
| `SessionResume` | Existing session is resumed |
| `SessionFork` | Session is forked from checkpoint |
| `SessionEnd` | Session ends |
| `ConfigChange` | Runtime config changes |
| `InstructionsLoaded` | Project/user instructions are loaded |

### Prompt Events

| Event | Fires when |
|---|---|
| `UserPromptSubmit` | User submits prompt before processing |
| `UserPromptExpansion` | Slash command/macro expands into prompt |
| `PromptNormalised` | Prompt is normalised |
| `ContextGathered` | Context bundle is ready |
| `PreCompact` | Before context compaction |
| `PostCompact` | After compaction |

### Tool Events

| Event | Fires when |
|---|---|
| `PreToolUse` | Before policy finalises execution |
| `PermissionRequest` | Approval is about to be shown |
| `PermissionDenied` | Tool is denied |
| `PostToolUse` | Tool succeeds |
| `PostToolUseFailure` | Tool fails |
| `PostToolBatch` | Parallel tool batch completes |
| `ToolOutputChunk` | Streaming output chunk arrives |

### Task And Background Events

| Event | Fires when |
|---|---|
| `TaskCreated` | Background task is created |
| `TaskStarted` | Background task begins |
| `TaskProgress` | Task emits progress |
| `TaskQuestion` | Task asks user a side question |
| `TaskAnswered` | User answers side question |
| `TaskCompleted` | Task completes |
| `TaskFailed` | Task fails |
| `TaskCancelled` | User cancels task |

### Subagent Events

| Event | Fires when |
|---|---|
| `SubagentStart` | Subagent starts |
| `SubagentMessage` | Subagent emits message |
| `SubagentToolUse` | Subagent proposes tool |
| `SubagentStop` | Subagent stops |

### File/Workspace Events

| Event | Fires when |
|---|---|
| `CwdChanged` | Working directory changes |
| `FileChanged` | Watched file changes |
| `WorktreeCreate` | Worktree is created |
| `WorktreeRemove` | Worktree is removed |
| `CheckpointCreated` | Checkpoint snapshot created |
| `CheckpointRestored` | Checkpoint restored |

### Display And Notification Events

| Event | Fires when |
|---|---|
| `MessageDisplay` | Assistant text streams to UI |
| `Notification` | Notification is emitted |
| `Idle` | Agent/team becomes idle |
| `Error` | Structured error is recorded |

---

## Hook Input Schema

```json
{
  "schema_version": "1.0",
  "hook_event_name": "PreToolUse",
  "hook_id": "hook_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "task_id": null,
  "cwd": "/workspace/project",
  "source_scope": "project",
  "actor": "agent_runtime",
  "event": {},
  "tool_name": "shell",
  "tool_input": {
    "command": "pytest"
  },
  "context": {
    "risk_level": "high",
    "policy_state": "pending"
  }
}
```

---

## Hook Output Schema

```json
{
  "schema_version": "1.0",
  "hook_event_name": "PreToolUse",
  "decision": "deny",
  "decision_reason": "Destructive command blocked.",
  "updated_input": null,
  "additional_context": null,
  "notifications": [],
  "defer_until": null,
  "metadata": {}
}
```

Allowed decisions:

- `allow`
- `deny`
- `ask`
- `defer`
- `no_decision`
- `retry`
- `cancel_task`
- `add_context_only`

Hook output can deny or ask for approval if the hook has decision authority, add context, rewrite input only when event allows it, emit notification, defer tool call, request retry after denial/failure, or cancel background task if policy permits.

---

## Decision Authority Rules

A hook may not silently grant broad permissions.

1. Hooks can always make a tool stricter by denying or asking.
2. Hooks can only allow a tool if policy grants hook decision authority.
3. Project hooks cannot override managed denies.
4. Plugin hooks cannot override user or managed denies.
5. Prompt/agent hooks are advisory unless explicitly trusted.
6. Hook output must be logged.

---

## Async Hooks

Hooks may run asynchronously when:

- they do not decide current action;
- they do not mutate current prompt/tool input;
- they have bounded timeout and cancellation;
- they emit progress and completion events;
- their output is attached to subsequent turns, task notes, memory candidates, or notifications.

Examples:

- run tests after file edit;
- index changed files into graph memory;
- refresh semantic memory;
- send notification when task completes;
- lint project config after config change.

Async hooks must not block the main agent loop unless explicitly configured as blocking.

---

## Hook Security Requirements

Hooks are untrusted by default.

Required controls:

- config validation;
- path safety for command hooks;
- timeout;
- output limits;
- redaction;
- no implicit network access;
- policy-controlled decision authority;
- event logging;
- test coverage;
- managed-policy override.

---

## Hook Testing Requirements

Tests must prove:

- matcher selects correct tools/events;
- matcher rejects invalid config;
- PreToolUse can deny tool;
- silent hook does not approve tool;
- async hook does not block current turn;
- hook timeout is handled;
- hook output is logged;
- project hook cannot override managed deny;
- plugin hook is inactive when plugin disabled.
