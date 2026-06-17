# Roadmap: Phase 2 To Phase 5

This roadmap expands Raiker beyond the Phase 1 MVP into a full local-first agent platform.

The roadmap is an implementation schedule, not a placeholder for missing design. Every item listed here must already be backed by a detailed specification, contract, storage plan, security rule, UI surface, event model, and test plan in the related docs.

Phase order does not define interface priority. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Phase 1: Secure Local Interface MVP

Goal: prove the core loop and install the global `raiker` terminal command without making the terminal client the only primary interface.

Features:

- global `raiker` command;
- minimal terminal client shell, usually Rich TUI;
- terminal prompt input;
- terminal slash commands;
- terminal approval cards;
- equal-interface contracts;
- SQLite bootstrap;
- event log;
- static policy;
- tool broker;
- read/list/glob/grep;
- local action approval gate;
- mock model provider;
- model profile registry;
- channel connector profile registry;
- Apple and Android mobile connector profiles as disabled Phase 3 profiles;
- deterministic runtime;
- checkpoint stub;
- tests.

Acceptance:

- `raiker` launches the configured local terminal client;
- a normal prompt typed inside the terminal client reaches the gateway;
- `/launch --provider mock --model mock-deterministic` loads the mock profile;
- `/channels` and `/models` list registry profiles;
- Apple and Android mobile profiles are visible in the connector registry;
- local action proposals that can affect the machine require approval;
- event log and checkpoint are created;
- no doc or test treats the terminal client as primary over another enabled interface.

---

## Phase 2: Rich Local Agent Workspace

Goal: make Raiker useful as a local coding/research/work agent while preserving equal-interface contracts.

Features:

- full Rich TUI;
- background task manager;
- side questions while work continues;
- pause/cancel/steer;
- full checkpoint/rewind/fork;
- file write/edit/apply_patch with approval;
- local model providers: Ollama, llama.cpp server, LM Studio;
- model profiles and launch/switch UI;
- project/user/local configs;
- permission rules;
- hook engine;
- memory candidates and approved project/profile memory;
- eidetic observations and gist memory;
- self-improving skill proposals after verified tasks;
- command palette and slash commands;
- event viewer;
- approval inbox;
- diagnostics command.

Acceptance:

- user can run a coding task in the terminal client;
- user can ask a status question while task continues;
- user can approve/deny file edits;
- user can rewind file change;
- user can resume session;
- user can use local model profile;
- eidetic observation retention is enforced;
- skill candidate cannot install without verification and approval;
- expanded terminal features do not create a gateway, policy, event, or runtime bypass.

---

## Phase 3: Extensible Platform And Equal Primary Apps

Goal: allow controlled extensibility and make Desktop, Web, Dashboard, Apple mobile app, Android mobile app, REST, and IDE equal primary interfaces.

Features:

- plugin manager;
- plugin manifests;
- plugin permission diff;
- commands from plugins;
- hooks from plugins;
- skills/procedural memory;
- Desktop UI;
- Web UI;
- Dashboard;
- Apple mobile app;
- Android mobile app;
- REST API;
- IDE extension;
- semantic memory;
- graph/codemap index;
- symbol/LSP tools;
- Git/worktree isolation;
- web search/fetch with egress policy;
- scheduled automations dashboard.

Acceptance:

- plugin can add a command and hook;
- plugin cannot bypass policy;
- graph query informs context;
- semantic memory retrieval is auditable;
- REST client uses same gateway;
- Desktop/Web/Mobile/IDE clients use the same gateway, event stream, session state, policy checks, and action contracts;
- Desktop/Web/Mobile dashboard displays tasks, approvals, memory, graph, storage, execution, channels, models, and security state.

---

## Phase 4: Multi-Channel And Multi-Agent

Goal: support external interfaces and safe delegation while preserving equal primary interface status.

Features:

- channel implementation packages wired to existing connector profiles;
- Email, Slack, Teams, Discord, Signal, Voice, Hotkeys, MCP Channel, and Browser Extension connectors;
- approval relay with strict binding and disabled-by-default policy;
- attachment scanning;
- subagent delegation;
- read-only specialist agents;
- parallel reviewers;
- manager/planner/executor mode;
- agent team UI;
- channel notifications;
- daemon mode;
- background monitors;
- execution profiles for container, SSH, VPS, Kubernetes, and persistent sandbox profiles.

Acceptance:

- channel side question does not stop active task;
- unknown sender rejected;
- subagent cannot exceed tools;
- connector implementation can be absent while connector profile remains listable;
- remote/container execution is denied unless profile configured;
- all linked channels show pairing, sender trust, and rate-limit state in Dashboard;
- enabled channel clients route actions through the same gateway and policy model as other primary interfaces.

---

## Phase 5: Governed Enterprise/Home-Lab Platform

Goal: production-grade governance and operations.

Features:

- managed policies;
- signed plugins;
- plugin marketplace/index;
- audit export;
- event log integrity checks;
- role-based access;
- multi-user sessions;
- central memory governance;
- cloud/GPU/batch execution;
- cost budgets;
- policy-as-code;
- security test suite;
- red-team harness;
- deployment guides;
- admin dashboards.

Acceptance:

- managed policy can force hooks/plugins;
- audit export maps to security controls;
- budgets stop overconsumption;
- event log tampering is detectable;
- security tests run in CI;
- managed governance preserves equal primary interface status unless policy explicitly restricts a capability across interfaces.

---

## Cross-Phase Requirements

Every phase must preserve:

- gateway-only client access;
- equal primary interface status for every implemented and enabled client;
- action parity through shared contracts;
- tool-broker-only execution;
- policy before action;
- event logging;
- approval binding;
- memory governance;
- local-first privacy;
- user interruptibility;
- verification;
- documentation-first implementation;
- global `raiker` terminal entry compatibility;
- connector and model registry compatibility.

---

## Do-Not-Drift Rules

Builder agents must not:

- add cloud dependency in a local-only task;
- implement plugin execution before manifest/policy exists;
- add channel connector wiring without pairing/security;
- add memory writes without governance;
- add command auto-allow without scoped permission rule;
- add subagent recursion without max depth;
- bypass event log for performance;
- treat a phase-scheduled roadmap item as current task scope unless the task explicitly targets that phase;
- treat phase scheduling as missing specification;
- describe one interface as primary over another interface.
