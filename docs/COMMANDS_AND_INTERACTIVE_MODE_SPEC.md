# Commands And Equal Interface Mode Specification

Raiker must provide a rich interactive experience across all enabled interfaces, not a set of fragmented or privileged entry points.

CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled. No interface is canonical over another. All actions must enter through the same Agent Gateway, contracts, policy gates, event log, session state, approval binding, task controls, checkpoint model, memory governance, and runtime orchestration.

---

## Global Command Requirement

Raiker must install one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` launches the configured local terminal client, which may be implemented as a Rich TUI or a plain terminal client. This terminal client is one primary interface, not the canonical place for normal user actions.

The global command must not require the user to choose separate primary modes such as ask/chat/tui. Those behaviours are actions inside Raiker clients. This rule does not reduce the equal primary status of Desktop, Web, IDE, Voice, Hotkeys, REST, Webhooks, chat channels, Email, Browser Extension, Apple mobile app, Android mobile app, or Mobile Companion.

---

## Equal Interface Action Model

The user can act through any enabled primary interface. Each interface may use its own native UX, but the resulting action contract and runtime behaviour must be equivalent.

| Action surface | Terminal/Rich TUI example | Behaviour |
|---|---|---|
| Normal prompt input | `List files in this project` | Creates a normal prompt turn. |
| Side question input | `? What is it doing now?` | Creates read-only side turn bound to active task. |
| Slash command or action | `/models` | Opens a panel or creates a structured action. |
| Approval card/control | Approve / deny / defer | Resolves exact pending action ID. |
| Model panel/action | `/launch --provider ollama --model qwen3.5-coder:9b` | Launches or switches model profile. |
| Channel panel/action | `/channels` | Lists, links, unlinks, and inspects connectors. |
| Memory panel/action | `/memory` | Searches and manages governed memory. |
| Graph panel/action | `/graph query --symbol ToolBroker` | Runs graph/codemap query through policy. |
| Checkpoint panel/action | `/checkpoints` | Inspect, restore, fork, export, or clean up checkpoints. |
| Diagnostics panel/action | `/doctor` | Runs diagnostics through approved checks. |

---

## Provider Launch From Any Interface

Model launch is an interface-neutral Raiker action, not a TUI-only action.

Terminal launch examples:

```text
/launch --provider ollama --model qwen3.5-coder:9b
/launch --provider llama.cpp --model /models/qwen.gguf --ctx 32768
/launch --provider lm-studio --model local-model
/launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
```

Desktop, Web, IDE, mobile, voice, channel, and API clients must map the same launch operation into the same model-launch action contract.

External provider adapters may expose convenience forms. For example, if a platform supports extension-style commands, an adapter may accept a shape such as:

```bash
ollama launch raiker --model <model>
```

That adapter must delegate into a Raiker model-launch action and record the equivalent interface action in the event log:

```text
/launch --provider ollama --model <model>
```

The global local terminal command remains:

```bash
raiker
```

but it is not the only primary interface.

---

## Interface Modes

| Mode | Purpose | User access |
|---|---|---|
| `cli` | Local command-line client and terminal entry path. | `raiker` and approved terminal workflows. |
| `rich_tui` | Full terminal UI with panels and background tasks. | `raiker` default terminal renderer or configured terminal client. |
| `desktop` | Native desktop shell or local webview client. | Desktop app. |
| `web_ui` | Browser client with same gateway and event stream. | Local or authenticated remote web UI. |
| `dashboard` | Operational overview and control surface. | Web/Desktop/Mobile dashboard views. |
| `ide` | Editor extension with project context. | IDE extension side panel and command palette. |
| `voice` | Speech input/output with confirmation gates. | Voice UI. |
| `hotkeys` | Local OS shortcut surface. | Configured hotkey actions. |
| `rest` | Programmatic API surface. | Authenticated local/remote REST API. |
| `webhooks` | Signed inbound automation. | Paired webhook connector. |
| `email` | Mailbox-based interaction. | Paired mailbox connector. |
| `slack` | Workspace chat interaction. | Paired Slack connector. |
| `teams` | Microsoft Teams interaction. | Paired Teams connector. |
| `discord` | Discord server/channel interaction. | Paired Discord connector. |
| `signal` | Signal device/channel interaction. | Paired Signal connector. |
| `browser_extension` | Browser selected-page/context handoff. | Paired extension. |
| `apple_mobile` | iOS/iPadOS mobile app. | Apple mobile app. |
| `android_mobile` | Android mobile app. | Android mobile app. |
| `mobile_companion` | Cross-platform mobile companion capability. | Apple/Android app implementations. |
| `prompt_turn` | One normal prompt action. | Any enabled primary interface. |
| `side_question` | Ask about active task without stopping it. | Any enabled interface that supports side questions. |
| `model_launch` | Launch/switch model provider. | Any enabled interface with model controls. |
| `channel_management` | Link/list/manage connectors. | Any enabled interface with admin/channel settings. |
| `diagnostics` | Run health checks. | Any enabled interface with diagnostics capability. |
| `daemon` | Long-running local service used by channels/webhooks. | Managed from settings, service manager, or admin UI. |
| `headless` | Automation/test-only path. | Internal/test harness, not human UX. |

---

## Rich TUI Requirements

The Rich TUI is one equal-status primary interface. It must support:

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

This is a mandatory feature for every enabled interface that supports side questions.

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
4. It displays answer in the originating interface using that interface's side-question UX.
5. It can be promoted to steering instruction by user confirmation.
6. It must not reorder events in the main task.
7. It must be cancellable.

---

## Interrupt And Steering Controls

The user can interrupt active work with explicit controls from any enabled primary interface:

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

## Shared Input Syntax

Raiker interfaces must support these concepts. Terminal-like interfaces may use text syntax; GUI, mobile, chat, voice, and API clients may use equivalent buttons, cards, forms, commands, menus, voice transcripts, or request fields.

| Syntax | Meaning |
|---|---|
| Plain text | Normal prompt. |
| `/command` | Slash command or equivalent structured action. |
| `!command` | Local command proposal, never direct execution without policy. |
| `@path` | File or directory mention. |
| `#task` | Task reference. |
| `$memory` | Memory reference/search. |
| `%checkpoint` | Checkpoint reference. |
| `?question` | Side question shortcut. |
| `Ctrl+C` | Interrupt/pause flow, not silent crash. |
| `Ctrl+D` | Exit if safe or ask if task running. |

---

## Built-In Actions And Slash Commands

Slash commands are terminal syntax for interface-neutral actions. Every command below must have an equivalent action in every primary interface that exposes the relevant capability.

| Command | Purpose |
|---|---|
| `/help` | Show commands/actions. |
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

Slash commands and equivalent GUI/mobile/API actions expand into structured prompts or actions before reaching the runtime.

Expansion lifecycle:

```text
raw interface input
  -> interface parser or action mapper
  -> UserPromptExpansion hook
  -> command/action permission check
  -> PromptEnvelope, UIActionEnvelope, ChannelMessageEnvelope, or ToolAction proposal
  -> runtime
```

Command expansion must be event-logged and must include the originating interface/client metadata.

---

## Background Task UI

A background task must expose task ID, title, status, current step, progress, started time, elapsed time, last event, pending approvals, side questions, changed files, output artifacts, and cancel/pause/steer controls in every enabled interface that can display task state.

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

No approval should be hidden in a stream of text. It must appear in the approval surface native to the originating or currently active interface: approval inbox, card, drawer, mobile approval control, channel card, or authenticated API approval response.

---

## File Mentions

`@path` mentions and equivalent file picker, attachment, or selected-file inputs must resolve inside workspace unless allowed, show matched files before loading if ambiguous, require approval for large/binary/sensitive files, record provenance in context bundle, and never bypass policy.

---

## Interface Events

Required terminal/TUI events:

- `tui_started`
- `tui_ready`
- `tui_panel_opened`
- `tui_prompt_submitted`
- `tui_command_submitted`
- `global_command_invoked`
- `tui_exited`

Required interface-neutral events:

- `ui_session_opened`
- `ui_prompt_submitted`
- `ui_action_submitted`
- `ui_side_question_submitted`
- `ui_interrupt_requested`
- `ui_task_steer_submitted`
- `ui_approval_selected`
- `ui_checkpoint_selected`
- `ui_connector_link_started`
- `ui_model_launch_requested`
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

---

## Interface Testing Requirements

Tests must prove:

- global `raiker` command launches the local terminal client;
- terminal prompt input creates a PromptEnvelope and reaches the gateway;
- provider launch maps to a model profile regardless of originating interface;
- parser/action mapper handles plain prompts, commands/actions, local proposals, file references, and side questions;
- side question does not stop active task;
- interrupt changes active task state safely;
- approval choice binds to action ID;
- checkpoint selection triggers restore/fork flow;
- TUI can render with no colour/limited terminal;
- background task progress updates without corrupting transcript;
- every enabled primary interface uses the same gateway, contracts, policy, event log, and session state.
