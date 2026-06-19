# Event Catalog

## Phase 3 Slice L — approval preview persistence readiness

Reserved metadata-only events:

- `phase3.approval_readiness.metadata_created`
- `phase3.approval_readiness.summary_viewed`
- `phase3.approval_readiness.exported`

These events are reserved for metadata-only readiness surfaces. They are not approval execution, approval relay runtime, durable approval queue, worker, scheduler, daemon, external channel, runtime execution, or approval action dispatch events.

Slice L did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Phase 3 Slice M reserved metadata-only events

Reserved only for metadata: `phase3.storage_cleanup_readiness.created`, `phase3.storage_cleanup_readiness.summary_rendered`, and `phase3.storage_cleanup_readiness.exported`. No runtime cleanup, deletion, purge, tombstone, rollback, worker, scheduler, daemon, dispatch, or execution events are added. Slice M did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

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

No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, approval relay, plugin execution, channel activation, cleanup execution, graph/codemap indexing, semantic memory writes, or runtime execution events are enabled. Slice P did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Minimal terminal shell/status rendering only; rich panels are specified, not implemented as a full app. | Partial/minimal | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |


## Phase 2.5 local code-review workflow events

The Phase 2.5 local code-review workflow (`/review`) emits metadata-only events. Payloads never
contain raw diffs, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, or
raw tool output. Allowed payload fields: `review_id`, `mode`, `files_reviewed`, `findings_count`,
`severity_counts`, `truncated`, `redaction_applied`, `untracked_count`.

| Event | When | Payload |
|---|---|---|
| `review_started` | A local review begins. | `review_id`, `mode` |
| `review_completed` | A local review finishes successfully. | `review_id`, `mode`, `files_reviewed`, `findings_count`, `severity_counts`, `truncated`, `redaction_applied`, `untracked_count` |
| `review_failed` | A local review raises an error. | `mode`, `error_class` |

Review is local CLI-only and read-only. It does not enable plugin execution, graph/codemap indexing,
semantic/vector memory writes, external channels, notifications, remote/container/cloud execution,
process/shell/network execution, or any runtime execution; those flags remain false.
