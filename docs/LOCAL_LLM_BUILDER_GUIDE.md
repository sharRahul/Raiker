# Local LLM Builder Guide

This guide is written for small and mid-size coding models such as Qwen 3.5 9B, Gemma 4 31B cloud, local Ollama models, or other constrained agentic builders.

The goal is to reduce ambiguity so the builder can implement Raiker task-by-task without inventing architecture, skipping security boundaries, or mixing future-phase features into the MVP.

---

## Builder Operating Rules

1. Work in one small task at a time.
2. Read the relevant docs before editing code.
3. Do not add a dependency unless the task explicitly allows it.
4. Do not implement future-phase features early.
5. Do not bypass the agent gateway, event log, policy engine, or tool broker.
6. Every meaningful action must produce an event.
7. Every risky action must pass policy review before execution.
8. Every task must include tests or a clear reason tests are not applicable.
9. Every task must update documentation when behaviour changes.
10. If unsure, create an ADR in `docs/adr/` rather than silently inventing behaviour.

---

## Recommended Build Loop

For each task:

```text
1. Read the task description.
2. List files expected to change.
3. Inspect existing code before editing.
4. Implement the smallest complete change.
5. Add or update tests.
6. Run formatting, linting, typing, and tests.
7. Verify acceptance criteria.
8. Summarise what changed.
9. Stop.
```

---

## Prompt Template For Builder Agents

Use this prompt when asking a local model to implement a task:

```text
You are implementing Raiker.

Before coding, read:
- README.md
- docs/ARCHITECTURE.md
- docs/CONTRACTS.md
- docs/PHASE_1_MVP_BUILD_PLAN.md
- docs/SECURITY_AND_POLICY.md
- docs/VERIFICATION_PLAN.md

Task ID: <TASK-ID>
Task title: <TITLE>
Scope: <EXACT SCOPE>
Allowed files: <FILES OR DIRECTORIES>
Forbidden changes: Do not implement future-phase features. Do not bypass policy or event logging. Do not add dependencies unless explicitly listed.
Acceptance criteria:
- <CHECK 1>
- <CHECK 2>
- <CHECK 3>

Process:
1. Inspect the current repo.
2. Explain the intended change briefly.
3. Implement only this task.
4. Add tests.
5. Run validation commands.
6. Report results and any follow-up items.
```

---

## Small-Model Anti-Drift Checklist

Before accepting a change, verify:

- [ ] The change matches a task in the build plan.
- [ ] No unplanned service, database, framework, or runtime was added.
- [ ] Public contracts remain compatible or are intentionally versioned.
- [ ] Tool execution still goes through the tool broker.
- [ ] Policy review happens before risky actions.
- [ ] Event logging wraps prompts, plans, tool proposals, approvals, denials, results, verification, errors, and checkpoints.
- [ ] Tests cover success and failure paths.
- [ ] The CLI still works for the basic prompt flow.
- [ ] Future features remain as stubs or interfaces only.

---

## Model-Specific Guidance

### Qwen 3.5 9B-class local builder

Use very small tasks. Prefer file-by-file changes. Avoid asking it to design architecture from scratch. Give it one target contract, one module, and one test file at a time.

Good task size:

```text
Implement EventLogWriter with append-only JSONL output and tests.
```

Bad task size:

```text
Build the full agent runtime, memory system, policy engine, and CLI.
```

### Gemma 4 31B-cloud-class builder

Can handle larger tasks, but still enforce phase boundaries. It may be asked to implement a complete slice, such as contracts + event log + tests, but should not be asked to implement the full platform in one pass.

---

## Definition Of Done For Any Builder Task

A task is done only when:

- code compiles or imports cleanly;
- tests pass;
- behaviour is observable through event logs;
- policy rules are not bypassed;
- errors are handled explicitly;
- documentation is updated where needed;
- the task remains inside its phase boundary.
