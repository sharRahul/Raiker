# Roadmap: Phase 2 To Phase 5

This roadmap expands Raiker beyond the Phase 1 MVP into a full local-first agent platform.

Builder agents must follow phase boundaries. Do not implement future phases early unless a task explicitly moves scope forward.

---

## Phase 1: Secure Local CLI MVP

Goal: prove the core loop.

Features:

- contracts;
- event log;
- static policy;
- tool broker;
- read/list/glob/grep;
- shell approval gate;
- mock model provider;
- deterministic runtime;
- checkpoint stub;
- CLI;
- tests.

---

## Phase 2: Rich Local Agent Workspace

Goal: make Raiker useful as a local coding/research/work agent.

Features:

- Rich TUI;
- background task manager;
- side questions while work continues;
- pause/cancel/steer;
- full checkpoint/rewind/fork;
- file write/edit/apply_patch with approval;
- local model providers: Ollama, llama.cpp server, LM Studio;
- model profiles;
- project/user/local configs;
- permission rules;
- hook engine;
- memory candidates and approved project/profile memory;
- command palette and slash commands;
- event viewer;
- approval inbox;
- diagnostics command.

Acceptance:

- user can run a coding task in TUI;
- ask status question while task continues;
- approve/deny file edits;
- rewind file change;
- resume session;
- use local model profile.

---

## Phase 3: Extensible Platform

Goal: allow controlled extensibility.

Features:

- plugin manager;
- plugin manifests;
- plugin permission diff;
- commands from plugins;
- hooks from plugins;
- skills/procedural memory;
- subagent profiles;
- MCP server integration;
- REST API;
- web UI;
- semantic memory;
- graph/codemap index;
- symbol/LSP tools;
- Git/worktree isolation;
- web search/fetch with egress policy.

Acceptance:

- plugin can add a command and hook;
- plugin cannot bypass policy;
- graph query informs context;
- semantic memory retrieval is auditable;
- REST client uses same gateway.

---

## Phase 4: Multi-Channel And Multi-Agent

Goal: support external interfaces and safe delegation.

Features:

- paired channels;
- Slack/Teams/Discord/Signal/email connectors as plugins;
- approval relay with strict binding;
- attachment scanning;
- subagent delegation;
- read-only specialist agents;
- parallel reviewers;
- agent team UI;
- channel notifications;
- daemon mode;
- background monitors;
- remote execution profiles: Docker and SSH.

Acceptance:

- channel side question does not stop active task;
- unknown sender rejected;
- subagent cannot exceed tools;
- remote execution denied unless profile configured.

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
- security tests run in CI.

---

## Cross-Phase Requirements

Every phase must preserve:

- gateway-only client access;
- tool-broker-only execution;
- policy before action;
- event logging;
- approval binding;
- memory governance;
- local-first privacy;
- user interruptibility;
- verification;
- documentation-first implementation.

---

## Do-Not-Drift Rules

Builder agents must not:

- add cloud dependency in local-only phase;
- implement plugin execution before manifest/policy exists;
- add channel connector without pairing/security;
- add memory writes without governance;
- add shell auto-allow without scoped permission rule;
- add subagent recursion without max depth;
- bypass event log for performance;
- treat future roadmap as current-phase scope.
