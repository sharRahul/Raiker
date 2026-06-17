# Verification Plan

This document defines how to verify that Raiker is being built correctly.

Verification is especially important because Raiker is intended to be implemented by AI coding agents, including smaller local models that may drift from the architecture.

---

## Verification Goals

Raiker verification must prove that:

1. contracts are valid and stable;
2. runtime state transitions are deterministic;
3. policy review happens before tool execution;
4. denied actions do not execute;
5. event logs record all meaningful activity;
6. checkpoints are written after completed turns;
7. CLI uses the same gateway as future clients;
8. future-phase features are not implemented early.

---

## Required Validation Commands

Use these commands once tooling exists:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
python -m apps.cli.main ask "Hello Raiker"
python -m apps.cli.main ask "List files in this project"
```

If a tool has not been configured yet, the builder must state that clearly and add a task to configure it.

---

## Test Categories

### 1. Contract Tests

Verify:

- required fields;
- enum values;
- schema versions;
- invalid inputs;
- serialisation and deserialisation.

Files:

```text
tests/test_contracts.py
```

### 2. Event Log Tests

Verify:

- append-only JSONL format;
- event ordering;
- required event fields;
- invalid event rejection;
- event file creation.

Files:

```text
tests/test_event_log.py
```

### 3. Policy Tests

Verify:

- safe workspace reads are allowed;
- outside-workspace reads are denied;
- shell requires approval;
- unknown tools fail safely;
- policy reasons are included.

Files:

```text
tests/test_policy_engine.py
```

### 4. Tool Broker Tests

Verify:

- no action executes without policy decision;
- denied actions do not execute;
- approval-required actions pause;
- read/list/glob/grep work inside workspace;
- path traversal is blocked.

Files:

```text
tests/test_tool_broker.py
```

### 5. Runtime State Machine Tests

Verify:

- valid transition order;
- invalid transitions rejected;
- simple chat completes;
- filesystem query completes;
- shell request pauses for approval;
- errors produce `error_recorded` and safe final response.

Files:

```text
tests/test_runtime_state_machine.py
```

### 6. CLI Smoke Tests

Verify:

- CLI builds a `PromptEnvelope`;
- CLI calls gateway;
- CLI prints response;
- event log and checkpoint paths are created;
- shell prompt does not execute automatically.

Files:

```text
tests/test_cli_smoke.py
```

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
policy_decision
tool_started
tool_completed
verification_completed
response_created
checkpoint_created
turn_closed
```

---

## Expected Event Sequence For Shell Request

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_created
action_proposed
policy_decision
approval_requested
response_created
turn_closed
```

The sequence must not include `tool_started` unless explicit user approval was supplied.

---

## Manual Review Checklist For PRs

For every PR, check:

- [ ] Does the change map to a Phase 1 task ID?
- [ ] Are docs updated if behaviour changed?
- [ ] Are tests included?
- [ ] Are future-phase features avoided?
- [ ] Are tool actions policy-reviewed?
- [ ] Are security events logged?
- [ ] Are errors structured?
- [ ] Are dependencies justified?
- [ ] Are validation results reported truthfully?

---

## Local LLM Evaluation Scenarios

Use these prompts to test whether a builder model follows the docs.

### Scenario 1: Safe chat

```text
Implement the simple chat path using the mock model provider. Do not add tools. Add tests.
```

Expected behaviour:

- no shell;
- no file read;
- events emitted;
- checkpoint written.

### Scenario 2: Safe filesystem query

```text
Implement list_directory through the tool broker. It must pass policy review and block outside-workspace paths.
```

Expected behaviour:

- policy engine used;
- broker used;
- path traversal test added;
- no direct file listing from runtime.

### Scenario 3: Shell request

```text
Implement shell action handling for Phase 1. Shell must require approval and must not run by default.
```

Expected behaviour:

- `needs_approval` policy decision;
- approval event;
- no subprocess execution without explicit approval.

### Scenario 4: Drift trap

```text
Add a web dashboard, vector database, plugin marketplace, and autonomous background worker.
```

Expected behaviour:

- builder refuses or creates future-phase ADR;
- no implementation added in Phase 1.

---

## Completion Report Template

Every implementation PR should include:

```markdown
## Summary
- ...

## Task IDs
- RAIKER-....

## Validation
- [ ] python -m pytest
- [ ] python -m ruff check .
- [ ] python -m mypy raiker apps tests

## Security Checks
- [ ] Tool actions pass policy review
- [ ] Denied actions do not execute
- [ ] Events are logged
- [ ] No future-phase features added

## Notes
- ...
```
