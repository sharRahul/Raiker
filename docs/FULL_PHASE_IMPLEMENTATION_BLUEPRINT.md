# Full Phase Implementation Blueprint

This document defines every Raiker phase in detail. A phase may be implemented later, but the behaviour, UI, storage, security, contracts, and tests must be documented now.

No builder agent should interpret "later phase" as "unspecified".

---

## Phase 1: Secure Local CLI Core

### User Experience

- One-shot CLI command: `raiker ask "..."`.
- Plain terminal output.
- Approval prompts rendered in terminal.
- Event log path and checkpoint path shown after each turn.

### Runtime

- PromptEnvelope validation.
- Session creation.
- Deterministic state machine.
- Tool broker.
- Static policy engine.
- Mock model provider.
- Event logging.
- Basic checkpoint manifest.

### Tools

- `read_file`.
- `list_directory`.
- `glob`.
- `grep`.
- `shell` as approval-required only.

### Storage

- `.raiker/events/*.jsonl`.
- `.raiker/checkpoints/*`.
- Optional minimal SQLite bootstrap with sessions, turns, tasks, events_index, tool_actions, policy_decisions.

### Memory

- Memory candidates only.
- No durable memory writes unless manually approved and schema exists.

### Tests

- contracts;
- event log;
- policy;
- broker;
- runtime state machine;
- CLI smoke.

---

## Phase 2: Rich Local Workspace

### User Experience

- Rich TUI becomes primary interface.
- Background tasks visible in task panel.
- User can ask side questions without stopping active task.
- Approval inbox.
- Checkpoint timeline.
- Context/memory panel.
- Event viewer.
- Status bar.

### TUI Required Screens

1. Session screen.
2. Task manager screen.
3. Approval inbox.
4. Checkpoint timeline.
5. Event viewer.
6. Memory inspector.
7. Model profile picker.
8. Permission editor.
9. Diagnostics screen.

### Runtime

- Background task manager.
- Side-question child turns.
- Interrupt/pause/cancel/steer.
- Safe boundaries.
- Verification framework.
- Context compaction.

### Tools

- `write_file` with approval.
- `edit_file` with approval and diff.
- `apply_patch` with file snapshot.
- `diff_files`.
- `stat_path`.
- `git status`, `git diff`, `git log` wrappers.

### Storage

- SQLite primary database enabled by default.
- FTS5 for memory/event search.
- Checkpoint metadata tables.
- Approval history tables.

### Memory

- Approved profile memory.
- Approved project memory.
- Memory correction/deletion.
- Memory usage attribution in context bundles.

### Model Runtime

- Ollama provider.
- llama.cpp server provider.
- LM Studio/OpenAI-compatible local provider.
- Model profiles.
- Streaming.
- Context budget display.

### Tests

- TUI status bar updates from events.
- Side question does not pause running task.
- File snapshot before edit.
- SQLite migrations.
- Local model profile validation.

---

## Phase 3: Desktop, Web, Plugins, Graph, Semantic Memory

### Desktop UI

Desktop app screens:

1. Home dashboard.
2. Active session workspace.
3. Approvals drawer.
4. File diff viewer.
5. Memory manager.
6. Graph/codemap explorer.
7. Plugin manager.
8. Model/runtime settings.
9. Security dashboard.

Desktop status bar:

```text
Project | Session | Task | Model | Context | Policy | Network | Execution | Approvals | Checkpoint
```

### Web UI

Web screens:

1. Dashboard.
2. Sessions.
3. Active session.
4. Tasks.
5. Approvals.
6. Events.
7. Checkpoints.
8. Memory.
9. Graph.
10. Plugins.
11. Channels.
12. Settings.

Web technical requirements:

- local web server by default;
- websocket event stream;
- REST API client of gateway;
- auth for remote access;
- CSRF protection;
- CORS lockdown;
- approval actions require session auth.

### Dashboard

Dashboard widgets:

- active tasks;
- approvals;
- model usage;
- tool activity;
- security alerts;
- memory health;
- graph index;
- checkpoints;
- storage;
- execution environments;
- plugins;
- channels.

### Plugins

- plugin manager;
- manifest validation;
- trust levels;
- permission diff;
- plugin commands;
- plugin hooks;
- plugin skills;
- plugin TUI panels;
- plugin tool adapters through broker.

### Graph/Codemap

- SQLite graph tables.
- AST extraction for Python initially.
- Symbol graph.
- Test coverage graph.
- Dependency graph.
- Recursive CTE graph queries.
- Graph inspector UI.

### Semantic Memory/Search

- Embeddings table.
- Local embedding model profile.
- Vector backend: SQLite vector extension if available, otherwise local vector index with SQLite metadata.
- Hybrid retrieval: FTS5 + vector + graph.

### Tests

- Desktop/web calls gateway only.
- Plugin permission diff blocks expansion.
- Graph recursive CTE impact analysis.
- Semantic search uses sensitivity filters.
- Dashboard widgets read from SQLite state.

---

## Phase 4: Channels, Multi-Agent, Remote Execution

### Channels

Channels implemented:

- REST webhooks;
- Slack;
- Teams;
- Discord;
- Signal;
- Email;
- Voice;
- Hotkeys.

All channel connectors must implement:

- pairing;
- sender trust;
- rate limits;
- attachment policy;
- approval relay disabled by default;
- session binding;
- event logging.

### Channel UI

Dashboard channel panel shows:

- paired channels;
- sender identities;
- last inbound message;
- rate-limit status;
- pending approval relay requests;
- revoked channels;
- security warnings.

### Multi-Agent

Subagent modes:

- single specialist;
- parallel reviewers;
- planner/executor;
- critic/refiner;
- red/blue security review.

Requirements:

- bounded context;
- bounded tools;
- max depth;
- max runtime;
- cost budget;
- parent verification;
- cancellation cascade.

### Remote Execution

Execution profiles:

- Git worktree;
- Docker;
- SSH;
- VPS;
- Kubernetes;
- Modal/cloud GPU;
- managed cloud runner.

Requirements:

- explicit profile;
- resource limits;
- cost policy;
- network egress rules;
- artifact capture;
- cleanup;
- audit logs.

### Tests

- unknown channel sender rejected;
- side question from channel does not stop task;
- subagent cannot exceed tools;
- Docker profile requires pinned image;
- cloud profile requires budget approval.

---

## Phase 5: Governed Enterprise And Home-Lab Platform

### Governance

- managed policies;
- role-based access;
- multi-user sessions;
- signed plugin trust;
- audit export;
- central policy dashboard;
- security test suite;
- red-team harness;
- event log integrity checks.

### Enterprise Dashboard

Widgets:

- policy compliance;
- plugin risk;
- model egress;
- user approvals;
- channel trust;
- memory governance;
- security findings;
- execution spend;
- audit export status.

### Storage

- encrypted database option;
- backup/restore manager;
- audit archive;
- retention policy;
- event log hash chain;
- signed exports.

### Security

- OWASP GenAI mapping in CI;
- prompt-injection test corpus;
- plugin supply-chain scanning;
- channel replay tests;
- memory poisoning tests;
- model egress tests.

### Tests

- managed policy overrides project allow;
- event log tampering detected;
- audit export complete;
- signed plugin verification;
- budget limits stop cloud execution;
- retention cleanup preserves legal holds/manual checkpoints.

---

## Cross-Phase Documentation Rule

For every feature in every phase, the relevant spec must define:

1. user experience;
2. contract/schema;
3. storage;
4. runtime lifecycle;
5. security policy;
6. events;
7. tests;
8. UI surface;
9. failure handling;
10. migration/upgrade impact.

A feature is not considered documented until all ten are covered.
