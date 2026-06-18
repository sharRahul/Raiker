# Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only

## Purpose
Slice K adds deterministic, metadata-only readiness surfaces for future semantic memory, vector, and embedding writes. It does not enable runtime write behavior.

## Scope
The slice is readiness-only and metadata-only. Contracts, registries, optional SQLite metadata persistence, CLI rendering, workspace summaries, docs, and reserved event catalog entries may describe readiness state only.

## Required pre-enablement gates
Future semantic memory writes require source scope, consent policy, sensitivity redaction, embedding provider policy, vector storage schema, retention policy, event catalog, approval policy, rollback plan, worker/scheduler plan, and tests.

## Required blockers
The readiness contract must keep a required, non-empty blockers list. Readiness must not become executable while any blocker remains, while Phase 3 is incomplete, or while Phase 4 is blocked.

## Disabled runtime flags
`ready_for_memory_writes`, `semantic_memory_writes_enabled`, `vector_writes_enabled`, `embedding_creation_enabled`, `embedding_storage_enabled`, `vector_indexing_enabled`, `memory_write_jobs_enabled`, `workers_enabled`, `schedulers_enabled`, `file_watchers_enabled`, `daemons_enabled`, and `runtime_execution_enabled` remain false.

## Non-goals
No semantic memory writes, vector writes, embedding creation/storage, vector indexes, vector records, memory write jobs, workers, schedulers, watchers, daemons, runtime execution, cleanup/rollback execution, graph/codemap indexing, graph writes, approval relay runtime, plugin execution, MCP/LSP/plugin server startup, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, or share links.

## CLI/API/storage/workspace/catalog/event expectations
`/memory-readiness`, `/memory-readiness --summary`, and `/memory-readiness --json` render metadata only. The Python API creates deterministic contracts and summaries. Optional SQLite persistence uses only `phase3_semantic_memory_readiness`; it is not a queue, vector table, embedding table, job table, worker table, scheduler table, daemon table, or runtime state table. Workspace inspection and views show metadata-only state, latest readiness ID, false runtime flags, and blocker counts. Event catalogs reserve metadata-only Slice K event names only and must not add runtime memory write events.

## Acceptance criteria
Readiness IDs are deterministic with the `smr_` prefix; metadata is JSON-safe; serialization and summaries are deterministic; invalid input raises `ValueError`; registry create/list/get/summary/render operations are read-only except optional metadata persistence; CLI invalid options return usage text safely.

## Test requirements
Tests cover deterministic IDs, disabled flags, required non-empty blockers, JSON-safe validation, deterministic serialization, registry behavior, SQLite metadata table presence, forbidden runtime table absence, CLI modes, invalid CLI usage, workspace summary fields, and docs/catalog consistency where supported.

## Phase status
Phase 3 remains incomplete. Phase 4 remains blocked.
