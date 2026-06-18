# Phase 3 Slice J — Graph/Codemap Indexing Readiness: Metadata Only

Slice J defines the source-of-truth readiness surface for graph/codemap indexing without enabling indexing.

## Scope

Implemented surfaces are metadata-only:

- deterministic readiness contract/model;
- in-process registry create/list/get/summary operations;
- read-only `/graph-readiness` terminal command;
- optional SQLite table `phase3_graph_codemap_readiness` for metadata contracts only;
- workspace inspection and workspace view summary fields;
- documentation and event catalog entries for future event names.

## Hard Runtime Boundary

Slice J must not enable graph indexing, graph writes, workers, schedulers, file watchers, daemons, or runtime jobs.

The readiness contract always reports:

- `metadata_only: true`
- `ready_for_indexing: false`
- `graph_indexing_enabled: false`
- `graph_writes_enabled: false`
- `runtime_jobs_enabled: false`
- `workers_enabled: false`
- `schedulers_enabled: false`
- `file_watchers_enabled: false`
- `daemons_enabled: false`

## Required Gates Before Future Enablement

Before graph/codemap indexing can ever be enabled, a later phase must satisfy and verify all readiness gates:

1. source scope defined;
2. path policy defined;
3. secret redaction defined;
4. incremental update strategy defined;
5. storage schema defined;
6. event catalog defined;
7. approval policy defined;
8. rollback plan defined;
9. worker/scheduler plan defined;
10. test coverage defined.

## Phase Status

Phase 3 remains incomplete. Phase 4 remains blocked. Slice J is a proof of readiness metadata only, not permission to start runtime indexing.
