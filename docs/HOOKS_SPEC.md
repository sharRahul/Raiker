# Hooks Specification

> **Status banner, refreshed 2026-08-22.** The launchable clients are the local
> terminal client (`raiker`) and the local web dashboard (`raiker-app` /
> `raiker-web`, loopback only). Approval resolution **executes** the twelve
> capabilities in `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) —
> file mutations, patches, bounded local `shell`, the git write and push path, a
> GitHub write, the two local planning rows, durable memory writes and forgets,
> and owner-selected SSH and Daytona commands — each re-governed at execution
> time; every other capability keeps decision-only resolution. Runtime execution
> is **not** globally disabled: plugin slices, graph indexing, channels,
> scheduled routines, model providers, MCP, container read tools and governed
> local commands all have real executors and are governed per action. Sensitive
> finance, investment, medical, pregnancy, CCTV, home-security and hardware
> domains have no executor and fail closed. Rich/native TUI, mobile, IDE and
> hosted multi-user clients remain deferred. The canonical statement of what is
> implemented is [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md); where
> this document and the code disagree, the code wins and this document must be
> updated.


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
>   workspace** (reuses `raiker/tools/filesystem.py::resolve_workspace_path`), bounded `timeout_ms`,
>   truncated output, minimal environment. Non-zero exit blocks by convention; JSON stdout
>   `{"decision": ...}` is honored. Timeouts/errors emit `hook_timeout`/`hook_failed` and fail
>   open (the action falls through to normal policy).
> - **Events:** `hook_matched`, `hook_executed`, `hook_decision`, `hook_failed`, `hook_timeout`.
> - **No hooks configured → no-op:** the dispatcher is inactive and the runtime is unchanged.
> - **A file that cannot be read fails closed for itself, not for the runtime.**
>   `HooksRegistry.load` runs inside the `AgentGateway` constructor, so a parse error used to make
>   *every prompt in the product* fail with a raw `JSONDecodeError`. It now records a
>   `HookSourceStatus` per source: a bad file contributes no rules and is reported, the others load
>   normally, and the runtime is untouched. `HooksRegistry.from_config` still raises, because a
>   caller handing over a config wants to be told it is wrong.
> - **Owner off switch:** `hooks.disabled` in the owner's settings makes
>   `HookDispatcher.is_active()` return `False`, re-read once per turn so it applies without a
>   restart. It is deliberately an owner setting rather than a fourth config source, because
>   `config/hooks.json` travels with a repository and a file a project ships must not be able to
>   re-enable itself. Rules stay loaded and listed while it is on (`raiker/hooks/owner_switch.py`).
> - **Owner surface:** Extensions → **Hooks** (`GET /api/hooks`) reports what the runtime loaded —
>   each rule's event, matcher, `if` guard, scope, source file and handlers; the file it could not
>   read; the events this build actually dispatches; the builtin handler names that exist; and the
>   recent `hook_*` records. It is read-only: the config files are the owner's own text, and a
>   surface that rewrote them would need its own authority story.
> - **Three ways a configured hook still does nothing, each stated rather than implied:** its file
>   did not parse; its event is in `HOOK_EVENTS` but not `DISPATCHED_HOOK_EVENTS`, so it parses and
>   never fires; or nothing on it carries a decision the runtime honours — only `PreToolUse` and
>   `PreCompact` decide (`DECIDING_HOOK_EVENTS`), and a `builtin` naming a handler this build does
>   not ship raises at dispatch, so it is reported as unavailable rather than as enforcing.
>
> See `tests/test_hooks.py` and `tests/test_hooks_surface.py` for the acceptance tests and `docs/EXTENSIBILITY_MODEL.md` for how
> hooks sit alongside the other extension surfaces. Sections below are the full design target;
> not every event/handler is wired yet (see the list above).
>
> **Reference alignment (Claude Code `hooks`), corrected 2026-08-23.** The
> [reference](https://code.claude.com/docs/en/hooks) documents **31 events** and
> **5 handler types** (`command`, `http`, `mcp_tool`, `prompt`, `agent`) using a
> three-level `EventName → matcher → hooks[]` config with an optional `if`
> condition (e.g. `Bash(git *)`). The matcher, `if` and decision-authority
> semantics here follow that reference.
>
> Raiker's event list and handler types are a **subset**, not a superset. This
> banner used to say the opposite. Raiker emits **16 of the 31**, and every one of
> its 16 is one of the reference's; the 15 with no Raiker equivalent are `Setup`,
> `UserPromptExpansion`, `PostToolBatch`, `Notification`, `MessageDisplay`,
> `TeammateIdle`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`,
> `DirectoryAdded`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`,
> `Elicitation` and `ElicitationResult`. Of the 5 handler types Raiker builds
> `command`; `builtin` is Raiker's own in-process code and is not one of the five,
> and the remaining four are refused at parse time (BUG-226).
>
> Two places Raiker is deliberately **not** aligned, and will not be:
> a Raiker hook can return only `deny` or `ask` from an authoritative handler, so
> nothing a hook returns can allow an action policy refused — the reference's
> `permissionDecision: "allow"` has no equivalent and will not get one; and the
> owner off switch is a stored owner setting rather than a `disableAllHooks` key
> in a config file a repository could ship. See
> [reference compatibility §2.5 and §4.3](REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks).
>
> **Re-verified 2026-08-23** against the reference page itself: 31 events, 5
> handler types, both counts and all 15 missing names unchanged.

### Which of the fifteen are worth adding

Parity is not the goal, so the fifteen are not one backlog item. Categorically:

| Event | Verdict | Why |
|---|---|---|
| `ConfigChange` | **Add — YES, differentiator** | "The owner changed a setting" is a governance fact Raiker records nowhere as a hook. It is the one missing event that would let an owner enforce a rule about their *own* configuration drifting |
| `Notification` | **Add — PARITY** | Raiker already has a notification path (`raiker/notify/`); it has no hook, so nothing can react to one |
| `PostToolBatch` | **Add — PARITY** | Raiker executes validated read-only calls concurrently and already knows when a batch ends. The event exists in the runtime in all but name |
| `InstructionsLoaded` | **Add — PARITY** | Project instructions are owner records rather than repository files, so the event is cheap and lets a hook see what standing context a turn got |
| `FileChanged` | **Consider — NO, little advantage** | Raiker's mutations are approved and already emit events; a filesystem watcher would be a second, weaker source of the same fact |
| `Elicitation`, `ElicitationResult` | **Blocked, not refused** | There is no mid-turn question surface to hook. If [backlog item 22](REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-medium-effort) is built, these follow it |
| `Setup`, `UserPromptExpansion`, `MessageDisplay` | **NO — little advantage** | Each names a step in the reference's own harness rather than a boundary Raiker has |
| `TeammateIdle` | **N/A** | Raiker is single-owner; there is no teammate |
| `CwdChanged`, `DirectoryAdded` | **N/A** | A Raiker session has one workspace, resolved once and confined |
| `WorktreeCreate`, `WorktreeRemove` | **N/A** | Raiker has no worktree surface, deliberately — see [§2.8](REFERENCE_PLATFORM_COMPATIBILITY.md#28-coding-agent--raiker-build) |

So of fifteen: **four worth adding**, two blocked behind a surface that does not
exist, four not applicable to a single-owner local product, and five of little
value. "Sixteen of thirty-one" is the honest count; "twenty of thirty-one" is the
ceiling worth aiming at.

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

## What This Build Accepts And Emits

The catalogue above is the target surface. This section is the build, and the two
are kept apart deliberately: a rule that parses and never runs is a safeguard the
owner believes is in place when it is not.

`raiker/hooks/contracts.py` publishes two sets:

- **`HOOK_EVENTS`** — what a configuration file may name. Anything else is
  refused at parse time, so a typo is never silently ignored.
- **`DISPATCHED_HOOK_EVENTS`** — what the runtime really emits.

They are **equal on this build** (BUG-223). `tests/test_hooks_surface.py` derives
the second set from the call sites in the source and asserts it matches, so the
published surface cannot drift from the code; when a later build accepts an event
before wiring it, every surface that lists hooks marks such a rule as configured
but never firing.

| Event | Where it is emitted | Decides? |
|---|---|---|
| `SessionStart` | first turn of a new conversation | observes |
| `SessionEnd` | a conversation is archived or deleted | observes |
| `UserPromptSubmit` | before the turn runs | observes |
| `Stop` | a turn finished and produced an answer | observes |
| `StopFailure` | a turn failed, was stopped, or parked on an approval | observes |
| `PreCompact` | before older exchanges leave the context window | **decides** |
| `PostCompact` | after compaction, with what it produced | observes |
| `PreToolUse` | before policy finalises a tool call | **decides** |
| `PostToolUse` | a tool call succeeded | observes |
| `PostToolUseFailure` | a tool call failed | observes |
| `PermissionRequest` | an approval is about to be raised | observes |
| `PermissionDenied` | a tool call was denied | observes |
| `SubagentStart` | a delegation is about to run | observes |
| `SubagentStop` | a delegation finished | observes |
| `TaskCreated` | a task was created | observes |
| `TaskCompleted` | a task completed, failed or was cancelled | observes |

Only `PreToolUse` and `PreCompact` decisions are honoured, and only from a
handler holding decision authority. Everything else observes: a handler returning
`deny` on `PostToolUse` changes nothing, which the Hooks surface says rather than
implies.

`Stop` and `StopFailure` are split because "the turn ended" and "the turn
succeeded" are different questions. A turn parked on an approval has not
finished — it is waiting — and a turn the owner stopped did what it was told;
reporting either as `Stop` would let a rule written to react to completion fire on
a run that never completed.

---

## Where Rules Are Loaded From

In order of authority, highest first:

| Source | Scope | Written by |
|---|---|---|
| `config/managed-hooks.json` | `managed` | the organisation |
| `config/hooks.json` | `project` | the repository |
| `.raiker/hooks.json` | `local` | this checkout |
| `.raiker/plugins/<plugin_id>/hooks.json` | `plugin` | an installed plugin |

A lower scope can never override a higher-scope deny, so a plugin rule can make
an action stricter and can never loosen one the owner set.

A source that cannot be parsed contributes **no rules** and is reported as a
failed source; it never takes the rest of the runtime with it. `HooksRegistry.load`
runs inside the `AgentGateway` constructor, so raising there once made every
prompt in the product fail.

### The Owner's Off Switch

`hooks.disabled` in owner settings makes `HookDispatcher.is_active()` return
`False` for every event, including the ones no turn owns — tasks, subagents,
session ends. It is deliberately **not** a fourth configuration file: a file a
project ships must not be able to re-enable itself. Rules stay listed while it is
on, because off is a state to display rather than a reason to hide what would
otherwise run.

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
