# Event Catalog

## Phase 3 Slice L — approval preview persistence readiness

Reserved metadata-only events:

- `phase3.approval_readiness.metadata_created`
- `phase3.approval_readiness.summary_viewed`
- `phase3.approval_readiness.exported`

These events are reserved for metadata-only readiness surfaces. They are not approval execution, approval relay runtime, durable approval queue, worker, scheduler, daemon, external channel, runtime execution, or approval action dispatch events.

Phase 3 remains incomplete. Phase 4 remains blocked.


## Phase 3 Slice M reserved metadata-only events

Reserved only for metadata: `phase3.storage_cleanup_readiness.created`, `phase3.storage_cleanup_readiness.summary_rendered`, and `phase3.storage_cleanup_readiness.exported`. No runtime cleanup, deletion, purge, tombstone, rollback, worker, scheduler, daemon, dispatch, or execution events are added. Phase 3 remains incomplete. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Phase 3 remains incomplete. Phase 4 remains blocked.

## Phase 3 Slice O reserved metadata-only events

Reserved event names only; no runtime dispatch events are introduced:

- `phase3.external_channels_notifications.readiness.metadata_defined`
- `phase3.external_channels_notifications.readiness.summary_rendered`
- `phase3.external_channels_notifications.readiness.sqlite_metadata_recorded`

These events are metadata-only reservations and do not represent channel dispatch, notification delivery, push notification, share-link, webhook, relay, worker, scheduler, daemon, or runtime execution events.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Slice P reserves metadata-only readiness surfaces and events for future remote/container/cloud execution. Reserved metadata-only events:

- `phase3.remote_container_cloud_readiness.metadata_created`
- `phase3.remote_container_cloud_readiness.summary_viewed`
- `phase3.remote_container_cloud_readiness.exported`

No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, approval relay, plugin execution, channel activation, cleanup execution, graph/codemap indexing, semantic memory writes, or runtime execution events are enabled. Phase 3 remains incomplete. Phase 4 remains blocked.
