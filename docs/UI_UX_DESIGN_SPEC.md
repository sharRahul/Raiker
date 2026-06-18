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

The default Rich TUI starts simple so Phase 1 can ship a small, safe terminal client without losing the future panel model. It must support a compact welcome/workspace view, recent activity, an input area, and a configurable status bar.

```text
┌──────── Raiker v0.0.0 ────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               │ Recent Activity:                                                                          │
│                               │ ✓ Inspect specs                                                                           │
│ Hello / Welcome back <user>   │ ▶ Update architecture                                                                     │
│                               │ • Verify docs                                                                             │
│         .-----------.         │                                                                                           │
|       .-░░▒▒░▒▒▒░▒▒░░-.       │───────────────────────────────────────────────────────────────────────────────────────────┤
│      (░░▒▒▒▒▓▓▓▒▒▒▓▓░░░)      │ What's new:                                                                               │
│     (░░▒▒▒▓▓▓▓▓▓▓▓▒▒▓▓▒░)     │                                                                                           │
│                               │                                                                                           │
│      <model> • <effort>       │                                                                                           │
│        <workspace>            │                                                                                           │
│                               │                                                                                           │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ > ? side question | / command | normal prompt | ! command proposal | @ file mention                                       │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ RUNNING | task:docs | approvals:2 | model:qwen | ctx: ███████░░░░░░░ 50% 18k/32k | mem:project | net:block              │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### TUI Status Bar

The TUI status bar must be configurable by user, project, workspace, managed policy, or terminal capability. The default field order is only a preset. Builders must implement the status bar as a list of named status items, not as one hard-coded string.

Default fields, left to right:

```text
STATE | task:<status> | approvals:<n> | model:<profile> | ctx_bar: ███████░░░░░░░ <used>% | ctx:<used>/<max> | mem:<scope> | net:<policy> | exec:<profile> | last:<event> | cost:<amount> | clock
```

Example:

```text
RUNNING | task:docs-expansion | approvals:1 | model:qwen9b | ctx_bar: ███████░░░░░░░ 50% | ctx:18k/32k | mem:project | net:blocked | exec:local | last:tool_completed | cost:£0.00 | 13:42
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
      "approvals",
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
| `minimal` | Small terminals and low-noise use | `state`, `task`, `approvals`, `model`, `clock` |
| `developer_compact` | Default local development | `state`, `task`, `approvals`, `model`, `context_percent_bar`, `context`, `network`, `last_event`, `clock` |
| `security_audit` | Security-heavy work | `state`, `task`, `approvals`, `policy`, `network`, `execution`, `last_event`, `checkpoint`, `cost`, `clock` |
| `model_debug` | Model/runtime debugging | `state`, `model`, `context_percent_bar`, `context`, `tokens_in_out`, `tool_calls`, `last_event`, `cost`, `clock` |

If terminal does not support colours, use text labels only. If terminal width is limited, prefer exact safety labels over decorative bars.

### TUI Panels

Required panels:

- Primary / Main Panel (Left);
- Activity Panel (Right);
- Input Panel;
- Status Bar Panel.

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

Supported panel regions:

```text
┌────────────────────────────── Raiker Session ──────────────────────────────┐
│ top_banner / notification strip                                            │
├───────────────┬──────────────────────────────────────────┬────────────────┤
│ left_drawer   │ main_workspace                           │ right_drawer   │
│ panels        │ transcript / selected panel / split view │ panels         │
├───────────────┴──────────────────────────────────────────┴────────────────┤
│ bottom_drawer / timeline / tool output / diff viewer                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ input_panel                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ status_bar                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

Optional panel catalogue:

| Panel | Purpose | Default region | Primary sources | Allowed actions |
|---|---|---|---|---|
| Active Plan | Show plan steps, status, blockers, next action. | `left_drawer` | runtime state, plan events | inspect step, ask side question |
| Approvals | Show pending approvals as cards, never inline-only text. | `right_drawer` | approval queue, policy events | approve, deny, defer, inspect |
| Task Progress | Show task status, elapsed time, safe boundaries, cancel/steer state. | `right_drawer` | tasks table, task events | pause, cancel, steer, side question |
| Tool/Event Stream | Show brokered tool calls and event timeline. | `bottom_drawer` | JSONL event log, events index | inspect event, copy event ID |
| Context/Memory/Graph | Show context sources, memory hits, graph references, trust labels. | `right_drawer` | context bundle, memory, graph | inspect provenance, request correction |
| Checkpoint Timeline | Show checkpoints, summaries, changed files, restore/fork options. | `bottom_drawer` | checkpoint service, event log | inspect, compare, restore, fork |
| Model/Profile Picker | Show model profiles, active model, local/hosted policy state. | `right_drawer` | model profile registry | launch/switch model via gateway action |
| Channel Connector List | Show connector profiles, enabled state, pairing status. | `right_drawer` | connector registry | link, unlink, inspect risk |
| Skill/Eidetic Memory Inspector | Show skill candidates, gist memory, raw observations, retention. | `right_drawer` | memory/eidetic tables | inspect, approve candidate, delete/request correction |
| Security/Policy Panel | Show policy decisions, denied actions, egress state, redactions. | `right_drawer` | policy engine, security events | inspect rule, open approval card |
| Diff Viewer | Show file diffs and snapshots for proposed edits. | `main_workspace` or `bottom_drawer` | checkpoint/file snapshot events | inspect diff, request explanation |
| Diagnostics Panel | Show health checks, registry errors, missing providers, DB state. | `main_workspace` | diagnostics actions, storage metrics | run approved diagnostic checks |
| Storage Panel | Show SQLite/event/checkpoint/artifact sizes. | `right_drawer` | storage metrics | inspect, export with approval |
| Custom User Panel | User-described panel generated from a panel manifest. | user choice | declared manifest sources | declared manifest actions |

Optional panel layout examples:

Active plan panel:

```text
┌─ Active Plan ─────────────────────┐
│ Objective: Update docs            │
│ ✓ Read README/docs map            │
│ ✓ Align architecture hand-off     │
│ ▶ Expand TUI optional panels      │
│ • Verify changed docs             │
│ Blockers: none                    │
└───────────────────────────────────┘
```

Approvals panel:

```text
┌─ Approvals ───────────────────────────────────────────┐
│ RISK: shell                                           │
│ Action: act_01H...                                    │
│ Command: pytest tests/test_policy_engine.py           │
│ Reason: shell_requires_approval                       │
│ Choices: [approve once] [deny] [defer] [inspect]      │
└───────────────────────────────────────────────────────┘
```

Tool/event stream panel:

```text
┌─ Tool / Event Stream ─────────────────────────────────┐
│ prompt_received       tui        13:41:02             │
│ action_proposed       grep       docs/**              │
│ policy_decision       allow      workspace_read       │
│ tool_completed        grep       18 matches           │
│ checkpoint_created    ckpt_01H   after turn           │
└───────────────────────────────────────────────────────┘
```

Context/memory/graph panel:

```text
┌─ Context / Memory / Graph ────────────────────────────┐
│ Context: 18.2k / 32k                                  │
│ Sources: prompt, docs/ARCHITECTURE.md, event_log      │
│ Trust: user_input, project_file, tool_result          │
│ Memory: 3 candidates, 0 durable writes pending        │
│ Graph: 12 nodes, 18 edges, 2 stale                    │
└───────────────────────────────────────────────────────┘
```

Panel rules:

1. A panel that only displays state may read from the event log, SQLite state, or gateway snapshots according to policy.
2. A panel that can mutate state must emit a `UIActionEnvelope` or approved action through the gateway.
3. A panel must not call tools, models, memory writes, plugin code, channel connectors, or execution environments directly.
4. Every panel open, close, focus, action, and error must be event-loggable.
5. Every panel must define a fallback text rendering for plain terminal and low-colour terminals.
6. User-built panels must be disabled by default until trusted or explicitly enabled.
7. Plugin-provided panels must follow plugin manifest, permission diff, and trust rules.
8. Panels must support keyboard navigation and must not trap focus during risky approval flows.
9. Panels must declare whether they can display sensitive data and whether export requires approval.
10. Panel state must be restorable from session/event/checkpoint state, not hidden UI memory only.

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
