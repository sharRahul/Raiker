# UI And UX Design Specification

Raiker must provide consistent UI behaviour across CLI, Rich TUI, Desktop UI, Web UI, Dashboard, IDE extension, Voice UI, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and channel clients.

Implementation is phased, but the user experience is fully specified now. No builder agent should invent how a screen, panel, status bar, connector wizard, dashboard widget, mobile view, approval surface, or channel interaction works.

---

## UI Principles

1. Every interface is a client of the same agent gateway.
2. No interface executes tools directly.
3. No interface is conceptually primary; every implemented and enabled interface can be the user's primary way to operate Raiker.
4. All interfaces expose the same core concepts: session, task, plan, tools, approvals, events, checkpoints, memory, context, models, channels, diagnostics, and policy.
5. All actions available in one primary interface must have an equivalent action path in every other primary interface that supports the relevant capability.
6. Long-running work is visible, interruptible, and cancellable.
7. The user can ask side questions without stopping running work.
8. Approvals are never hidden inside normal assistant text.
9. Risk, cost, model, memory, network, and execution environment must be visible.
10. UI actions map to explicit runtime commands/events.
11. Connector and model registries must be visible before their implementations are wired.
12. Implementations may prioritize specific interfaces (e.g., Desktop, Web) for usability and adoption while maintaining capability parity across all interfaces.

---

## Experience Levels And Progressive Disclosure

Raiker must support multiple user experience levels to reduce cognitive overload while preserving full system power.

### Objectives
- Prevent overwhelming new users
- Preserve expert-level control
- Enable gradual learning of system concepts

### Experience Levels

#### Beginner Mode (Default for new users)
- Shows: session, prompt, active task, approvals
- Hides: graph, memory internals, event stream, execution details
- Uses simplified language (e.g., "Running task" instead of "execution profile")
- Collapses advanced panels by default

#### Intermediate Mode
- Shows: tasks, plans, approvals, basic event visibility, context usage
- Introduces: tool activity summaries, checkpoint awareness
- Enables limited panel customization

#### Expert Mode
- Full UI exposure
- All panels available (graph, memory, diagnostics, event stream, policy)
- Full status bar fields
- Raw event visibility

### Rules
- Mode affects visibility, not capability
- All actions remain accessible via command or API
- Users may switch modes at any time
- Managed policy may enforce minimum visibility level

### Behaviour
- Progressive disclosure applies to:
  - Panels
  - Status bar fields
  - Event stream verbosity
  - Approval detail level
``
## Interface Parity Model

Raiker enforces capability parity across interfaces, not UI parity.

### Definitions

Capability parity:
- Every core action (task control, approvals, memory inspection, etc.) is available on all primary interfaces.

UI parity:
- Identical layouts and visual structures across interfaces (not required).

### Rules

- Interfaces may adapt presentation to their form factor:
  - Mobile uses cards and flows instead of panels
  - CLI uses structured text instead of visual grids
  - Voice uses summaries and confirmation flows

- Missing capabilities must:
  - Be explicitly disabled, or
  - Provide a handoff to a capable interface

- No interface may introduce unique capabilities unavailable elsewhere

### Principle

"Same system power, different interaction models"

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

### Default Mode Variants

The TUI must support preset complexity levels:

#### Minimal (default for small terminals)
- Single main panel (transcript)
- Input panel
- Compact status bar (state, task, approvals, model, clock)

#### Standard (developer default)
- Main panel + activity panel
- Input panel
- Full status bar (developer_compact preset)

#### Advanced
- Full panel system enabled
- Optional panels accessible
- Event stream expanded

### Default Layout

The default dynamic Rich TUI starts simple so Phase 1 can ship a small, safe terminal client without losing the future panel model. It must support a compact welcome/workspace view, recent activity, an input area, and a configurable status bar.

```text
┌──────── Raiker v0.0.0 ────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               │ Recent activity                                                                           │
│                               │ ✓ Inspect specs                                                                           │
│ Welcome back <user>!          │ ▶ Update architecture                                                                     │
│                               │ • Verify docs                                                                             │
│         .-----------.         │                                                                                           │
|       .-░░▒▒░▒▒▒░▒▒░░-.       │───────────────────────────────────────────────────────────────────────────────────────────┤
│      (░░▒▒▒▒▓▓▓▒▒▒▓▓░░░)      │ Tips for getting started                                                                  │
│     (░░▒▒▒▓▓▓▓▓▓▓▓▒▒▓▓▒░)     │                                                                                           │
│                               │                                                                                           │
│      <model> • <effort>       │                                                                                           │
│        <workspace>            │                                                                                           │
│                               │                                                                                           │
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  > ? side question / command                                   
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 
```

### Welcome bannner

Dynamic welcome banner where it can say Hello or Welcome.

### Configurable TUI Status Bar

The TUI status bar must be configurable by user, project, workspace, managed policy, or terminal capability. The default field order is only a preset. Builders must implement the status bar as a list of named status items, not as one hard-coded string.

Default fields, left to right:

```text
STATE | task:<status> | model:<profile> | ctx_bar: ███████░░░░░░░ <used>% | ctx:<used>/<max> | mem:<scope> | net:<policy> | exec:<profile> | last:<event> | cost:<amount> | clock
```

Example:

```text
RUNNING | task:docs-expansion | model:qwen9b | ctx_bar: ███████░░░░░░░ 50% | ctx:18k/32k | cost:£0.00 | mem:project | net:blocked | exec:local | last:tool_completed | 13:42
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

Configurable status item registry:

| Item ID | Example rendering | Source | Default visibility |
|---|---|---|---|
| `state` | `RUNNING` | Runtime state machine | required |
| `task` | `task:docs-expansion` | active task store | visible |
| `approvals` | `approvals:1` | approval queue | visible |
| `model` | `model:qwen9b` | model profile registry/router | visible |
| `context_percent_bar` | `ctx_bar: ███████░░░░░░░ 50%` | context budget tracker | visible |
| `context` | `ctx:18k/32k` | context budget tracker | visible |
| `memory` | `mem:project` | memory/context policy | visible |
| `network` | `net:blocked` | egress policy | visible |
| `execution` | `exec:local` | execution profile | visible |
| `last_event` | `last:tool_completed` | event stream | visible |
| `cost` | `cost:£0.00` | budget/cost tracker | visible when known |
| `clock` | `13:42` | local clock | visible |
| `workspace` | `ws:Raiker` | project/session metadata | optional |
| `branch` | `branch:main` | VCS metadata if available | optional |
| `checkpoint` | `ckpt:latest` | checkpoint service | optional |
| `policy` | `policy:default` | policy engine | optional |
| `tool_calls` | `tools:3/10` | runtime/tool broker | optional |
| `tokens_in_out` | `↑12k ↓425` | model/runtime token tracker | optional |

Configuration rules:

1. Required safety items such as `state`, `approvals`, `network`, and high-risk policy indicators must not be hidden during risky work.
2. User preference may reorder, hide, shorten, or expand non-safety items.
3. Project or managed policy may force security and audit fields to remain visible.
4. The renderer must degrade gracefully for narrow terminals by moving lower-priority fields into a compact overflow indicator such as `+4`.
5. The status bar must never show stale approval, stale policy, or stale network state after a task transition.
6. Every visible field must derive from gateway/runtime/event/store state, not private UI-only state.
7. `context_percent_bar` and `context` may be displayed together or separately; when shown together, the bar shows percentage used and `context` shows exact used/max values.

Example configuration shape:

```json
{
  "schema_version": "1.0",
  "status_bar": {
    "preset": "developer_compact",
    "fields": [
      "state",
      "task",
      "model",
      "context_percent_bar",
      "context",
      "network",
      "last_event",
      "clock"
    ],
    "pinned_fields": ["state", "approvals", "network"],
    "hide_when_idle": ["tool_calls", "cost"],
    "compact_below_columns": 100,
    "overflow_mode": "summary_count"
  }
}
```

Preset examples:

| Preset | Purpose | Fields |
|---|---|---|
| `minimal` | Small terminals and low-noise use | `state`, `task`, `model`, `clock` |
| `developer_compact` | Default local development | `state`, `task`, `model`, `context_percent_bar`, `context`, `cost`, `network`, `last_event`, `clock` |
| `security_audit` | Security-heavy work | `state`, `task`, `policy`, `network`, `execution`, `last_event`, `checkpoint`, `cost`, `clock` |
| `model_debug` | Model/runtime debugging | `state`, `model`, `context_percent_bar`, `context`, `tokens_in_out`, `tool_calls`, `last_event`, `cost`, `clock` |

If terminal does not support colours, use text labels only. If terminal width is limited, prefer exact safety labels over decorative bars.

### TUI Panels

Required panels:

- Primary / Main Panel (Left);
- Activity Panel (Right);
- Input Panel;
- Status Bar Panel  () .

The required panels form the minimum bootable TUI. Optional panels must be addable without creating a second runtime path, bypassing the gateway, or duplicating contracts.

#### Required layout shell

```text
┌────────────────────────────── Raiker Session ──────────────────────────────┐
│ Primary / Main Panel                 │ Activity Panel                      │
│ Transcript, welcome, active answer    │ Recent tasks, recent events, news   │
├───────────────────────────────────────┴─────────────────────────────────────┤
│ Input Panel: ? side question | / command | prompt | ! proposal | @ mention │
├─────────────────────────────────────────────────────────────────────────────┤
│ Status Bar Panel: configurable status items                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Optional panels (user can add and help user build)

Optional panels are user-buildable UI modules. They may be first-party, project-local, or plugin-provided in later phases, but they must behave as display/action surfaces over the same gateway, contracts, policy engine, event log, and store. The user should be able to ask Raiker to help build a panel by describing the panel purpose, data source, layout, actions, events, policy needs, and tests.

Panel build flow:

```text
User requests custom panel
  -> Raiker creates panel proposal
  -> identify data sources, contracts, actions, and events
  -> policy review for any action-capable panel
  -> generate panel manifest/config
  -> add tests or validation checklist
  -> load panel only if trusted/enabled
  -> panel reads from gateway/event/store state
```

Optional panel manifest shape:

```json
{
  "schema_version": "1.0",
  "panel_id": "panel.active_plan",
  "display_name": "Active Plan",
  "owner_scope": "builtin",
  "default_region": "left_drawer",
  "data_sources": ["runtime_state", "event_log"],
  "actions": ["inspect_step", "ask_side_question"],
  "requires_policy": false,
  "can_mutate_state": false,
  "events_consumed": ["plan_created", "task_progress", "turn_state_changed"],
  "events_emitted": ["ui_panel_opened"],
  "fallback_rendering": "text_table"
}
```

Side questions must be visually separated from the main task and must not overwrite streamed task progress.

## Transcript / Event Stream Behaviour

The transcript panel is a **structured, streaming event system** (not plain chat).

### Event Types

* Tool actions: `List(...)`, `Read(...)`, `Update(...)`, `Search(...)`, `Execute(...)`
* Reasoning steps: natural language explanations
* Results: summaries, outputs, diffs

### Visual Indicators

* `●` successful tool/action
* `○` reasoning/explanation step
* `⚠` warning or risk state
* `✖` failure state

### Behaviour

* Events stream **incrementally (token-level rendering)**
* Tool execution and reasoning are **interleaved**
* Each event is **atomic and traceable**
* No hidden actions — all system behaviour must be visible

## Hierarchical Tree Rendering

The interface supports structured, nested outputs using ASCII tree formatting.

### Characters

* `│` continuation
* `├` branch
* `└` final branch
* `|_` fallback rendering (low compatibility terminals)

### Example

```text
List(Modules/Tests)
│
├ Listed 57 paths
│
└ Read(file.swift)
  └ Read 85 lines
```

### Usage

* File and directory listings
* Execution breakdowns
* Nested tool outputs

## Expandable / Collapsible Nodes

Large outputs must be collapsible by default.

### Format

```text
└ Listed 57 paths (ctrl+r to expand)
```

### Behaviour

* Default: collapsed for large content
* Shows summary metadata:
  * item count
  * size (lines/files)
* Keyboard accessible (e.g. `ctrl+r`)
* Expansion must preserve hierarchy

## Inline Diff Viewer

File updates must render inline as structured diffs.

### Format

```diff
- import WordPressShared
+ @testable import WordPressShared
```

### Behaviour

* Syntax highlighted code
* Line numbers preserved
* Color semantics:
  * Removed -> red (`-`)
  * Added -> green (`+`)
* Expandable for large diffs
* Scrollable within block

## Tool / Event Integration Model

Tool execution is embedded directly into the transcript (no separate panel required).

### Rules

* Every tool call appears as a first-class event
* Must include:
  * Action name
  * Target resource
  * Summary result
* Detailed output is collapsible

### Example

```text
● Read(file.swift)
└ Read 85 lines (ctrl+r to expand)
```

## Live Execution Indicator

Displays real-time operation status above the input.

### Format

```text
☁ Searching... (27s • ↓ 425 tokens • esc to interrupt)
```

### Fields

* Activity label (Searching, Generating, Updating)
* Elapsed time
* ↑ ↓ for Token input and output
* Token usage
* Interrupt hint

### Behaviour

* Updates in real time
* Replaces itself per active task
* Disappears when task completes

## Command Input Behaviour

### Prompt Modes

* `?` -> side question
* `/` -> command
* `!` -> command proposal
* `@` -> file or entity reference
* default -> normal prompt

### Behaviour

* Real-time input parsing
* Supports command + natural language mixing
* Context-aware suggestions if supported

## Side Question Handling

Side questions must not interrupt or overwrite active tasks.

### Rules

* Rendered in **separate visual context**
* Do not mutate:
  * current task state
  * execution stream
* Status bar switches to `SIDE-Q`

## Approval Mode System

### Indicator

```text
▶ auto-accept edits: ON (shift+tab to cycle)
```

### Modes

* `manual` -> explicit approval required
* `auto-accept` -> changes applied automatically only where policy permits

### Behaviour

* Always visible to user
* Keyboard toggle supported
* Applies only to mutating actions where policy explicitly permits it
* Must not override approval requirements for high-risk command, delete, export, network, memory, plugin, channel, remote execution, or managed-policy actions

## Execution & Interruptibility

### Behaviour

* All long-running operations must be interruptible
* Interrupt via `esc`
* Partial results must be preserved when interrupted

## Streaming Model

### Behaviour

* Output appears incrementally, not batch-rendered
* Supports:
  * partial reasoning
  * progressive tool results
* Ensures low-latency feedback loop

## Tool Feedback & Summaries

Each tool must return:

* **Summary line, always visible**
* **Detailed output, collapsible**

### Example

```text
● Update(file.swift)
└ Updated with 1 addition and 1 removal
```

## Status Bar Behaviour

The status bar reflects **real-time system state** and is configured from the status item registry defined above.

### Dynamic Updates

* `STATE` changes per lifecycle
* `task` reflects current activity
* `approvals` increments when user action required
* `context_percent_bar` updates the visual percentage-used bar from the active context budget
* `context` updates the exact used/max token numbers from the active context budget
* `last` shows most recent event
* `cost` accumulates usage where available
* configured fields re-render when their backing event/store state changes

### Context Usage Bar

```text
ctx_bar: ███████░░░░░░░ 50%
ctx:18k/32k
```

* Updates continuously
* Visual + numeric percentage representation through `context_percent_bar`
* Exact used/max representation through `context`
* Falls back to `ctx_bar: 50%` and `ctx:18k/32k` when block rendering is unavailable

## Window Header Behaviour

### Format

```text
<view name> (#<session/task id>)
```

### Behaviour

* Updates when switching context/session
* Provides persistent orientation

## Enterprise / Audit Behaviour

* All actions must be:
  * visible
  * timestampable
  * reproducible
* No silent background execution
* Network policy must be honoured and reflected (`net:blocked/open`)
* Approval-sensitive operations must respect mode and policy

## Core Interaction Principles

1. **Transparency** — every action is observable
2. **Interleaving** — reasoning + execution coexist
3. **Progressive disclosure** — collapse complexity by default
4. **Interruptibility** — user retains control at all times
5. **Traceability** — full audit trail in transcript
6. **Consistency** — all tools follow same event model

## Cognitive Load Constraints

The UI must actively prevent overload during normal operation.

### Constraints

- No more than:
  - 2 primary panels visible by default
  - 1 active high-attention task at a time
  - 1 approval card in focus at a time

- Large outputs must always:
  - Be collapsed by default
  - Include summary metadata

- Status bar:
  - Must not exceed terminal width without overflow handling
  - Must prioritize safety-critical fields

### Progressive Reveal

Complex elements are introduced only when:
- User interacts with them
- A task requires them
- User switches to higher experience mode

### Anti-Patterns (must be avoided)

- Full system state shown at startup
- Inline approvals buried in text
- Simultaneous panel overload
- Hidden system actions


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
┌──────────────────── Raiker Desktop ──────────────────────────────────────────────┐
│ Sidebar                      │ Main Workspace                                    │
│ ─ Sessions                   │ - Welcome / Active Session                        │
│ ─ Active Tasks               │ - Completed / Pending / Recent Tasks              │
│ ─ Approvals                  │ - Approved / Rejected / Pending Approvals         │
│ ─ Memory                     │ - Recent Memory Update / Project Context          │
│ ─ Eidetic Observations       │ - Retention / Replay                              │
│ ─ Graph                      │ - Quick Actions                                   │
│ ─ Channels                   │ - Link / Unlink                                   │
│ ─ Models                     │ - Launch / Switch                                 │
│ ─ Plugins                    │ - Registry / Risk                                 │
│ ─ Settings                   │                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
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

### Mobile Adaptation Model

Mobile UI is not a compressed desktop UI. It is a flow-based interface.

### Design Rules

- Replace panels with:
  - Cards
  - Drill-down views
  - Swipe navigation

- Use navigation hierarchy:
  - Home → Session → Task → Detail View

- High-risk actions:
  - Must require explicit confirmation
  - Must display full context before approval

- Event stream:
  - Summarized by default
  - Expandable per event

- Graph, diagnostics, and large datasets:
  - Must use summarized views or deep-link handoff

### Principle

"Focus over density — one decision per screen"


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
- `ui_panel_closed`
- `ui_panel_focused`
- `ui_panel_action_submitted`
- `ui_status_bar_config_loaded`
- `ui_status_bar_config_changed`
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
- configurable status bar loads default and user/project overrides;
- safety-critical status fields remain visible during risky work;
- status bar updates from events;
- optional panels render in fallback text mode;
- optional panel actions route through `UIActionEnvelope` and the gateway;
- user-built panel manifests are validated before loading;
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

## Phase 3 read-only workspace parity foundation

Before a desktop app, web server, or dashboard runtime is activated, those clients must use the same read-only workspace inspection contract as terminal inspection commands. No UI client may receive a privileged path to tools, approvals, plugin execution, semantic-memory writes, channels, or remote/container execution.


## Phase 3 rollout slice B read-only workspace views

Future terminal, desktop, web, and dashboard clients consume the same read-only workspace inspection contract. The current implementation provides deterministic local renderers only: JSON-safe workspace data, terminal text, dashboard summary, client capability summary, and plugin-plan summary. This is not a full desktop application, a web server, or a privileged dashboard runtime.

## Phase 3 Slice E Approval-preview UX

Approval-preview UI surfaces make future graph indexing and semantic memory writes visible before any execution path exists.

CLI surfaces:

- `/approval-previews` lists preview availability and explicitly states previews are not persisted in Slice E.
- `/graph-approval-preview` renders a fresh dry-run graph indexing approval preview.
- `/memory-approval-preview [--summary]` renders memory preview details or summary from review candidates.
- `/approval-preview <preview_id>` returns a helpful non-persistence message for Slice E instead of pretending durable preview lookup exists.

Workspace surfaces include `approval_preview_summary` with graph/memory preview availability, pending/denied counts, `preview_only_mode=true`, and `runtime_execution_enabled=false`.

These previews are not executable approvals. Graph indexing and semantic/vector memory writes remain disabled; no plugin, external channel, remote execution, container execution, subagent, or multi-agent path is activated.

## Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled; no embeddings or vectors are created.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Graph indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- Rollback execution remains disabled.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.

## Implementation Phases (UX Scope)

### Phase 1 — Core Usability (Must Ship)
- Prompt input + transcript
- Task execution visibility
- Approval system (explicit and safe)
- Basic status bar (state, task, approvals, model)
- Minimal TUI and basic desktop/web UI

### Phase 2 — Observability And Control
- Event stream (structured)
- Checkpoints and restore
- Context usage visibility
- Basic panels (approvals, task progress)

### Phase 3 — Advanced System Features
- Memory + graph UI
- Plugin panels
- Diagnostics and storage views
- Dashboard

### Phase 4 — Power User Ecosystem
- Custom panels
- Full panel manifests
- Advanced debugging and audit tools

### Rule

No phase may introduce UI that:
- Bypasses the gateway
- Hides system actions
- Breaks consistency across interfaces

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Raiker uses `httpx.AsyncClient` for async model transport and does not use the OpenAI SDK or Pydantic. FastAPI, LangChain, and LlamaIndex are deferred because no governed API, agent-framework, or retrieval integration is implemented in this change. llama.cpp is local-first through the async OpenAI-compatible path; Ollama, LM Studio, vLLM, generic endpoints, and OpenRouter are OpenAI-compatible profiles. OpenRouter is hosted and policy-gated. The deterministic provider is test-only, and production does not fall back to deterministic providers or silently switch from local to hosted providers.

Event/status labels distinguish `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Emitted model events must contain only safe metadata: provider, profile_id, model, endpoint_kind, duration_ms, finish_reason, tool_call_count, text_length, usage summary, error_class, safe_error_code, capability booleans, and reasoning settings. Raw prompts, completions, streamed chunks, Authorization headers, API keys, file contents, and tool outputs are not event payload material.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI | Live single-panel Textual TUI implemented (Slice Q4): one full-width scrolling transcript, live execution indicator, live status bar, input box, and real keyboard shortcuts, with token-by-token streaming via the gateway streaming path. Claude-Code-style — no simultaneously docked side/region panels. Inspection views (approvals, tasks, events, memory/graph, …) render inline on demand and remain display-only over existing handlers. `RAIKER_TUI=rich` keeps the turn-based single-panel shell; `=plain` the plain loop. | Yes | No direct tool authority; prompts stream through gateway/broker/policy; tools still require approval. | Stream tool-call deltas once providers emit them; optional docked panels remain deferred. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |



## Phase 3 Slice Q1 — Documented Default Rich TUI Access Shell (implemented)

The documented default layout above (Primary / Main Panel, Activity Panel, Input Panel, and
Status Bar Panel) is implemented as Raiker's default access shell in
`raiker/tui/`. Q1 implements the documented default layout only; the optional/advanced panel
catalogue, dockable drawers, and dashboard-style multi-pane views remain specified and
deferred. The shell adapts to standard, narrow, and no-colour/ASCII terminals and falls back
to a plain terminal loop when rich is unavailable, the terminal is non-interactive, or
`RAIKER_TUI=plain` is set. It creates no new runtime authority and adds no new events or
storage. See `docs/completed/PHASE_3_SLICE_Q1_RICH_TUI_DEFAULT_ACCESS_SHELL_SPEC.md`.

## Phase 3 Slice Q2 — Interactive Rich TUI With Optional Panels (implemented)

Building on Q1, the interactive Rich TUI now implements the documented region-based panel
system in `raiker/tui/`: a window header, left/right/bottom drawers, a main workspace with
a structured streaming transcript (event indicators `● ○ ⚠ ✖`, hierarchical tree
rendering, collapsible large output, inline diffs), the input panel with prompt modes
(`?` side question, `/` command, `!` command proposal, `@` file mention, default prompt),
and the configurable status bar. The optional panel catalogue (Active Plan, Approvals,
Task Progress, Tool/Event Stream, Context/Memory/Graph, Checkpoint Timeline, Model Picker,
Channels, Skill/Eidetic, Security/Policy, Diff Viewer, Diagnostics, Storage) is implemented
as **read-only display surfaces** over the existing command handlers and local store, with
the documented optional-panel manifest shape. Mode variants (`minimal`/`standard`/
`advanced`) and the documented keyboard shortcuts are available, each shortcut mapped to an
equivalent typed command for capability parity.

This slice adds no new runtime authority, events, or storage. Panels never call tools,
models, plugins, channels, memory/graph writes, or remote/container execution; every
mutating action remains a user-issued command routed through the gateway, broker, policy,
approvals, and disabled-runtime gates. Side questions never mutate task state, and `!`
command proposals are surfaced for review only and never executed while runtime execution
is disabled. Plugin-provided and user-built custom panels remain deferred. See
`docs/PHASE_3_SLICE_Q2_RICH_TUI_FULL_SHELL_SPEC.md`.

## Phase 3 Slice Q3 — Live Streaming Textual TUI (implemented)

Q3 adds the live, key-driven front-end and the streaming path the turn-based shell lacked.
A streaming contract (`raiker/contracts/streaming.py`) and a single DRY runtime turn loop
let `RuntimeOrchestrator.astream_handle` and `AgentGateway.astream_prompt` yield text
deltas, mirrored lifecycle events, and a final response incrementally, while the
synchronous `ahandle`/`submit_prompt` paths stay byte-for-byte unchanged. The new Textual
app (`raiker/tui/textual_app.py`, dependency `textual>=0.60`) is a real repainting TUI: a
scrollable transcript that appends streamed tokens live, drawer panels from the read-only
optional-panel catalogue, a live status bar, and real keyboard shortcuts (Ctrl+A/T/E/M/G/K,
Ctrl+P, Ctrl+L, Shift+Tab, etc.). `run_terminal_client` prefers Textual when available;
`RAIKER_TUI=rich` selects the Slice Q2 turn-based shell and `=plain` the plain loop.

Safety is unchanged: prompts stream through the same gateway/broker/policy/approval path,
tool execution still requires policy and approval, `!` command proposals are surfaced but
never executed, and offline the stream fails safe with `model_unavailable` while still
finalising the turn (checkpoint + turn close). See
`docs/PHASE_3_SLICE_Q3_LIVE_STREAMING_TEXTUAL_TUI_SPEC.md`.

## Phase 3 Slice Q4 — Single-Panel Default Layout (implemented; supersedes Q1–Q3 multi-panel UX)

Q4 removes the multi-panel/region UX from the implemented Rich TUI and reduces it to a
single default layout, like Claude Code: one full-width scrolling transcript, a live
execution indicator, the input box, and a single configurable status bar. There are no
simultaneously docked side/region drawers, no `minimal`/`standard`/`advanced` mode
variants, and no panel focus cycling. This replaces the Q1 two-column default access shell,
the Q2 left/right/bottom drawer regions, and the Q3 right-drawer panels.

All capabilities are preserved. The optional-panel catalogue is retained as a read-only
**inspection view** catalogue: each view (approvals, tasks, events, context/memory/graph,
checkpoints, model picker, channels, skill/eidetic, security/policy, diff, diagnostics,
storage) renders **inline into the transcript, once, on demand** via `/view <id>` (alias
`/panel <id>`) or a keyboard shortcut (Ctrl+A/T/E/M/G/K), instead of occupying a persistent
docked region. Prompt modes (`?` `/` `!` `@` + default), streaming, the structured event
transcript (`● ○ ⚠ ✖`, tree rendering, collapsible output, inline diffs), command-palette,
history, and approval-mode cycling (Shift+Tab) are unchanged.

Removed code: `raiker/tui/default_layout.py` and `raiker/tui/panels.py` (two-column
renderers); the region/panel/focus/mode machinery in `raiker/tui/session.py`; the
left/right/bottom drawer rendering in `raiker/tui/layout.py`; and the right drawer plus
focus/mode-cycle actions in `raiker/tui/textual_app.py`. The `Tab` (cycle panels) and
`/close`, `/focus`, `/mode` commands are gone; `/views` lists inline views.

Safety is unchanged: no new runtime authority, events, or storage; views never call tools,
models, plugins, channels, or memory/graph writes; every mutating action remains a
user-issued command routed through the gateway, broker, policy, approvals, and
disabled-runtime gates. Optional docked panels and user-built/plugin panels remain
specified and deferred.
