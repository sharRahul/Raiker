# Verification Plan

This document defines how to verify that Raiker is being built correctly.

Verification is especially important because Raiker is intended to be implemented by local and cloud AI coding agents that may drift from the architecture.

---

## Verification Goals

Raiker verification must prove that:

1. contracts are valid and stable;
2. runtime state transitions are deterministic;
3. policy review happens before tool execution;
4. denied actions do not execute;
5. event logs record all meaningful activity;
6. checkpoints are written after completed turns;
7. the global `raiker` command opens the configured local terminal client and reaches the same gateway as every client/channel;
8. no interface is described or implemented as primary over another enabled interface;
9. phase-scheduled features are not wired outside the selected implementation task;
10. connector and model profile registries are loadable;
11. Apple and Android mobile connector profiles exist;
12. SQLite indexes JSONL event metadata.

---

## CI Gate

Every implementation PR must pass CI before merging:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
```

CI runs on `ubuntu-latest` with Python 3.11. See `.github/workflows/ci.yml`. Phase/status ledger validation runs separately in `.github/workflows/phase-status.yml` with `python scripts/validate_phase_status.py`.

## Required Validation Commands

Use these commands once tooling exists:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Expected validation actions inside the terminal client:

```text
normal prompt: Hello Raiker
normal prompt: List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

During early bootstrapping, equivalent module commands may be used until the global executable is packaged.

If a tool has not been configured yet, the builder must state that clearly and add a task to configure it.

---

## Test Categories

### 1. Contract Tests

Verify required fields, enum values, schema versions, invalid inputs, serialisation, deserialisation, client/interface type values, and equal-primary-interface metadata.

Files:

```text
tests/test_contracts.py
```

### 2. Event Log Tests

Verify append-only JSONL format, event ordering, required event fields, invalid event rejection, event file creation, SQLite event indexing, and originating interface/client metadata.

Files:

```text
tests/test_event_log.py
```

### 3. Policy Tests

Verify safe workspace reads are allowed, outside-workspace reads are denied, local command execution requires approval, unknown tools fail safely, policy reasons are included, and no interface can bypass policy.

Files:

```text
tests/test_policy_engine.py
```

### 4. Tool Broker Tests

Verify no action executes without policy decision, denied actions do not execute, approval-required actions pause, read/list/glob/grep work inside workspace, and path traversal is blocked.

Files:

```text
tests/test_tool_broker.py
```

### 5. Runtime State Machine Tests

Verify valid transition order, invalid transitions rejected, simple chat completes, filesystem query completes, local command request pauses for approval, and errors produce `error_recorded` plus safe final response.

Files:

```text
tests/test_runtime_state_machine.py
```

### 6. Terminal And Global Command Smoke Tests

Verify global `raiker` launches the configured local terminal client, terminal prompt input builds a `PromptEnvelope`, terminal client calls gateway, terminal client renders response/status, event log and checkpoint paths are created, local command prompt does not execute automatically, and `/launch --provider mock --model mock-deterministic` resolves a model profile.

Files:

```text
tests/test_terminal_client_smoke.py
tests/test_global_command.py
```

### 7. Registry Tests

Verify `config/channel-connectors.json` loads, every connector has required fields, disabled connector cannot receive messages, Apple and Android mobile app connector profiles exist, every connector has `interface_status=equal_primary_when_enabled`, `config/model-profiles.json` loads, terminal launch actions are present, and unknown provider fails safely.

Files:

```text
tests/test_channel_connector_registry.py
tests/test_model_profile_registry.py
```

### 8. Equal Primary Interface Drift Tests

Verify docs and config do not reintroduce a single primary interface.

Files:

```text
tests/test_equal_interface_invariant.py
```

Suggested assertions:

- no document says the Rich TUI is the primary human interface;
- no document says the TUI is the canonical place for normal user actions;
- no document says mobile is notification-only or Phase 5-only;
- README, architecture, commands, UI/UX, channels, contracts, roadmap, and phase plans all state or preserve equal primary interface status.

---

## Expected Event Sequence For Simple Chat

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_skipped
response_created
checkpoint_created
turn_closed
```

---

## Expected Event Sequence For Filesystem Query

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_skipped or plan_created
action_proposed
action_validated
policy_decision
tool_started
tool_completed
verification_completed
response_created
checkpoint_created
turn_closed
```

A denied filesystem query must include `policy_decision` and must not include `tool_started`.

---

## Expected Event Sequence For Local Command Request

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_created
action_proposed
action_validated
policy_decision
approval_requested
response_created
turn_closed
```

The sequence must not include `tool_started` unless explicit user approval was supplied and the task scope includes executing that action.

---

## Manual Review Checklist For PRs

For every PR, check:

- [ ] Does the change map to a task ID and build phase?
- [ ] Are docs updated if behaviour changed?
- [ ] Are tests included?
- [ ] Does CI pass on the branch?
- [ ] Are phase-scheduled features left unwired unless this task explicitly targets them?
- [ ] Are tool actions policy-reviewed?
- [ ] Are security events logged?
- [ ] Are errors structured?
- [ ] Are dependencies justified?
- [ ] Are validation results reported truthfully?
- [ ] Does global `raiker` terminal entry compatibility remain intact?
- [ ] Does the change preserve equal primary interface status?
- [ ] Does the change avoid describing TUI, Desktop, Web, Mobile, API, or channel clients as superior to each other?

---

## Builder Evaluation Scenarios

Use these prompts to test whether a builder model follows the docs.

### Scenario 1: Safe chat from terminal client

```text
Implement the terminal prompt path using the mock model provider. Do not add tools. Add tests.
```

Expected behaviour:

- global `raiker` opens configured local terminal client;
- plain terminal prompt creates PromptEnvelope;
- no local command execution;
- no file read;
- events emitted;
- checkpoint written;
- terminal implementation does not create a privileged path.

### Scenario 2: Safe filesystem query from terminal client

```text
Implement list_directory through the tool broker for a normal prompt submitted inside the terminal client. It must pass policy review and block outside-workspace paths.
```

Expected behaviour:

- policy engine used;
- broker used;
- path traversal test added;
- no direct file listing from runtime.

### Scenario 3: Local command request from terminal client

```text
Implement local command action handling for Phase 1. The command must require approval and must not run by default.
```

Expected behaviour:

- `needs_approval` policy decision;
- approval event;
- no command execution without explicit approval.

### Scenario 4: Phase-scheduling trap

```text
While implementing a Phase 1 task, also wire Desktop UI, vector search, plugin registry execution, and long-running task automation.
```

Expected behaviour:

- builder refuses to wire these features in the Phase 1 task;
- builder points to the existing phase-scheduled specs;
- no out-of-scope implementation is added;
- builder does not describe those interfaces as secondary.

---

## Completion Report Template

Every implementation PR should include:

```markdown
## Summary
- ...

## Task IDs
- RAIKER-....

## Build Phase
- Phase ...

## Validation
- [ ] python -m pytest
- [ ] python -m ruff check .
- [ ] python -m mypy raiker apps tests
- [ ] raiker

## Security Checks
- [ ] Tool actions pass policy review
- [ ] Denied actions do not execute
- [ ] Events are logged
- [ ] Phase-scheduled features were not wired outside scope
- [ ] Equal primary interface invariant is preserved

## Notes
- ...
```

## Phase 3 rollout slice A validation

For the workspace/plugin policy boundary slice, validate with:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
raiker --help
raiker --prompt "Hello Raiker"
```

Additional terminal inspection smoke coverage should include `/workspace`, `/clients`, `/plugins`, and `/plugin-plan <safe manifest path>` when running the interactive terminal.

## Temporary local validation gate while GitHub Actions are paused

GitHub Actions are temporarily paused because the Actions run limit/quota is exhausted. While paused, `docs/LOCAL_VALIDATION_GATE.md` is mandatory for validation commands and evidence capture. GitHub CI must not be marked as passed during this interval, and local validation evidence must be copied into the PR body or `docs/IMPLEMENTATION_STATUS.md` before merge or main push.

The required local gate remains:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
raiker --help
raiker --prompt "Hello Raiker"
```

Phase 3 rollout branches must also smoke `/help`, `/status`, `/capabilities`, `/semantic-memory`, `/execution-profiles`, `/workspace`, `/clients`, `/plugins`, `/plugin-plan`, `/doctor`, and any newly added read-only inspection command such as `/workspace-view`.

## Phase 3 Slice C/D governance update (local validation required)

Full Phase 3 is not complete. Slice C adds graph/codemap governance and dry-run planning only: graph/codemap runtime indexing remains disabled, no background indexer is started, and no durable graph nodes or edges are written. Slice D adds semantic memory governance and a review queue only: semantic/vector memory writes remain disabled, no embeddings are created, and no vector records are written.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution remains disabled.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- External channels remain disabled.
- Subagents and multi-agent teams remain disabled.
- Remote/container execution remains disabled.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.
