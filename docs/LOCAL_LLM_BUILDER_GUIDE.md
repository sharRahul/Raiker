# Local LLM Builder Guide

This guide is written for local and cloud coding agents that need to implement Raiker in small, reliable steps.

The goal is to reduce ambiguity so the builder can implement Raiker task-by-task without inventing architecture, skipping security boundaries, or confusing phase scheduling with missing design.

---

## Builder Operating Rules

1. Work in one small task at a time.
2. Read the relevant docs before editing code.
3. Do not add a dependency unless the task explicitly allows it.
4. Implement only the selected task's build phase.
5. Treat phase-scheduled features as fully specified but not wired unless the task says to wire them.
6. Do not bypass the agent gateway, event log, policy engine, storage layer, or tool broker.
7. Every meaningful action must produce an event.
8. Every risky action must pass policy review before execution.
9. Every task must include tests or a clear reason tests are not applicable.
10. Every task must update documentation when behaviour changes.
11. If unsure, create an ADR in `docs/adr/` rather than silently inventing behaviour.

---

## Required Reading Flow

For every task, read in this order:

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

Task-specific specs include tools, commands, UI, model runtime, channels, memory, eidetic learning, graph, plugins, hooks, execution environments, or multi-agent strategy depending on the task.

---

## Recommended Build Loop

For each task:

```text
1. Read the task description.
2. Identify phase, task ID, affected contracts, affected storage, affected events, policy gates, UI surface, and tests.
3. List files expected to change.
4. Inspect existing code before editing.
5. Implement the smallest complete change.
6. Add or update tests.
7. Run formatting, linting, typing, and tests.
8. Verify acceptance criteria.
9. Summarise what changed.
10. Stop.
```

---

## Prompt Template For Builder Agents

```text
You are implementing Raiker.

Before coding, read:
- README.md
- docs/FEATURE_COVERAGE_MATRIX.md
- docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
- docs/ARCHITECTURE.md
- docs/CONTRACTS.md
- docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
- docs/SECURITY_AND_POLICY.md
- docs/VERIFICATION_PLAN.md
- <TASK-SPECIFIC-DOC>

Task ID: <TASK-ID>
Task title: <TITLE>
Build phase: <PHASE>
Scope: <EXACT SCOPE>
Allowed files: <FILES OR DIRECTORIES>
Forbidden changes: Implement only this task's phase wiring. Do not bypass policy, storage, gateway, or event logging. Do not add dependencies unless explicitly listed.
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

## Anti-Drift Checklist

Before accepting a change, verify:

- [ ] The change matches a task in the build plan.
- [ ] The task's build phase is identified.
- [ ] Phase-scheduled specs were not mistaken for missing design.
- [ ] No unplanned service, database, framework, or runtime was added.
- [ ] Public contracts remain compatible or are intentionally versioned.
- [ ] Tool execution still goes through the tool broker.
- [ ] Policy review happens before risky actions.
- [ ] SQLite/event/checkpoint storage contracts are respected.
- [ ] Event logging wraps prompts, plans, tool proposals, approvals, denials, results, verification, errors, and checkpoints.
- [ ] Tests cover success and failure paths.
- [ ] The global `raiker` command still opens the TUI and reaches the gateway where relevant.
- [ ] Connector/model registries remain loadable.

---

## Task Size Guidance

Good task size:

```text
Implement EventLogWriter with append-only JSONL output and SQLite event index tests.
```

Bad task size:

```text
Build the full agent runtime, memory system, policy engine, and all UI clients.
```

---

## Definition Of Done For Any Builder Task

A task is done only when:

- code compiles or imports cleanly;
- tests pass;
- behaviour is observable through event logs;
- policy rules are not bypassed;
- SQLite/storage contracts are respected where relevant;
- errors are handled explicitly;
- documentation is updated where needed;
- the global `raiker` TUI entry path remains valid where relevant;
- the task remains inside its phase boundary.
