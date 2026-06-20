# Phase 3 Slice M: Storage Cleanup Execution Readiness — Metadata Only

## Slice name and purpose

Phase 3 Slice M defines storage cleanup execution readiness metadata. It creates deterministic, read-only surfaces that describe what must be true before future cleanup execution can be considered.

## Metadata-only/readiness-only scope

Slice M is metadata-only and readiness-only. It records readiness IDs, blockers, required gates, disabled runtime flags, and JSON-safe contract metadata. It does not execute cleanup.

## Required pre-enablement gates

Future cleanup execution requires cleanup governance, retention-to-cleanup authorization, deletion safety, purge safety, tombstone policy, rollback policy, approval handoff policy, audit evidence policy, worker/scheduler/daemon policy, and complete test coverage.

## Required blockers

Blockers are required and non-empty while cleanup execution is disabled. A readiness record with no blockers is invalid.

## Disabled runtime flags

cleanup execution, deletion execution, purge execution, tombstone execution, rollback execution, cleanup jobs, deletion jobs, worker queues, workers, schedulers, file watchers, daemons, and runtime execution are all disabled.

## Explicit non-goals

Slice M does not add cleanup execution, deletion execution, purge execution, tombstone execution, rollback execution, cleanup jobs, deletion jobs, worker queues, workers, schedulers, file watchers, daemons, runtime execution, graph/codemap indexing, graph writes, semantic memory writes, vector writes, embeddings, approval execution, plugin execution, MCP/LSP/plugin server startup, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, or share links.

## CLI/API/storage/workspace/catalog/event expectations

The `/cleanup-readiness` CLI renders metadata only. API modules expose deterministic create/list/get/summary/render operations. SQLite persistence is optional and limited to `phase3_storage_cleanup_execution_readiness`. Workspace inspection and views include the latest readiness ID, metadata-only state, disabled flags, and blocker counts. Catalog and event docs reserve metadata-only Slice M events only.

## Acceptance criteria

Readiness IDs are deterministic and start with `scer_`; metadata is JSON-safe; serialization and summaries are deterministic; invalid input raises `ValueError`; registry listing is sorted; SQLite creates only the metadata table; CLI invalid options return usage; workspace views never imply execution is active.

## Test requirements

Tests must cover deterministic IDs, disabled runtime flags, required blockers, JSON-safe validation, deterministic serialization, registry behavior, SQLite table boundaries, `/cleanup-readiness` modes, invalid CLI usage, workspace fields, and docs/catalog/event consistency.

## Phase status

Phase 3 remains incomplete. Phase 4 remains blocked.
