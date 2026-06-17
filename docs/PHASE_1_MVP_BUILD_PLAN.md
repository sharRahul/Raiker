# Phase 1 MVP Build Plan

This plan decomposes Raiker Phase 1 into small implementation tasks suitable for local or cloud builder models.

This document is the single source of truth for Phase 1 build scope. The previous Phase 1 alignment addendum has been merged into this plan so builders do not need to reconcile separate Phase 1 instructions.

Phase 1 objective:

```text
Build a local agent runtime core opened first through the global `raiker` terminal command, with explicit contracts, deterministic state transitions, append-only event logging, SQLite bootstrap, static policy review, a tool broker for safe filesystem/search tools, approval-gated local action proposals, a mock model provider, checkpoint stubs, connector/model registries, and tests.
```

The Phase 1 terminal client is the first implementation target only. It is not the privileged human interface. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Phase 1 Alignment Rules

### Phase Scheduling Rule

Phase-scheduled features are fully specified elsewhere in the docs. Phase 1 does not wire those features into active behaviour, but it must preserve their contracts, registries, storage boundaries, gateway paths, event shapes, client metadata, and policy boundaries.

A builder must not treat phase scheduling as missing design, lower priority interface status, or permission to create a terminal-only architecture.

### Equal Primary Interface Rule

All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. This includes CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, chat clients, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients.

Phase 1 may implement the terminal client first, but no code, contract, event, policy rule, storage table, or runtime path may describe the terminal client as the only primary human interface or grant it a private bypass path.

### Global Command Rule

The final Phase 1 deliverable must expose the global `raiker` command. Running `raiker` must open the configured local terminal client.

During early bootstrapping, module-based commands may be used temporarily, but they must be documented as temporary and must not replace the final global command requirement.

### Builder Working Rule

When working on Phase 1, a builder must:

1. choose exactly one task ID from this plan;
2. read the canonical implementation docs for that task;
3. preserve equal-interface contracts even when only the terminal client is wired;
4. implement the smallest production-quality change that satisfies the task;
5. add or update tests for the task;
6. report any temporary bootstrap limitation honestly instead of pretending the final command or integration exists.

---

## Phase 1 Scope

Included:

- Python package scaffold;
- global `raiker` command entry point;
- `raiker` opens the configured local terminal client, usually Rich TUI during early implementation;
- minimal terminal client shell;
- terminal prompt input;
- terminal slash-command parser;
- terminal approval cards;
- terminal `/launch --provider mock --model mock-deterministic` profile resolution;
- terminal `/channels` registry view;
- terminal `/models` registry view;
- contracts;
- agent gateway;
- session manager;
- deterministic runtime state machine;
- event log writer;
- JSONL event log;
- SQLite bootstrap;
- static policy engine;
- policy-gated tool broker skeleton;
- `read_file` tool;
- `list_directory` tool;
- `glob` tool;
- `grep` tool;
- approval-gated local command/action proposal path;
- mock model provider;
- model profile registry;
- channel connector profile registry;
- Apple and Android mobile app connector profiles as disabled Phase 3 profiles;
- checkpoint service stub;
- memory governance candidate path;
- interface/client metadata preservation;
- tests.

Phase-scheduled but not wired in Phase 1 unless a future task explicitly changes scope:

- Desktop UI;
- Web UI;
- Dashboard;
- Apple mobile app;
- Android mobile app;
- remote/container execution;
- plugin execution;
- durable vector memory writes;
- semantic/vector write path;
- graph runtime indexing;
- autonomous agent teams;
- subagent teams;
- production authentication;
- external channel implementations;
- hosted model billing controls.

These are not vague exclusions and do not imply lower interface status. The specs and registries must remain compatible with all equal-status primary interfaces.

---

## Milestone 0: Repository Foundation

### RAIKER-0001: Add project scaffold

Create the recommended directory structure from `docs/ARCHITECTURE.md`.

Acceptance criteria:

- package imports as `raiker`;
- terminal entry module exists;
- `tests/` exists;
- no runtime behaviour yet;
- README points to the docs map.

### RAIKER-0002: Add development tooling

Add minimal tooling for formatting, linting, typing, and tests.

Acceptance criteria:

- `python -m pytest` runs;
- formatter/linter command is documented;
- no unnecessary dependencies are added.

---

## Milestone 1: Contracts

### RAIKER-0101: Implement contract models

Implement contracts from `docs/CONTRACTS.md`.

Acceptance criteria:

- `PromptEnvelope`, `AgentEvent`, `ToolAction`, `PolicyDecision`, `ToolResult`, `AgentResponse`, and `Checkpoint` are represented in code;
- client/interface metadata is preserved;
- valid phase-scheduled client types are accepted by contract tests even when not wired yet;
- invalid enum values are rejected;
- required fields are tested;
- schema version is present on public contracts.

### RAIKER-0102: Add ID and timestamp helpers

Acceptance criteria:

- generated IDs have prefixes such as `req_`, `sess_`, `turn_`, `evt_`;
- timestamps are UTC ISO 8601 strings;
- tests verify format.

---

## Milestone 2: Storage And Event Logging

### RAIKER-0201: Implement SQLite bootstrap

Acceptance criteria:

- database is created under `.raiker/`;
- sessions, turns, tasks, events_index, tool_actions, policy_decisions, approvals, memory_candidates, connector_profiles, and model_profiles tables exist;
- migration table exists;
- tests verify fresh database creation.

### RAIKER-0202: Implement append-only JSONL event writer

Acceptance criteria:

- creates directory if missing;
- appends one JSON object per line;
- never rewrites existing events;
- validates event contract before writing;
- indexes event metadata in SQLite;
- records originating interface/client metadata;
- tests verify multiple events are appended in order.

### RAIKER-0203: Load built-in registries

Acceptance criteria:

- every connector profile has required fields;
- Apple and Android mobile connector profiles exist;
- every connector profile declares equal-primary status when enabled;
- every model profile has required fields;
- disabled profiles are listable but not wired;
- terminal `/channels` and `/models` can show profiles when terminal command support lands;
- tests cover invalid registry entries.

---

## Milestone 3: Policy Engine

### RAIKER-0301: Implement static policy config

Acceptance criteria:

- workspace root is defined;
- allowed read actions are defined;
- local action proposals that can affect the machine require approval;
- outside-workspace access is denied;
- tests cover allow, deny, and needs_approval.

### RAIKER-0302: Implement policy engine

Acceptance criteria:

- returns `PolicyDecision`;
- includes reasons;
- logs decision event when integrated;
- no action can execute without policy decision;
- no interface can bypass policy.

---

## Milestone 4: Tool Broker

### RAIKER-0401: Implement tool broker routing

Acceptance criteria:

- unknown tool is denied or failed safely;
- denied action does not execute;
- approval-required action returns `approval_required`;
- action proposal and policy decision are logged.

### RAIKER-0402: Implement safe file read

Acceptance criteria:

- path is normalised;
- outside-workspace path is denied;
- missing file returns structured error;
- binary file handling is explicit;
- tests cover success, missing file, outside workspace.

### RAIKER-0403: Implement list directory

Acceptance criteria:

- lists file and directory names;
- output is stable sorted order;
- outside-workspace path is denied;
- tests cover success and denial.

### RAIKER-0404: Implement glob and grep

Acceptance criteria:

- glob patterns are restricted to workspace;
- grep handles text files only;
- output is bounded by max results;
- tests cover normal and bounded output.

### RAIKER-0405: Implement approval-gated local action placeholder

Acceptance criteria:

- approval-gated action always requires approval in Phase 1;
- without approval, the action is not executed;
- approval-required response is rendered in the terminal approval area;
- event log records proposal and approval request.

---

## Milestone 5: Model Router

### RAIKER-0501: Implement mock model provider

Acceptance criteria:

- accepts prompt/context input;
- returns predictable text;
- supports simple tool proposal fixtures if needed;
- tests do not require network or local model installation.

### RAIKER-0502: Implement model router interface

Acceptance criteria:

- `mock` provider works;
- unknown provider fails clearly;
- no hosted calls happen in Phase 1 tests;
- model profile registry is used.

### RAIKER-0503: Implement terminal launch profile resolution

Acceptance criteria:

- `/launch --provider mock --model mock-deterministic` resolves the mock profile;
- unknown provider/model returns structured error;
- launch request emits model launch events;
- launch action is interface-neutral in contract shape;
- tests cover success and unknown provider.

---

## Milestone 6: Runtime State Machine

### RAIKER-0601: Implement runtime states

Acceptance criteria:

- valid transitions are enforced;
- invalid transitions raise structured errors;
- tests cover normal prompt lifecycle;
- state changes are logged.

### RAIKER-0602: Implement simple classifier and planner

Acceptance criteria:

- simple prompt does not require tools;
- file listing prompt maps to `filesystem_query`;
- local action prompt maps to approval-gated action intent;
- plan is required for approval-gated and code-change tasks;
- plan skipped event includes reason.

### RAIKER-0603: Implement verification stub

Acceptance criteria:

- completed tool action can verify true;
- denied/failed action verifies false or partial with reason;
- verification event is logged.

---

## Milestone 7: Gateway, Sessions, Checkpoints

### RAIKER-0701: Implement agent gateway

Acceptance criteria:

- invalid envelope returns failed response;
- valid envelope reaches runtime;
- gateway logs prompt received;
- gateway preserves client/interface metadata.

### RAIKER-0702: Implement session manager

Acceptance criteria:

- new session can be created;
- existing session can be loaded;
- turn IDs are tracked;
- tests cover create/load.

### RAIKER-0703: Implement checkpoint service

Acceptance criteria:

- checkpoint path is deterministic;
- completed turn writes checkpoint;
- checkpoint includes last event ID and summary;
- tests cover write/read.

---

## Milestone 8: Terminal Client MVP

### RAIKER-0801: Implement global `raiker` terminal launch

Acceptance criteria:

- `raiker` starts the configured local terminal client;
- terminal client shows prompt input and status area;
- terminal client can exit safely;
- tests cover dispatch.

### RAIKER-0802: Implement terminal prompt path

Acceptance criteria:

- plain terminal input builds `PromptEnvelope`;
- terminal client calls gateway;
- terminal client renders final response;
- event log is created;
- checkpoint is created.

### RAIKER-0803: Add terminal approval behaviour

Acceptance criteria:

- approval-gated prompt does not execute by default;
- approval card explains approval is required;
- event log contains approval request.

### RAIKER-0804: Add terminal registry panels

Add Phase 1 registry panels:

```text
/channels
/models
```

Acceptance criteria:

- lists profiles from config registries;
- disabled profiles are visible as disabled;
- Apple and Android mobile app profiles are visible as disabled Phase 3 profiles;
- invalid registry produces structured error.

---

## Milestone 9: Integration Validation

### RAIKER-0901: Add end-to-end smoke tests

Acceptance criteria:

- global `raiker` opens the configured local terminal client;
- simple prompt completes through terminal path;
- list directory completes through terminal path;
- approval-gated request pauses for approval;
- denied outside-workspace read does not execute;
- event log contains expected event sequence;
- checkpoint exists after completion;
- `/launch --provider mock --model mock-deterministic` resolves a profile;
- equal-interface invariant is asserted in docs/config tests.

---

## Phase 1 Final Acceptance Criteria

Phase 1 is complete when:

- all tests pass;
- global `raiker` command opens the configured local terminal client;
- terminal client can run a simple prompt;
- terminal client can run safe filesystem query;
- terminal client can resolve `/launch --provider mock --model mock-deterministic`;
- terminal client can show `/channels` and `/models` registry views;
- approval-gated local action is policy-gated;
- event log is created for every turn;
- checkpoint is created for every completed turn;
- connector/model registries load and list inside terminal client;
- connector registry includes Apple and Android mobile app profiles as disabled Phase 3 profiles;
- phase-scheduled features are not wired beyond the Phase 1 task scope;
- docs remain consistent with implementation;
- docs do not describe any interface as primary over another.

---

## Suggested Validation Commands

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Expected manual terminal validation actions:

```text
normal prompt: Hello Raiker
normal prompt: List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

If mypy or the global command is not configured yet during bootstrapping, document that explicitly rather than pretending it ran. During early packaging, module-based commands may be used temporarily, but the final Phase 1 deliverable must expose the global `raiker` command that opens the configured local terminal client.
