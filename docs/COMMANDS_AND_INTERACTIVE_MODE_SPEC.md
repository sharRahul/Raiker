# Commands And Rich Interactive Mode Specification

Raiker must provide a rich interactive experience, not a set of fragmented primary CLI entry points.

The Rich TUI is the primary human interface. It can show live work, ask and answer side questions, interrupt or steer the active task, review approvals, browse events, inspect memory, launch or switch models, link channels, and manage checkpoints without losing active agent state.

---

## Global Command Requirement

Raiker must install one human-facing global command named `raiker`.

```bash
raiker
```

Running `raiker` launches the Rich TUI. The TUI is the canonical place for normal user actions.

The global command must not require the user to choose separate primary modes such as ask/chat/tui. Those behaviours are modes and panels inside the TUI.

---

## TUI Action Model

The user acts inside the TUI through:

| Action surface | Example | Behaviour |
|---|---|---|
| Normal prompt input | `List files in this project` | Creates a normal prompt turn. |
| Side question input | `? What is it doing now?` | Creates read-only side turn bound to active task. |
| Slash command | `/models` | Opens a TUI panel or creates a structured action. |
| Approval card | Approve / deny / defer | Resolves exact pending action ID. |
| Model panel | `/launch --provider ollama --model qwen3.5-coder:9b` | Launches or switches model profile. |
| Channel panel | `/channels` | Lists, links, unlinks, and inspects connectors. |
| Memory panel | `/memory` | Searches and manages governed memory. |
| Graph panel | `/graph query --symbol ToolBroker` | Runs graph/codemap query through policy. |
| Checkpoint panel | `/checkpoints` | Inspect, restore, fork, export, or clean up checkpoints. |
| Diagnostics panel | `/doctor` | Runs diagnostics through approved checks. |

---

## Provider Launch From TUI

Model launch is a TUI action, not a separate primary user entry point.

Required TUI launch examples:

```text
/launch --provider ollama --model qwen3.5-coder:9b
/launch --provider llama.cpp --model /models/qwen.gguf --ctx 32768
/launch --provider lm-studio --model local-model
/launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
```

External provider adapters may expose convenience forms. For example, if a platform supports extension-style commands, an adapter may accept a shape such as:

```bash
ollama launch raiker --model <model>
```

That adapter must delegate into a Raiker model-launch action and record the equivalent TUI action in the event log:

```text
/launch --provider ollama --model <model>
```

The canonical human-facing Raiker command remains:

```bash
raiker
```

---

## Interface Modes

| Mode | Purpose | User access |
|---|---|---|
| `rich_tui` | Full terminal UI with panels and background tasks. | `raiker` |
| `prompt_turn` | One normal prompt action. | Type prompt inside TUI. |
| `side_question` | Ask about active task without stopping it. | Prefix input with `?` in TUI. |
| `model_launch` | Launch/switch model provider. | `/launch` inside TUI. |
| `channel_management` | Link/list/manage connectors. | `/channels` inside TUI. |
| `diagnostics` | Run health checks. | `/doctor` inside TUI. |
| `daemon` | Long-running local service used by channels/webhooks. | Managed from TUI/settings or service manager. |
| `headless` | Automation/test-only path. | Internal/test harness, not primary user UX. |

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
17. model launch/profile panel;
18. channel connector panel;
19. policy decision display;
20. keyboard shortcuts;
21. mouse support where available;
22. fallback plain terminal mode.

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
│ Side question / slash command / normal prompt / file mention     │
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

Safe boundaries include before tool execution, after tool completion, before file write, before local command execution, before checkpoint creation, and before subagent handoff.

---

## TUI Input Syntax

Raiker TUI input must support:

| Syntax | Meaning |
|---|---|
| Plain text | Normal prompt. |
| `/command` | Slash command. |
| `!command` | Local command proposal, never direct execution without policy. |
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
| `/channels` | Show paired channels and connector registry. |
| `/models` | Show model profiles. |
| `/launch` | Launch or switch model provider profile. |
| `/graph` | Query graph/codemap context. |
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
raw TUI input
  -> command parser
  -> UserPromptExpansion hook
  -> command permission check
  -> PromptEnvelope, UIActionEnvelope, or ToolAction proposal
  -> runtime
```

Command expansion must be event-logged.

---

## Background Task UI

A background task must expose task ID, title, status, current step, progress, started time, elapsed time, last event, pending approvals, side questions, changed files, output artifacts, and cancel/pause/steer controls.

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

Approvals must show exact tool/action, exact command/path/URL, risk level, policy reasons, file diff if file write/edit, network host if network, command classification, and choices: approve once, approve session, deny, defer, inspect.

No approval should be hidden in a stream of text. It must appear in approval inbox.

---

## File Mentions

`@path` mentions must resolve inside workspace unless allowed, show matched files before loading if ambiguous, require approval for large/binary/sensitive files, record provenance in context bundle, and never bypass policy.

---

## TUI Events

Required events:

- `tui_started`
- `tui_ready`
- `tui_panel_opened`
- `tui_prompt_submitted`
- `tui_command_submitted`
- `global_command_invoked`
- `model_launch_requested`
- `model_launch_completed`
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

- global `raiker` command launches the TUI;
- TUI prompt input creates a PromptEnvelope and reaches the gateway;
- provider launch through `/launch` maps to a model profile;
- command parser handles plain prompts, `/`, `!`, `@`, `?`;
- side question does not stop active task;
- interrupt changes active task state safely;
- approval choice binds to action ID;
- checkpoint selection triggers restore/fork flow;
- TUI can render with no colour/limited terminal;
- background task progress updates without corrupting transcript.
