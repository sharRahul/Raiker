# Phase 1 MVP Build Plan

This plan decomposes Raiker Phase 1 into small implementation tasks suitable for local or mid-size LLM builders.

Phase 1 objective:

```text
Build a local CLI-driven agent runtime with explicit contracts, deterministic state transitions, append-only event logging, static policy review, a tool broker for safe filesystem/search tools, shell approval handling, a mock model provider, checkpoint stubs, and tests.
```

---

## Phase 1 Scope

Included:

- Python package scaffold;
- CLI client;
- contracts;
- agent gateway;
- session manager;
- deterministic runtime state machine;
- event log writer;
- static policy engine;
- tool broker skeleton;
- `read_file` tool;
- `list_directory` tool;
- `glob` tool;
- `grep` tool;
- `shell` tool with approval gate;
- mock model provider;
- checkpoint service;
- memory governance stub;
- tests.

Excluded:

- web UI;
- desktop UI;
- remote execution;
- plugin marketplace;
- real vector memory;
- graph memory;
- autonomous background agents;
- production authentication;
- Slack, Teams, Discord, Signal, email, or voice clients;
- real hosted LLM billing controls.

---

## Milestone 0: Repository Foundation

### RAIKER-0001: Add project scaffold

Create the recommended directory structure from `docs/ARCHITECTURE.md`.

Acceptance criteria:

- package imports as `raiker`;
- `apps/cli/main.py` exists;
- `tests/` exists;
- no runtime behaviour yet;
- README points to the docs map.

### RAIKER-0002: Add development tooling

Add minimal tooling for formatting, linting, typing, and tests.

Suggested tools:

- pytest;
- ruff;
- mypy or pyright;
- pyproject.toml.

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
- invalid enum values are rejected;
- required fields are tested;
- schema version is present on public contracts.

### RAIKER-0102: Add ID and timestamp helpers

Implement deterministic helpers for IDs and UTC timestamps.

Acceptance criteria:

- generated IDs have prefixes such as `req_`, `sess_`, `turn_`, `evt_`;
- timestamps are UTC ISO 8601 strings;
- tests verify format.

---

## Milestone 2: Event Logging

### RAIKER-0201: Implement append-only JSONL event writer

The event writer stores events under `.raiker/events/`.

Acceptance criteria:

- creates directory if missing;
- appends one JSON object per line;
- never rewrites existing events;
- validates event contract before writing;
- tests verify multiple events are appended in order.

### RAIKER-0202: Add event logging wrapper

Provide a helper used by runtime and services to emit events consistently.

Acceptance criteria:

- every emitted event has event ID and timestamp;
- parent event ID is optional;
- event type is validated;
- tests cover success and invalid event type.

---

## Milestone 3: Policy Engine

### RAIKER-0301: Implement static policy config

Add a simple static policy file such as `config/policy.phase1.json`.

Acceptance criteria:

- workspace root is defined;
- allowed read actions are defined;
- shell requires approval;
- outside-workspace access is denied;
- tests cover allow, deny, and needs_approval.

### RAIKER-0302: Implement policy engine

Policy engine evaluates `ToolAction` before execution.

Acceptance criteria:

- returns `PolicyDecision`;
- includes reasons;
- logs decision event when integrated;
- no action can execute without policy decision.

---

## Milestone 4: Tool Broker

### RAIKER-0401: Implement tool broker routing

The broker receives `ToolAction`, asks policy engine, then dispatches if allowed.

Acceptance criteria:

- unknown tool is denied or failed safely;
- denied action does not execute;
- approval-required action returns `approval_required`;
- action proposal and policy decision are logged.

### RAIKER-0402: Implement safe file read

Implement `read_file` inside workspace.

Acceptance criteria:

- path is normalised;
- outside-workspace path is denied;
- missing file returns structured error;
- binary file handling is explicit;
- tests cover success, missing file, outside workspace.

### RAIKER-0403: Implement list directory

Implement `list_directory` inside workspace.

Acceptance criteria:

- lists file and directory names;
- output is stable sorted order;
- outside-workspace path is denied;
- tests cover success and denial.

### RAIKER-0404: Implement glob and grep

Implement basic project search tools.

Acceptance criteria:

- glob patterns are restricted to workspace;
- grep handles text files only;
- output is bounded by max results;
- tests cover normal and bounded output.

### RAIKER-0405: Implement shell approval placeholder

Implement shell action path, but do not auto-run high-risk commands.

Acceptance criteria:

- shell action always requires approval in Phase 1;
- without approval, command is not executed;
- approval-required response is returned;
- event log records proposal and approval request.

---

## Milestone 5: Model Router

### RAIKER-0501: Implement mock model provider

The mock provider returns deterministic responses for tests.

Acceptance criteria:

- accepts prompt/context input;
- returns predictable text;
- supports simple tool proposal fixtures if needed;
- tests do not require network or local model installation.

### RAIKER-0502: Implement model router interface

Router selects a provider by profile.

Acceptance criteria:

- `mock` provider works;
- unknown provider fails clearly;
- no real hosted calls happen in Phase 1 tests.

---

## Milestone 6: Runtime State Machine

### RAIKER-0601: Implement runtime states

Implement the states listed in `docs/ARCHITECTURE.md`.

Acceptance criteria:

- valid transitions are enforced;
- invalid transitions raise structured errors;
- tests cover normal prompt lifecycle;
- state changes are logged.

### RAIKER-0602: Implement simple classifier and planner

Implement deterministic classifiers for Phase 1.

Acceptance criteria:

- simple chat does not require tools;
- file listing prompt maps to `filesystem_query`;
- shell prompt maps to `shell_request`;
- plan is required for shell and code-change tasks;
- plan skipped event includes reason.

### RAIKER-0603: Implement verification stub

Verification checks that required outputs exist and action status is acceptable.

Acceptance criteria:

- completed tool action can verify true;
- denied/failed action verifies false or partial with reason;
- verification event is logged.

---

## Milestone 7: Gateway, Sessions, Checkpoints

### RAIKER-0701: Implement agent gateway

Gateway validates prompt envelope and starts the runtime.

Acceptance criteria:

- invalid envelope returns failed response;
- valid envelope reaches runtime;
- gateway logs prompt received.

### RAIKER-0702: Implement session manager

Session manager creates and loads local session metadata.

Acceptance criteria:

- new session can be created;
- existing session can be loaded;
- turn IDs are tracked;
- tests cover create/load.

### RAIKER-0703: Implement checkpoint service

Checkpoint service writes turn checkpoint JSON.

Acceptance criteria:

- checkpoint path is deterministic;
- completed turn writes checkpoint;
- checkpoint includes last event ID and summary;
- tests cover write/read.

---

## Milestone 8: CLI MVP

### RAIKER-0801: Implement CLI prompt command

Add CLI command:

```bash
python -m apps.cli.main ask "List files in this project"
```

Acceptance criteria:

- builds `PromptEnvelope`;
- calls gateway;
- prints final response;
- event log is created;
- checkpoint is created.

### RAIKER-0802: Add CLI approval behaviour

For shell actions, CLI should show approval-required response instead of running automatically.

Acceptance criteria:

- shell command prompt does not execute by default;
- output explains approval is required;
- event log contains approval request.

---

## Milestone 9: Integration Validation

### RAIKER-0901: Add end-to-end smoke tests

Acceptance criteria:

- simple chat completes;
- list directory completes;
- shell request pauses for approval;
- denied outside-workspace read does not execute;
- event log contains expected event sequence;
- checkpoint exists after completion.

---

## Phase 1 Final Acceptance Criteria

Phase 1 is complete when:

- all tests pass;
- CLI can run a simple prompt;
- CLI can run safe filesystem query;
- shell action is policy-gated;
- event log is created for every turn;
- checkpoint is created for every completed turn;
- no future-phase features are implemented beyond stubs;
- docs remain consistent with implementation.

---

## Suggested Validation Commands

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python -m apps.cli.main ask "Hello Raiker"
python -m apps.cli.main ask "List files in this project"
```

If mypy is not configured yet, document that explicitly rather than pretending it ran.
