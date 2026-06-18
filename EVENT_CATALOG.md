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
