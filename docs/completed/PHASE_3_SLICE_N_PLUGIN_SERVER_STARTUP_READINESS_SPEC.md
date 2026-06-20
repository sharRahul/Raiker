# Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

## Slice name and purpose
Slice N defines deterministic, metadata-only readiness surfaces for future plugin execution, plugin installation, plugin activation, MCP server startup, LSP server startup, plugin server startup, monitor daemon startup, hosted routines, marketplace installs, external channels, approval relay runtime, workers, schedulers, watchers, daemons, and runtime execution.

## Metadata-only scope
The slice is readiness-only. It creates contracts, summaries, optional SQLite metadata persistence, workspace fields, CLI output, documentation, and reserved metadata-only catalog/event entries. It does not execute runtime work.

## Required pre-enablement gates
Future startup cannot be considered until policies and tests exist for plugin execution, plugin installation, plugin activation, MCP server startup, LSP server startup, plugin server startup, monitor daemon startup, hosted routines, marketplace installs, external channels, approval relay runtime, worker queues, workers, schedulers, file watchers, daemons, runtime execution, audit evidence, and rollback/disablement.

## Required blockers
All missing gates remain blockers. Blockers are required and non-empty while readiness is disabled. Empty blockers are invalid input and must raise `ValueError`.

## Disabled runtime flags
`plugin_execution_enabled`, `plugin_installation_enabled`, `plugin_activation_enabled`, `mcp_server_startup_enabled`, `lsp_server_startup_enabled`, `plugin_server_startup_enabled`, `monitor_daemon_startup_enabled`, `hosted_routines_enabled`, `marketplace_installs_enabled`, `external_channels_enabled`, `approval_relay_runtime_enabled`, `worker_queues_enabled`, `workers_enabled`, `schedulers_enabled`, `file_watchers_enabled`, `daemons_enabled`, and `runtime_execution_enabled` are all false.

## Explicit non-goals
Slice N does not enable plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, hosted routines, marketplace installs, external channels, approval relay runtime, worker queues, workers, schedulers, file watchers, daemons, runtime execution, cleanup execution, deletion, purge, tombstones, rollback execution, graph/codemap indexing, graph writes, semantic memory writes, vector writes, embeddings, durable approval queues, remote/container/cloud execution, push notifications, or share links.

## CLI/API/storage/workspace/catalog/event expectations
`/plugin-readiness`, `/plugin-readiness --summary`, and `/plugin-readiness --json` render metadata only and include disabled runtime flags. The optional SQLite table `phase3_plugin_server_startup_readiness` stores readiness metadata only. Workspace inspection and views include latest readiness ID, blocker counts, metadata-only state, `ready_for_plugin_server_startup: false`, and disabled runtime flags. Catalogs and event catalogs reserve metadata-only Slice N events only.

## Acceptance criteria
Readiness IDs are deterministic with the `pssr_` prefix. Metadata is JSON-safe. Serialization and summaries are deterministic. Registry create/list/get/summary/render operations do not execute runtime behavior. SQLite contains only the metadata readiness table and no plugin/server/daemon/runtime tables.

## Test requirements
Tests must cover deterministic IDs, disabled runtime flags, blocker validation, JSON-safe metadata validation, deterministic serialization, registry behavior, SQLite boundaries, CLI modes and invalid usage, workspace fields, and docs/catalog/event consistency.

## Phase status
Phase 3 remains incomplete. Phase 4 remains blocked.
