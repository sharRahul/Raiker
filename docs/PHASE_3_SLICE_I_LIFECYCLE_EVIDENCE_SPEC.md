# Phase 3 Slice I — Lifecycle Evidence, Export, Filtering, and Policy Simulation

Slice I adds metadata-only lifecycle evidence bundles and policy simulations for Slice G/H lifecycle records. It is the source of truth for evidence/export and policy-simulation behavior.

## Contracts

`StorageLifecycleEvidenceBundle` creates deterministic `sleb_` IDs from canonical JSON after secret-like fields are redacted. Bundles include source lifecycle, retention policy, cleanup preview, and approval handoff IDs; record/status counts; disabled execution flags; and a redacted summary. Bundles are `metadata_only`, `export_only`, cannot execute now, and have execution disabled.

`StorageLifecyclePolicySimulation` creates deterministic `slps_` IDs from canonical JSON after redaction. Simulations include policy/cleanup-preview inputs, simulated outcome counts, blocked reasons, required future policy, and explicit disabled execution flags. Simulations are metadata-only and simulation-only.

## Registry and CLI

The registry may store metadata-only evidence/simulation records in process memory for inspection, listing, summaries, and deterministic JSON rendering. Missing IDs return `None`; list output is deterministically sorted. CLI commands are read-only/export-only/simulation-only:

- `/storage-lifecycle-evidence`
- `/storage-lifecycle-evidence --summary`
- `/storage-lifecycle-evidence --json`
- `/storage-lifecycle-policy-simulation`
- `/storage-lifecycle-policy-simulation --summary`
- `/storage-lifecycle-policy-simulation --json`

Supported filters are display filters only: `--status`, `--target`, and `--limit`.

## SQLite metadata tables

Allowed Slice I tables are:

- `phase3_storage_lifecycle_evidence_bundles`
- `phase3_storage_lifecycle_policy_simulations`
- `phase3_storage_lifecycle_evidence_events`

These tables are idempotent metadata/export storage only. They are not graph, vector, embedding, semantic-memory durable-write, rollback-execution, plugin-execution, channel-runtime, approval-relay, remote, container, or cloud execution tables.

## Workspace summary fields

Workspace inspection and views expose evidence/simulation counts, latest IDs, and disabled execution flags. All execution fields remain false.

## Disabled runtime boundary and non-goals

Slice I does not execute cleanup; graph/codemap indexing; graph writes; semantic/vector memory writes; embedding generation/storage; rollback; plugins; MCP/LSP/plugin servers; monitors; external channels; approval relay; subagents; multi-agent teams; remote/container/cloud execution; hosted routines; marketplace installs; push notifications; or share links. It does not mark Phase 3 complete.

## Validation

Tests must prove deterministic IDs, JSON safety, redaction before ID generation/serialization, stable ordering, CLI usage handling, allowed SQLite tables, forbidden runtime table absence, and disabled execution flags.
