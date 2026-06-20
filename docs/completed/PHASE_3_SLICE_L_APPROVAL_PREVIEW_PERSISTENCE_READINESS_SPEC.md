# Phase 3 Slice L — Approval Preview Persistence Readiness — Metadata Only

Slice L defines deterministic, metadata-only readiness surfaces for future durable approval preview persistence.
It does not enable approval execution, approval relay runtime, approval preview execution, durable approval queues, workers, schedulers, file watchers, daemons, hosted routines, external channels, or runtime approval actions.

## Scope

The slice is readiness-only and metadata-only. It adds a deterministic contract, metadata registry, optional SQLite metadata table, read-only CLI rendering, workspace inspection/view summaries, and catalog/event documentation.

## Required pre-enablement gates

Future durable approval preview persistence must not be enabled until approval governance policy, preview schema, durable metadata storage review, retention, audit events, access control, relay runtime policy, queue/worker/scheduler policy, rollback policy, and test coverage are complete.

## Required blockers

Readiness records must include a non-empty blockers list. These blockers prevent readiness from becoming executable and keep `ready_for_persistence: false`.

## Disabled runtime flags

`approval_preview_persistence_enabled`, `approval_execution_enabled`, `approval_relay_runtime_enabled`, `approval_preview_execution_enabled`, `durable_approval_queues_enabled`, `approval_workers_enabled`, `schedulers_enabled`, `file_watchers_enabled`, `daemons_enabled`, and `runtime_execution_enabled` are always false.

## Non-goals

Slice L does not execute approvals, persist executable approval actions, start approval relay runtime, create durable approval queues, start workers/schedulers/watchers/daemons, run cleanup or rollback, write graph/codemap/semantic/vector data, create embeddings, execute plugins, start MCP/LSP/plugin servers, launch remote/container/cloud execution, run hosted routines, install marketplace packages, send push notifications, or create share links.

## CLI/API/storage/workspace/catalog/event expectations

The `/approval-readiness [--summary|--json]` command renders metadata only. The registry supports create/list/get/summary/render JSON-safe metadata operations. Optional SQLite persistence uses `phase3_approval_preview_persistence_readiness` and must not represent executable approval queues, relay runtime state, workers, schedulers, daemons, external channels, runtime execution state, or approval action dispatch. Workspace inspection and views show metadata-only readiness state, disabled flags, latest readiness ID, and blocker counts. Catalogs reserve Slice L metadata-only events only.

## Acceptance criteria

Readiness IDs are deterministic and begin with `appr_`; metadata is JSON-safe; serialization and summaries are deterministic; invalid input raises `ValueError`; blockers are required and non-empty; all runtime flags remain false; workspace and CLI surfaces do not imply active persistence or execution.

## Test requirements

Tests must cover deterministic IDs, disabled runtime flags, blocker validation, JSON-safe metadata validation, deterministic serialization, registry operations, optional SQLite table creation, forbidden runtime table absence, CLI modes and invalid usage, workspace inspection/view summaries, and docs/catalog/event consistency.

Phase 3 remains incomplete. Phase 4 remains blocked.
