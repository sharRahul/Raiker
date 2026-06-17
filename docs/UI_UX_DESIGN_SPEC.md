# UI And UX Design Specification

Raiker must provide consistent UI behaviour across CLI, Rich TUI, Desktop UI, Web UI, Dashboard, IDE extension, and channel clients.

The implementation may be phased, but the user experience must be fully specified now. No builder agent should invent how a screen, panel, status bar, or dashboard works.

---

## UI Principles

1. Every interface is a client of the same agent gateway.
2. No interface executes tools directly.
3. All interfaces expose the same core concepts: session, task, plan, tools, approvals, events, checkpoints, memory, context, models, and policy.
4. Long-running work is visible, interruptible, and cancellable.
5. The user can ask side questions without stopping running work.
6. Approvals are never hidden inside normal assistant text.
7. Risk, cost, model, memory, network, and execution environment must be visible.
8. UI actions map to explicit runtime commands/events.

---

## Shared UI Information Architecture

All rich clients should provide access to:

```text
Home
  Sessions
  Active Tasks
  Approvals
  Tools
  Events
  Checkpoints
  Memory
  Graph / Codemap
  Models
  Plugins
  Hooks
  Channels
  Execution Environments
  Settings
  Diagnostics
```

---

## Rich TUI Design

The Rich TUI is the primary power-user interface.

### Default Layout

```text
┌──────────────────────────────────────── Raiker ────────────────────────────────────────┐
│ Session: sess_abc  Project: Raiker  Branch: docs/local-llm-blueprint  Mode: Plan+Act     │
│ Model: qwen-local-coder  Context: 18.2k/32k  Policy: default  Net: blocked  Mem: project │
├───────────────────────────────┬──────────────────────────────┬─────────────────────────┤
│ Transcript                    │ Active Plan                  │ Approvals               │
│ ───────────────────────────── │ ───────────────────────────  │ ─────────────────────── │
│ User: Add full UI docs...     │ ✓ Read reference docs        │ pending: shell pytest    │
│ Assistant: Working...         │ ✓ Add UI spec                │ pending: file snapshot   │
│ Tool: write_file docs/...     │ ▶ Add storage spec           │                         │
│ Side Q: What is it doing?     │ • Update roadmap             │                         │
├───────────────────────────────┼──────────────────────────────┼─────────────────────────┤
│ Tool / Event Stream           │ Task Progress                │ Context / Memory / Graph │
│ action_proposed write_file    │ Task: docs expansion         │ Sources: 12              │
│ policy_decision allow         │ Step 3/7  █████░░ 43%        │ Memory hits: 5           │
│ checkpoint_created ckpt_123   │ Elapsed: 00:08:42            │ Graph nodes: 27          │
├───────────────────────────────┴──────────────────────────────┴─────────────────────────┤
│ ? side question | / command | normal prompt | ! shell proposal | @ file mention          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ READY  task:running  approvals:2  last:event checkpoint_created  cpu:12%  ram:4.1GB     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### TUI Status Bar

The status bar must be visible in rich mode unless hidden by user setting.

Required fields, left to right:

```text
STATE | task:<status> | approvals:<n> | model:<profile> | ctx:<used>/<max> | tools:<n> | mem:<scope> | net:<policy> | exec:<profile> | last:<event> | cost:<amount> | clock
```

Example:

```text
RUNNING | task:docs-expansion | approvals:1 | model:qwen9b | ctx:18k/32k | tools:14 | mem:project | net:blocked | exec:local | last:tool_completed | cost:£0.00 | 13:42
```

Status colours:

| State | Meaning |
|---|---|
| green `READY` | Waiting for user input. |
| blue `RUNNING` | Task is active. |
| yellow `WAITING` | Waiting for approval/user answer. |
| orange `RISK` | High-risk action proposed. |
| red `FAILED` | Current task failed. |
| grey `PAUSED` | Task paused. |
| purple `SIDE-Q` | Side question mode active. |

If terminal does not support colours, use text labels only.

### TUI Panels

#### Transcript Panel

Shows user messages, assistant messages, side questions, tool summaries, and final responses.

Rules:

- Tool output is collapsed by default.
- High-risk actions are highlighted.
- Side questions are visually separated from main task messages.
- Streaming assistant output should not overwrite task progress.

#### Active Plan Panel

Shows plan steps:

- step ID;
- status;
- description;
- tool expected;
- risk level;
- dependencies;
- verification criteria.

Statuses:

- pending;
- running;
- blocked;
- waiting_for_approval;
- completed;
- failed;
- skipped.

#### Approvals Panel

Shows approval cards:

```text
Approval: appr_123
Tool: shell
Command: pytest tests/test_policy.py
Risk: high
Reason: shell_requires_approval
Choices: [a] approve once  [s] approve session  [d] deny  [i] inspect  [x] defer
```

#### Task Progress Panel

Shows:

- task ID;
- objective;
- phase;
- progress;
- current step;
- elapsed time;
- pending approvals;
- child subagents;
- changed files;
- last event;
- controls.

#### Context / Memory / Graph Panel

Tabs:

- context sources;
- memory hits;
- memory candidates;
- graph nodes;
- graph relationships;
- redactions;
- token budget.

#### Event Stream Panel

Shows recent events with filters:

- all;
- tool;
- policy;
- hook;
- checkpoint;
- memory;
- channel;
- security;
- error.

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

Desktop UI is a local application shell around the same gateway.

### Desktop Home Screen

```text
┌──────────────────── Raiker Desktop ────────────────────┐
│ Sidebar                      │ Main Workspace            │
│ ─ Sessions                   │ Welcome / Active Session  │
│ ─ Active Tasks               │ Recent Tasks              │
│ ─ Approvals                  │ Pending Approvals         │
│ ─ Memory                     │ Project Context           │
│ ─ Graph                      │ Quick Actions             │
│ ─ Plugins                    │                           │
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
- status bar.

### Desktop Status Bar

```text
Session sess_abc | Task running | Model qwen-local | Context 18k/32k | Net blocked | Exec local | Approvals 1 | Checkpoint ckpt_123
```

### Desktop Notification UX

Notifications:

- approval required;
- task completed;
- task failed;
- checkpoint created;
- channel message received;
- memory candidate pending;
- security warning.

Notifications must open the relevant panel, not just show text.

---

## Web UI Design

Web UI uses the same gateway and event stream. It may be local-only or authenticated remote depending on deployment policy.

### Web Layout

```text
Top Nav: Project | Session | Model | Policy | Search | User
Left Nav: Sessions, Tasks, Approvals, Memory, Graph, Tools, Plugins, Settings
Main: Transcript / Dashboard / Inspector
Right Drawer: Context, Plan, Approval, Memory, Graph, Event Details
Bottom: Prompt / Side Question / Command Bar
```

### Web Session Page

Components:

- transcript stream;
- plan timeline;
- running tasks;
- approval cards;
- tool output viewer;
- file diff viewer;
- checkpoint timeline;
- side-question bar;
- event timeline.

### Web Security Requirements

- local-only mode by default;
- CSRF protection if browser server exists;
- auth for remote access;
- websocket event stream auth;
- no approval relay without trusted session;
- attachments scanned before context use;
- CORS locked down.

---

## Dashboard Design

Dashboard is the operational overview for Raiker.

### Dashboard Widgets

| Widget | Shows |
|---|---|
| Active Tasks | Running, waiting, failed, completed tasks. |
| Approvals | Pending risky actions. |
| Model Usage | Model profile, context, latency, local/remote. |
| Tool Activity | Recent tools, failures, denied actions. |
| Checkpoints | Recent checkpoints and restore options. |
| Memory Health | Candidates, stale records, corrections, poisoning warnings. |
| Graph Index | Last index time, stale files, node/edge counts. |
| Channels | Paired channels, recent inbound messages. |
| Plugins | Enabled plugins, permission warnings. |
| Security | OWASP control alerts, policy blocks, secret redactions. |
| Storage | SQLite DB size, vector index size, event log size. |
| Execution | Running processes, environment profile, resource usage. |

### Dashboard Layout

```text
┌────────────────────── Raiker Dashboard ──────────────────────┐
│ Health: OK | Tasks: 2 running | Approvals: 1 | Security: 0 critical │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│ Active Tasks │ Approvals    │ Model Usage  │ Security Alerts │
├──────────────┼──────────────┼──────────────┼─────────────────┤
│ Memory       │ Graph Index  │ Tool Activity│ Checkpoints     │
├──────────────┼──────────────┼──────────────┼─────────────────┤
│ Channels     │ Plugins      │ Storage      │ Execution       │
└──────────────┴──────────────┴──────────────┴─────────────────┘
```

---

## IDE Extension Design

IDE extension must provide:

- side panel transcript;
- inline file diff previews;
- diagnostics integration;
- symbol/context picker;
- approval prompts;
- checkpoint/rewind from editor;
- commands palette;
- task status badge;
- no direct tool execution outside gateway.

---

## Voice UI Design

Voice is a future client but fully specified.

Requirements:

- push-to-talk and wake mode;
- speech-to-text local-first;
- confirmation for risky actions;
- spoken summaries;
- screen/TUI handoff for approvals;
- no voice-only approval for high-risk shell/write/delete unless policy permits;
- transcript stored as normal channel message.

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

---

## UI Testing Requirements

Tests must prove:

- TUI renders in small terminal;
- status bar updates from events;
- side question does not pause task;
- approval card binds to action ID;
- checkpoint timeline opens restore flow;
- dashboard widgets derive from event/store state;
- desktop/web clients call gateway only;
- remote web UI requires auth before event stream.
