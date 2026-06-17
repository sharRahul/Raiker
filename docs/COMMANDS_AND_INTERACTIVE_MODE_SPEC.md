# Commands And Rich Interactive Mode Specification

Raiker must provide a rich interactive experience, not only a simple CLI.

The Rich TUI is a first-class client that can show live work, ask and answer side questions, interrupt or steer the active task, review approvals, browse events, inspect memory, and manage checkpoints without losing the active agent state.

---

## Interface Modes

| Mode | Purpose |
|---|---|
| `cli_command` | One-shot command, scriptable. |
| `interactive_cli` | Prompt loop in terminal. |
| `rich_tui` | Full terminal UI with panels and background tasks. |
| `headless` | API/automation mode. |
| `daemon` | Long-running local service for channels/webhooks. |

---

## Rich TUI Requirements

The Rich TUI must support:

1. live transcript panel;
2. active plan panel;
3. task progress panel;
4. tool calls panel;
5. approvals inbox;
6. side-question input box;
7. event log viewer;
8. checkpoint timeline;
9. memory inspector;
10. graph/context inspector;
11. notifications panel;
12. command palette;
13. file/reference picker;
14. background task manager;
15. interrupt/steer controls;
16. model/context usage display;
17. policy decision display;
18. keyboard shortcuts;
19. mouse support where available;
20. fallback plain terminal mode.

---

## TUI Layout

Recommended default layout:

```text
┌──────────────────────── Raiker Session ────────────────────────┐
│ Transcript / Assistant Stream                                   │
├───────────────┬──────────────────────────┬─────────────────────┤
│ Plan          │ Active Tools / Tasks     │ Approvals / Alerts  │
│ Checkpoints   │ Progress / Logs          │ Memory / Context    │
├───────────────┴──────────────────────────┴─────────────────────┤
│ Side question / command / prompt input                          │
└─────────────────────────────────────────────────────────────────┘
```

Panels must be resizable or switchable through keyboard commands.

---

## Side Questions While Work Continues

This is a mandatory feature.

User must be able to ask:

```text
What is it doing now?
Why is it running tests?
Can you explain the last error?
How far has the task reached?
What files has it changed?
```

without stopping the active task.

Implementation rules:

1. The side question runs as a separate lightweight turn.
2. It reads active task state and event log snapshot.
3. It does not mutate the active task unless escalated.
4. It displays answer in a side panel or inline note.
5. It can be promoted to steering instruction by user confirmation.
6. It must not reorder events in the main task.
7. It must be cancellable.

---

## Interrupt And Steering Controls

The user can interrupt active work with explicit controls:

| Control | Behaviour |
|---|---|
| `pause` | Pause after current safe boundary. |
| `cancel` | Cancel active task and log cancellation. |
| `steer` | Add new instruction to active task. |
| `approve` | Approve exact pending action. |
| `deny` | Deny exact pending action. |
| `defer` | Move approval/action to deferred queue. |
| `fork` | Fork from checkpoint. |
| `rewind` | Restore previous checkpoint. |
| `summarise` | Summarise current task state. |

Safe boundaries include:

- before tool execution;
- after tool completion;
- before file write;
- before shell execution;
- before checkpoint creation;
- before subagent handoff.

---

## Command Syntax

Raiker command input must support:

| Syntax | Meaning |
|---|---|
| `/command` | Slash command. |
| `!command` | Shell command proposal, never direct execution without policy. |
| `@path` | File or directory mention. |
| `#task` | Task reference. |
| `$memory` | Memory reference/search. |
| `%checkpoint` | Checkpoint reference. |
| `?question` | Side question shortcut. |
| `Ctrl+C` | Interrupt/pause flow, not silent crash. |
| `Ctrl+D` | Exit if safe or ask if task running. |

---

## Built-In Slash Commands

| Command | Purpose |
|---|---|
| `/help` | Show commands. |
| `/status` | Show active session/task status. |
| `/plan` | Show or request plan. |
| `/tasks` | Show background tasks. |
| `/approvals` | Show pending approvals. |
| `/events` | Open event log viewer. |
| `/checkpoints` | Show checkpoint timeline. |
| `/rewind` | Restore checkpoint. |
| `/fork` | Fork from checkpoint. |
| `/memory` | Inspect/search governed memory. |
| `/context` | Show current context bundle. |
| `/tools` | Show tool registry and permissions. |
| `/permissions` | Show/edit permission rules. |
| `/hooks` | Show hook registry and status. |
| `/plugins` | Show plugin registry. |
| `/channels` | Show paired channels. |
| `/models` | Show model profiles. |
| `/compact` | Compact context. |
| `/export` | Export session/task/events. |
| `/doctor` | Run diagnostics. |
| `/config` | Inspect config. |
| `/quit` | Exit safely. |

---

## Command Expansion

Slash commands expand into structured prompts or actions before reaching the runtime.

Expansion lifecycle:

```text
raw input
  -> command parser
  -> UserPromptExpansion hook
  -> command permission check
  -> PromptEnvelope or ToolAction proposal
  -> runtime
```

Command expansion must be event-logged.

---

## Background Task UI

A background task must expose:

- task ID;
- title;
- status;
- current step;
- progress percentage if known;
- started time;
- elapsed time;
- last event;
- pending approvals;
- side questions;
- changed files;
- output artifacts;
- cancel/pause/steer controls.

Task statuses:

- `queued`
- `running`
- `waiting_for_approval`
- `waiting_for_user_answer`
- `paused`
- `cancelling`
- `cancelled`
- `completed`
- `failed`

---

## Approval UX

Approvals must show:

- exact tool/action;
- exact command/path/URL;
- risk level;
- policy reasons;
- file diff if file write/edit;
- network host if network;
- shell command classification;
- choices: approve once, approve session, deny, defer, inspect.

No approval should be hidden in a stream of text. It must appear in approval inbox.

---

## File Mentions

`@path` mentions must:

- resolve inside workspace unless allowed;
- show matched files before loading if ambiguous;
- require approval for large/binary/sensitive files;
- record provenance in context bundle;
- never bypass policy.

---

## TUI Events

Required events:

- `tui_started`
- `tui_panel_opened`
- `tui_command_submitted`
- `command_expanded`
- `side_question_received`
- `side_question_answered`
- `task_interrupted`
- `task_steered`
- `approval_rendered`
- `approval_selected`
- `checkpoint_selected`
- `tui_exited`

---

## TUI Testing Requirements

Tests must prove:

- command parser handles `/`, `!`, `@`, `?`;
- side question does not stop active task;
- interrupt changes active task state safely;
- approval choice binds to action ID;
- checkpoint selection triggers restore/fork flow;
- TUI can render with no color/limited terminal;
- background task progress updates without corrupting transcript.
