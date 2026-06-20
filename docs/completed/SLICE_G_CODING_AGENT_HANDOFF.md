# Slice G Coding Agent Handoff

This handoff tells local or cloud coding agents how to interpret the current Raiker state after Phase 3 Slice G.

Canonical detailed spec: `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md`.

Canonical tool/plugin inventory: `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`.

---

## Current state

Phase 1 and Phase 2 remain `implemented_verified`.

Phase 3 remains incomplete. Current implemented Phase 3 slices are safe foundations only:

- Slice A: read-only workspace inspection and plugin planning boundary.
- Slice B: read-only workspace view/API foundation.
- Slice C: graph/codemap governance and dry-run planning only.
- Slice D: semantic-memory governance and review queue only.
- Slice E: approval-preview UX/contracts only.
- Slice F: approval-audit and rollback planning only.
- Slice G: storage lifecycle metadata preparation only.

Phase 4 remains incomplete and disabled except for safe planning/inspection surfaces.

Phase 5 now has a dedicated build-plan document: `docs/PHASE_5_BUILD_PLAN.md`.

---

## Tool and plugin source of truth

Before adding, changing, or enabling any tool, command, plugin component, permission, lifecycle action, channel, subagent, remote runner, model/provider action, memory action, graph action, MCP/LSP adapter, monitor, schedule, notification, marketplace flow, or audit/export feature, a builder must update and reconcile `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`.

That catalog must answer four questions for each tool/plugin component:

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|

No tool or plugin component is considered documented unless those four fields exist.

---

## What Slice G added

Slice G added:

- deterministic lifecycle IDs;
- JSON-safe lifecycle metadata;
- allowed record/status validation;
- secret-like redaction;
- disabled runtime write flags;
- conversions from approval previews, approval audit records, and rollback plans;
- in-memory lifecycle registry/service;
- create/list/get/expire/supersede lifecycle metadata operations;
- workspace seeding from existing preview/audit/rollback sources;
- deterministic summaries and read-only rendering;
- safe SQLite metadata tables:
  - `phase3_storage_lifecycle`
  - `phase3_storage_lifecycle_events`
- CLI commands:
  - `/storage-lifecycle`
  - `/storage-lifecycle --summary`
  - `/storage-lifecycle --graph`
  - `/storage-lifecycle --memory`
- workspace inspection/view lifecycle summaries;
- tests in `tests/test_phase_3_storage_lifecycle.py`.

---

## What Slice G did not add

Slice G did not add:

- graph indexing execution;
- graph node/edge writes;
- background indexers;
- file watchers;
- semantic memory durable writes;
- vector writes;
- embedding creation;
- rollback execution;
- plugin execution;
- MCP/LSP/plugin server startup;
- monitor/watch daemon activation;
- external channels;
- subagent runtime execution;
- multi-agent team execution;
- remote/container/cloud execution;
- hosted routines, marketplace installs, hosted push notifications, or share links.

---

## Required docs to read before changing this area

A builder must read these docs in order:

```text
README.md
  -> docs/IMPLEMENTATION_STATUS.md
  -> docs/BUILD_ORDER.md
  -> docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md
  -> docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md
  -> docs/PHASE_1_TO_5_SLICE_G_ALIGNMENT.md
  -> docs/PHASE_3_BUILD_PLAN.md
  -> docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/API_AND_CONTRACT_SCHEMAS.md
  -> docs/EVENT_CATALOG.md
  -> docs/MEMORY_GOVERNANCE_RULES.md
  -> docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md
  -> docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> docs/ACCEPTANCE_TESTS_BY_PHASE.md
  -> docs/VERIFICATION_PLAN.md
  -> docs/LOCAL_VALIDATION_GATE.md
```

If any of these conflict, stop and update docs before coding.

---

## Required validation for any next change

Minimum validation while GitHub Actions are paused:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python -m pytest tests/test_phase_3_storage_lifecycle.py
python -m apps.cli.main --help
python -m apps.cli.main --prompt "Hello Raiker"
```

Required CLI smoke coverage:

```text
/storage-lifecycle
/storage-lifecycle --summary
/storage-lifecycle --graph
/storage-lifecycle --memory
/workspace
/workspace-view
/graph-status
/graph-plan
/memory-review --summary
/approval-previews
/approval-audit --summary
/rollback-plan
```

---

## Required invariants for the next PR

The next PR must explicitly confirm:

- no plugin execution was enabled;
- no graph/codemap runtime indexing was enabled;
- no graph node/edge write path was added;
- no semantic/vector memory write path was added;
- no embedding generation or embedding storage was added;
- no rollback execution was enabled;
- no external channel runtime was enabled;
- no subagent or multi-agent runtime was enabled;
- no remote/container/cloud execution was enabled;
- lifecycle status changes remain metadata-only;
- lifecycle records store redacted summaries/counts only;
- `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md` was updated if any tool/plugin status, permission, or description changed;
- local/cloud validation evidence is included.

---

## Recommended next Codex target

The safest next target is **Phase 3 Slice H: Lifecycle Retention, Cleanup, and Approval-Handoff Planning**.

Slice H should add contracts, docs, tests, and read-only/preview-only surfaces for lifecycle retention and approval handoff. It must not enable runtime graph indexing, semantic/vector writes, embeddings, rollback execution, plugins, channels, subagents, or remote/container execution.

## Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.
