# Full Phase Implementation Blueprint

This document defines every Raiker phase in detail. A phase may be built later, but the behaviour, UI, storage, security, contracts, and tests are documented now.

No builder agent should interpret "later phase" as "unspecified" or "lower priority interface". Phase means implementation order only. Every implemented and enabled interface is an equal-status primary interface.

---

## Builder Flow Across All Files

A local or cloud builder model must follow this order:

```text
README.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/ARCHITECTURE.md
  -> docs/CONTRACTS.md
  -> docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/SECURITY_AND_POLICY.md
  -> task-specific spec
  -> docs/VERIFICATION_PLAN.md
```

For any task, the builder must identify phase, task ID, files to change, contracts affected, storage affected, events emitted, policy gates, UI surface, tests, documentation updates, and interface/action parity impact.

---

## Cross-Phase Equal Interface Rule

CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

All actions available through one enabled primary interface must have an equivalent action path in every other enabled primary interface that supports the relevant capability. UI shape can differ, but the underlying gateway contract, policy review, event logging, approval binding, session state, checkpoint handling, memory governance, and runtime orchestration must be the same.

---

## Phase 1: Secure Local Interface Core

### User Experience

- Global command: `raiker`.
- Running `raiker` opens the configured local terminal client, usually the Rich TUI during early implementation.
- The terminal client is the first implementation target, not the privileged human interface.
- Normal prompts are submitted through the terminal client in Phase 1 and through every enabled primary interface in its build phase.
- Side questions use terminal syntax such as `?` in Phase 1 and equivalent native controls in other interfaces.
- Model launch and switching use terminal commands such as `/launch` and `/models` in Phase 1 and equivalent model controls in other interfaces.
- Channel listing/linking uses terminal commands such as `/channels` in Phase 1 and equivalent settings/linking screens in other interfaces.
- Diagnostics use terminal commands such as `/doctor` in Phase 1 and equivalent diagnostics screens/actions in other interfaces.
- Approval prompts are rendered as terminal approval cards in Phase 1 and equivalent approval inbox/cards/drawers/mobile controls in other interfaces.
- Event log path and checkpoint path are visible in the terminal status/details panels after each turn and must be exposed by other interfaces through equivalent status surfaces.

### Runtime

- PromptEnvelope validation.
- UIActionEnvelope validation for interface actions.
- ChannelMessageEnvelope validation for channel/mobile/chat/API inputs.
- Session creation.
- Deterministic state machine.
- Tool broker.
- Static policy engine.
- Mock model provider.
- Event logging.
- SQLite bootstrap.
- Basic checkpoint manifest.
- Equal-interface client metadata preserved on events and responses.

### Tools

- `read_file`.
- `list_directory`.
- `glob`.
- `grep`.
- local command proposal as approval-required only.

### Storage

- `.raiker/raiker.db` bootstrap.
- `.raiker/events/*.jsonl`.
- `.raiker/checkpoints/*`.
- SQLite tables for sessions, turns, tasks, events_index, tool_actions, policy_decisions, approvals, memory_candidates, connector profiles, and model profiles.

### Memory

- Memory candidates.
- Scratchpad memory for current task.
- Eidetic observation metadata table available but raw capture disabled until Phase 2 policy is wired.
- No durable memory write without approval and schema.

### Tests

- contracts;
- event log;
- policy;
- broker;
- runtime state machine;
- global `raiker` launches the configured local terminal client;
- terminal prompt path reaches gateway;
- interface client metadata is preserved;
- SQLite bootstrap;
- connector registry load;
- model profile registry load;
- terminal/TUI smoke.

---

## Phase 2: Rich Local Workspace

### User Experience

- Full Rich TUI becomes a complete local terminal interface, but not the primary interface over others.
- Background tasks visible in task panel.
- User can ask side questions without stopping active task.
- Approval inbox.
- Checkpoint timeline.
- Context/memory panel.
- Event viewer.
- Status bar.
- Local provider launch/switch UI.
- Shared action contracts remain compatible with Desktop, Web, Mobile, IDE, Voice, Hotkeys, REST, Webhooks, and channels.

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
10. Provider launch screen.
11. Channel connector listing screen.

### Runtime

- Background task manager.
- Side-question child turns.
- Interrupt/pause/cancel/steer.
- Safe boundaries.
- Verification framework.
- Context compaction.
- Provider launch and health-check path.

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
- Eidetic observation tables.
- Gist memory records.

### Memory

- Approved profile memory.
- Approved project memory.
- Episodic memory.
- Procedural memory.
- Eidetic observation snapshots with retention.
- Gist summaries.
- Memory correction/deletion.
- Memory usage attribution in context bundles.
- Hermes-style skill candidate proposals after verified successful tasks.

### Model Runtime

- llama.cpp server provider (native default backend).
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
- Eidetic observation retention.
- Skill candidate requires verification.
- Equal-interface contracts remain unchanged when TUI features expand.

---

## Phase 3: Desktop, Web, Mobile, Plugins, Graph, Semantic Memory

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
10. Channel connector wizard.
11. Skill manager.
12. Scheduled automation manager.

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
12. Models.
13. Skills.
14. Automations.
15. Settings.

Web technical requirements:

- local web server by default;
- websocket or SSE event stream;
- REST API client of gateway;
- auth for remote access;
- CSRF protection;
- CORS lockdown;
- approval actions require session auth.

### Apple And Android Mobile Apps

Apple mobile app and Android mobile app are equal primary interfaces and must not be treated as notification-only companions.

Mobile screens:

1. Home and session list.
2. Active session transcript.
3. Prompt and side-question composer.
4. Active task progress.
5. Approval inbox.
6. Checkpoint timeline.
7. Memory/context inspector.
8. Graph/codemap query view or deep-link handoff.
9. Models launch/switch screen.
10. Channels link/unlink and pairing screen.
11. Diagnostics.
12. Settings and security summary.

Mobile requirements:

- prompt submission;
- side questions;
- pause/cancel/steer;
- approve/deny/defer with exact action binding;
- checkpoint restore/fork;
- model launch/switch;
- channel link/unlink;
- memory search and correction request;
- graph/codemap query;
- diagnostics;
- push notifications for task updates and approval requests;
- stale mobile state cannot approve actions until refreshed against the gateway.

### Dashboard

Dashboard widgets:

- active tasks;
- approvals;
- model usage;
- tool activity;
- security alerts;
- memory health;
- eidetic observation retention;
- graph index;
- checkpoints;
- storage;
- execution environments;
- plugins;
- channels;
- skills;
- scheduled automations.

### Plugins And Skills

- plugin manager;
- manifest validation;
- trust levels;
- permission diff;
- plugin commands;
- plugin hooks;
- plugin skills;
- plugin TUI panels;
- plugin UI panels for Desktop, Web, and Mobile where supported;
- plugin tool adapters through broker;
- bundled/global/workspace skills with precedence;
- skill self-improvement through proposals, tests, and approval.

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

- Desktop/web/mobile clients call gateway only.
- Mobile approval rejects stale state.
- Plugin permission diff blocks expansion.
- Graph recursive CTE impact analysis.
- Semantic search uses sensitivity filters.
- Dashboard widgets read from SQLite state.
- Skill precedence and self-improvement proposal flow works.
- Prompt, side-question, approval, task-control, model, channel, memory, graph, diagnostics, and checkpoint actions use equivalent contracts across enabled interfaces.

---

## Phase 4: Channels, Multi-Agent, Remote Execution

### Channels

Connector profiles already exist in `config/channel-connectors.json`. Phase 4 wires the implementation packages for these connectors:

- REST webhooks;
- Email;
- Slack;
- Teams;
- Discord;
- Signal;
- Voice;
- Hotkeys;
- MCP channel;
- Browser extension.

All channel connectors must implement pairing, sender trust, rate limits, attachment policy, approval relay disabled by default, session binding, side-question routing, task controls where permitted, and event logging.

### OpenClaw-Style Gateway Coverage

Raiker must include:

- local-first gateway;
- multi-channel inbox;
- pairing for unknown senders;
- channel allowlists;
- daemon mode;
- channel-to-agent routing;
- companion app control surfaces;
- live workspace/canvas equivalent through Web/Desktop/Mobile dashboard panels;
- skills available from bundled, global, and workspace scopes;
- channel security diagnostics.

### Channel UI

Dashboard channel panel shows paired channels, sender identities, last inbound message, rate-limit status, pending approval relay requests, revoked channels, connector implementation status, package needed, and security warnings.

Channel/chat/email/browser-extension interfaces are equal primary interfaces when linked and enabled, but their enabled capabilities are constrained by policy, trust, transport limitations, and pairing state.

### Multi-Agent

Subagent modes:

- single specialist;
- parallel reviewers;
- planner/executor;
- critic/refiner;
- red/blue security review;
- manager/planner/executor memory intelligence pattern.

Requirements:

- bounded context;
- bounded tools;
- max depth;
- max runtime;
- cost budget;
- parent verification;
- cancellation cascade;
- memory writes as candidates unless governance approves.

### Remote Execution

Execution profiles:

- Git worktree;
- container;
- SSH;
- VPS;
- Kubernetes;
- Modal/cloud GPU;
- managed cloud runner;
- Daytona-style persistent sandbox.

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
- channel task control obeys sender trust and policy;
- subagent cannot exceed tools;
- container profile requires pinned image;
- cloud profile requires budget approval;
- channel connector can be listed before implementation is installed.

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
- eidetic retention and deletion status;
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
- model egress tests;
- eidetic raw-observation retention tests.

### Tests

- managed policy overrides project allow;
- event log tampering detected;
- audit export complete;
- signed plugin verification;
- budget limits stop cloud execution;
- retention cleanup preserves legal holds/manual checkpoints;
- managed policies preserve the equal primary interface invariant unless explicitly restricting a capability for all interfaces by policy.

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
10. migration/upgrade impact;
11. equal-interface action parity impact.

A feature is not considered documented until all eleven are covered.
