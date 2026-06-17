# UI And UX Design Specification

Raiker must provide consistent UI behaviour across CLI, Rich TUI, Desktop UI, Web UI, Dashboard, IDE extension, Voice UI, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and channel clients.

Implementation is phased, but the user experience is fully specified now. No builder agent should invent how a screen, panel, status bar, connector wizard, dashboard widget, mobile view, approval surface, or channel interaction works.

---

## UI Principles

1. Every interface is a client of the same agent gateway.
2. No interface executes tools directly.
3. No interface is primary over another; every implemented and enabled interface can be the user's primary way to operate Raiker.
4. All interfaces expose the same core concepts: session, task, plan, tools, approvals, events, checkpoints, memory, context, models, channels, diagnostics, and policy.
5. All actions available in one primary interface must have an equivalent action path in every other primary interface that supports the relevant capability.
6. Long-running work is visible, interruptible, and cancellable.
7. The user can ask side questions without stopping running work.
8. Approvals are never hidden inside normal assistant text.
9. Risk, cost, model, memory, network, and execution environment must be visible.
10. UI actions map to explicit runtime commands/events.
11. Connector and model registries must be visible before their implementations are wired.

---

## Shared UI Information Architecture

All primary interfaces should provide access to:

```text
Home
  Sessions
  Active Tasks
  Approvals
  Tools
  Events
  Checkpoints
  Memory
  Eidetic Observations
  Skills
  Graph / Codemap
  Models
  Plugins
  Hooks
  Channels
  Execution Environments
  Settings
  Diagnostics
```

Small-screen, voice, chat, and API clients may expose these through navigation flows, cards, command palettes, action sheets, structured requests, or delegated deep links instead of showing every region at once.

---

## Rich TUI Design

The Rich TUI is one equal-status primary interface. It is not the primary human interface over Desktop, Web, IDE, Voice, Hotkeys, REST, Webhooks, channel clients, Browser Extension, Apple mobile app, Android mobile app, or Mobile Companion.

### Default Layout

```text
┌──────────────────────────────────────── Raiker v0.0.0────────────────────────────────────────┐
│ Session: sess_abc  Project: Raiker  Branch: main  Mode: Plan+Act                       │
│ Model: qwen-local  Context: 18.2k/32k  Policy: default  Net: blocked  Mem: project     │
├───────────────────────────────┬──────────────────────────────┬─────────────────────────┤
│ Transcript                    │ Active Plan                  │ Approvals               │
│ User: Add docs...             │ ✓ Inspect specs              │ pending: command check   │
│ Assistant: Working...         │ ▶ Update architecture         │ pending: file snapshot   │
│ Side Q: What is it doing?     │ • Verify docs                │                         │
├───────────────────────────────┼──────────────────────────────┼─────────────────────────┤
│ Tool / Event Stream           │ Task Progress                │ Context / Memory / Graph │
│ action_proposed write_file    │ Task: docs expansion         │ Sources: 12              │
│ policy_decision allow         │ Step 3/7  █████░░ 43%        │ Memory hits: 5           │
│ checkpoint_created ckpt_123   │ Elapsed: 00:08:42            │ Graph nodes: 27          │
├───────────────────────────────┴──────────────────────────────┴─────────────────────────┤
│ ? side question | / command | normal prompt | ! command proposal | @ file mention       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ RUNNING | task:docs | approvals:2 | model:qwen | ctx:18k/32k | mem:project | net:block │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### TUI Status Bar

Required fields, left to right:

```text
STATE | task:<status> | approvals:<n> | model:<profile> | ctx:  ███████░░░░░░░ <used>% <used>/<max> | mem:<scope> | net:<policy> | exec:<profile> | last:<event> | cost:<amount> | clock
```

Example:

```text
RUNNING | task:docs-expansion | approvals:1 | model:qwen9b | ctx: ███████░░░░░░░ 50% 18k/32k | mem:project | net:blocked | exec:local | last:tool_completed | cost:£0.00 | 13:42
```

Status labels:

| State | Meaning |
|---|---|
| `READY` | Waiting for user input. |
| `RUNNING` | Task is active. |
| `WAITING` | Waiting for approval/user answer. |
| `RISK` | High-risk action proposed. |
| `FAILED` | Current task failed. |
| `PAUSED` | Task paused. |
| `SIDE-Q` | Side question mode active. |

If terminal does not support colours, use text labels only.

### TUI Panels

Required panels:

- Transcript panel;
- Active plan panel;
- Approvals panel;
- Task progress panel;
- Tool/event stream panel;
- Context/memory/graph panel;
- Checkpoint timeline;
- Model/profile picker;
- Channel connector list;
- Skill/eidetic memory inspector.

Side questions must be visually separated from the main task and must not overwrite streamed task progress.

---

## TUI Keyboard Shortcuts

| Shortcut | Behaviour |
|---|---|
| `Ctrl+C` | Request interrupt/pause at safe boundary. |
| `Esc` | Cancel current input or open interrupt menu. |
| `Esc Esc` | Open rewind/checkpoint menu. |
| `Ctrl+L` | Clear/redraw screen. |
| `Ctrl+R` | Resume/fork session picker. |
| `Ctrl+P` | Command palette. |
| `Ctrl+A` | Approvals inbox. |
| `Ctrl+T` | Task manager. |
| `Ctrl+E` | Event viewer. |
| `Ctrl+M` | Memory inspector. |
| `Ctrl+G` | Graph/codemap inspector. |
| `Ctrl+K` | Context usage panel. |
| `Tab` | Cycle panels. |
| `Shift+Tab` | Cycle permission mode. |
| `?` prefix | Side question. |

---

## Desktop UI Design

Desktop UI is an equal primary local application shell around the same gateway.

### Desktop Home Screen

```text
┌──────────────────── Raiker Desktop ────────────────────┐
│ Sidebar                      │ Main Workspace            │
│ ─ Sessions                   │ Welcome / Active Session  │
│ ─ Active Tasks               │ Recent Tasks              │
│ ─ Approvals                  │ Pending Approvals         │
│ ─ Memory                     │ Project Context           │
│ ─ Eidetic Observations       │ Retention / Replay        │
│ ─ Graph                      │ Quick Actions             │
│ ─ Channels                   │ Link / Unlink             │
│ ─ Models                     │ Launch / Switch           │
│ ─ Plugins                    │ Registry / Risk           │
│ ─ Settings                   │                           │
└─────────────────────────────────────────────────────────┘
```

### Desktop Active Session Screen

Required regions:

- transcript;
- plan timeline;
- task cards;
- approvals drawer;
- file diff viewer;
- checkpoint timeline;
- memory/context drawer;
- graph/codemap drawer;
- side-question input;
- channel connector drawer;
- status bar.

Desktop status bar:

```text
Session sess_abc | Task running | Model qwen-local | Context 18k/32k | Net blocked | Exec local | Approvals 1 | Checkpoint ckpt_123
```

Notifications must open the relevant panel, not just show text.

---

## Web UI Design

Web UI is an equal primary browser client using the same gateway and event stream. It may be local-only or authenticated remote depending on deployment policy.

Layout:

```text
Top Nav: Project | Session | Model | Policy | Search | User
Left Nav: Sessions, Tasks, Approvals, Memory, Eidetic, Graph, Tools, Plugins, Channels, Settings
Main: Transcript / Dashboard / Inspector
Right Drawer: Context, Plan, Approval, Memory, Graph, Event Details
Bottom: Prompt / Side Question / Command Bar
```

Web session page components:

- transcript stream;
- plan timeline;
- running tasks;
- approval cards;
- tool output viewer;
- file diff viewer;
- checkpoint timeline;
- side-question bar;
- event timeline;
- channel connector wizard;
- model launch panel.

Web security requirements:

- local-only mode by default;
- CSRF protection if browser server exists;
- auth for remote access;
- websocket/SSE event stream auth;
- no approval relay without trusted session;
- attachments scanned before context use;
- CORS locked down.

---

## Mobile App Design: Apple And Android

Apple mobile app and Android mobile app are equal primary interfaces, not secondary companions. They must support the same Raiker action set within a mobile-native UX.

Mobile required screens:

1. Home / active session list.
2. Active session transcript.
3. Prompt and side-question composer.
4. Task progress and background task cards.
5. Approval inbox with exact action binding.
6. Checkpoint timeline with restore/fork controls.
7. Memory and context inspector.
8. Graph/codemap query view or deep-link handoff.
9. Models screen for launch/switch/status.
10. Channels screen for link/unlink and pairing.
11. Diagnostics screen.
12. Settings and security policy summary.

Mobile-specific requirements:

- push notifications for task updates and approvals;
- approval actions require authenticated device/session state;
- high-risk approvals must show exact action ID, arguments, risk reasons, and changed files or target host when applicable;
- mobile must support pause, cancel, steer, approve, deny, defer, rewind, fork, and side questions;
- offline or stale mobile state must not approve actions until refreshed against the gateway;
- attachments, photos, files, shared links, and selected text are untrusted inputs and must pass normal attachment/context policy;
- Apple and Android implementations must use the same contracts and event types.

---

## Dashboard Design

Dashboard is an equal primary operational overview and control surface for Raiker. It may appear in Web, Desktop, Mobile, or a dedicated dashboard client.

| Widget | Shows |
|---|---|
| Active Tasks | Running, waiting, failed, completed tasks. |
| Approvals | Pending risky actions. |
| Model Usage | Model profile, context, latency, local/remote. |
| Tool Activity | Recent tools, failures, denied actions. |
| Checkpoints | Recent checkpoints and restore options. |
| Memory Health | Candidates, stale records, corrections, poisoning warnings. |
| Eidetic Retention | Raw observations, expiry, deletion, exact replay warnings. |
| Skill Learning | Skill candidates, proposals, verification status. |
| Graph Index | Last index time, stale files, node/edge counts. |
| Channels | Connector profiles, paired channels, inbound messages. |
| Plugins | Enabled plugins, permission warnings. |
| Security | OWASP control alerts, policy blocks, secret redactions. |
| Storage | SQLite DB size, vector index size, event log size. |
| Execution | Running processes, environment profile, resource usage. |

Dashboard layout:

```text
┌────────────────────── Raiker Dashboard ──────────────────────┐
│ Health: OK | Tasks: 2 running | Approvals: 1 | Security: 0 critical │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│ Active Tasks │ Approvals    │ Model Usage  │ Security Alerts │
├──────────────┼──────────────┼──────────────┼─────────────────┤
│ Memory       │ Eidetic      │ Graph Index  │ Checkpoints     │
├──────────────┼──────────────┼──────────────┼─────────────────┤
│ Channels     │ Plugins      │ Storage      │ Execution       │
└──────────────┴──────────────┴─────────────────────────────────┘
```

---

## IDE Extension Design

IDE extension is an equal primary project-aware interface. It must provide side panel transcript, inline file diff previews, diagnostics integration, symbol/context picker, approval prompts, checkpoint/rewind from editor, command palette, task status badge, and no direct tool execution outside gateway.

---

## Voice UI Design

Voice is an equal primary interface where enabled, but high-risk actions still require policy-compliant confirmation and may require visual handoff depending on policy.

Requirements:

- push-to-talk and wake mode;
- speech-to-text local-first;
- confirmation for risky actions;
- spoken summaries;
- screen, mobile, web, desktop, or TUI handoff for approvals when policy requires visual review;
- no voice-only approval for high-risk command/write/delete unless policy permits;
- transcript stored as normal channel message.

---

## Channel And Chat UI Design

Slack, Teams, Discord, Signal, Email, Webhooks, REST, Browser Extension, and other channel clients are equal primary interfaces when linked and enabled. They must expose the same action set as far as their transport and security profile allow, and any missing capability must be represented as an explicit disabled or handoff state rather than silently omitted.

Channel clients must support:

- session binding;
- sender trust display;
- prompt submission;
- side questions where supported;
- task status updates;
- approval handoff or relay according to policy;
- attachment provenance;
- rate-limit feedback;
- channel unlink/revoke flow.

---

## UI Event Model

Every UI action maps to runtime events:

- `ui_session_opened`
- `ui_panel_opened`
- `ui_prompt_submitted`
- `ui_side_question_submitted`
- `ui_interrupt_requested`
- `ui_approval_selected`
- `ui_checkpoint_selected`
- `ui_memory_record_opened`
- `ui_graph_node_opened`
- `ui_task_cancel_requested`
- `ui_task_steer_submitted`
- `ui_connector_link_started`
- `ui_model_launch_requested`
- `mobile_session_opened`
- `mobile_push_sent`
- `mobile_approval_selected`

---

## UI Testing Requirements

Tests must prove:

- TUI renders in small terminal;
- status bar updates from events;
- side question does not pause task;
- approval card binds to action ID;
- checkpoint timeline opens restore flow;
- dashboard widgets derive from event/store state;
- desktop/web/mobile clients call gateway only;
- remote web UI requires auth before event stream;
- mobile approval cannot be submitted from stale state;
- channel connector wizard reads `config/channel-connectors.json`;
- model launch panel reads `config/model-profiles.json`;
- every enabled primary interface can create equivalent prompt, side-question, approval, task-control, model, channel, memory, graph, diagnostics, and checkpoint actions through shared contracts.
