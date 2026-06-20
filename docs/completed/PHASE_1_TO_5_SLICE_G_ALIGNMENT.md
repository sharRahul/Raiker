# Phase 1 to Phase 5 Slice G Alignment

This document explains how Phase 3 Slice G affects every Raiker phase without rewriting the original phase scope documents.

Slice G is metadata-only. It adds lifecycle records and read-only lifecycle summaries. It does not activate graph indexing, semantic/vector writes, embeddings, rollback execution, plugins, channels, subagents, remote execution, container execution, or hosted execution.

---

## Phase 1 impact

Phase 1 remains the secure local runtime core.

Slice G relies on Phase 1 foundations:

- deterministic IDs;
- SQLite bootstrap;
- append-only event logging;
- static policy review;
- tool broker boundaries;
- equal-interface metadata.

Phase 1 is not changed by Slice G. Builders must not interpret the new lifecycle metadata tables as Phase 1 runtime graph, memory, or execution tables.

---

## Phase 2 impact

Phase 2 remains the rich local workspace foundation.

Slice G relies on Phase 2 foundations:

- tasks and event inspection;
- checkpoint timeline concepts;
- approval inbox concepts;
- memory candidate listing;
- local validation gate.

Phase 2 is not changed by Slice G. Lifecycle status changes are metadata-only and must not trigger task execution, checkpoint rollback, memory writes, or file mutations.

---

## Phase 3 impact

Phase 3 remains incomplete.

Slice G is the current Phase 3 storage lifecycle preparation slice. It follows:

```text
Slice C graph/codemap dry-run planning
  -> Slice D semantic-memory review queue
    -> Slice E approval previews
      -> Slice F approval audit and rollback planning
        -> Slice G storage lifecycle metadata
```

Slice G adds metadata-only lifecycle records that connect the previous planning/preview/audit/rollback surfaces to a storage lifecycle concept. It does not activate the lifecycle.

Canonical details are in `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md`.

---

## Phase 4 impact

Phase 4 remains incomplete and disabled except for safe planning/inspection surfaces.

Phase 4 builders may show lifecycle metadata in future channel, subagent, team, monitor, remote execution, container execution, or dashboard surfaces only as read-only status.

Phase 4 builders must not use lifecycle records to:

- start external channels;
- relay approvals over channels;
- spawn subagents;
- coordinate multi-agent work;
- start monitors/watchers;
- run remote/container execution;
- trigger rollback execution;
- trigger graph indexing or memory writes.

---

## Phase 5 impact

Phase 5 now has a dedicated build plan: `docs/PHASE_5_BUILD_PLAN.md`.

Phase 5 builders may add managed retention, archive, export, backup/restore, and audit governance around lifecycle metadata. They must not convert Slice G metadata into executable hosted jobs or marketplace-triggered runtime behavior.

Allowed Phase 5 work around Slice G:

- redacted audit export;
- integrity hashing;
- managed retention;
- backup/restore manifests;
- dashboard reporting;
- managed policy that keeps lifecycle execution disabled.

Forbidden Phase 5 work without a later explicit task:

- hosted routine execution from lifecycle records;
- marketplace plugin activation from lifecycle records;
- cloud/GPU execution from lifecycle records;
- graph/memory/vector/embedding writes from lifecycle records.

---

## Builder rule

If a coding agent touches lifecycle code, lifecycle docs, lifecycle migrations, lifecycle CLI output, lifecycle workspace summaries, or future Slice H work, it must read:

```text
docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md
docs/SLICE_G_CODING_AGENT_HANDOFF.md
docs/BUILD_ORDER.md
docs/LOCAL_VALIDATION_GATE.md
docs/ACCEPTANCE_TESTS_BY_PHASE.md
docs/VERIFICATION_PLAN.md
```

If the task requires behavior not covered there, update docs before code.
