# Phase 3 Slice H — Lifecycle Retention, Cleanup, and Approval-Handoff Planning

Slice H extends Slice G lifecycle metadata with retention policies, cleanup previews, expiry/supersede counts, and approval-handoff planning. It is metadata-only, preview-only, read-only, and non-executing. Phase 3 remains incomplete; Slice H does not mark Phase 3, Phase 4, or Phase 5 complete.

## Source-of-truth placement

- This spec owns the detailed Slice H contract and safety boundary.
- `docs/EVENT_CATALOG.md` owns event names.
- `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` owns slash-command definitions.
- `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` owns SQLite table definitions.
- `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md` owns the tool/command inventory, permissions, and implementation status.
- `docs/IMPLEMENTATION_STATUS.md`, `docs/LOCAL_VALIDATION_GATE.md`, and `docs/VERIFICATION_PLAN.md` own status and validation summaries.

## Contracts

- `StorageLifecycleRetentionPolicy`: deterministic `slrp_` ID, lifecycle target type, retention class, expiry rule, cleanup eligibility, legal/manual hold flags, redacted reason summary, metadata-only flag, and disabled runtime execution flags.
- `StorageLifecycleCleanupPreview`: deterministic `slcp_` ID, linked lifecycle IDs, expired/superseded candidate counts, redacted summaries, `can_cleanup_now=false`, `cleanup_execution_enabled=false`, and all graph/memory/vector/embedding/rollback/plugin/channel/subagent/remote/container execution disabled.
- `StorageLifecycleApprovalHandoff`: deterministic `slah_` ID, linked lifecycle IDs, source preview/audit/rollback IDs, target capability, approval state (`handoff_planned`, `blocked`, `requires_future_policy`), `can_execute_now=false`, `execution_enabled=false`, and redacted summary only.

All contracts must be JSON-safe after redaction. IDs are derived from canonical redacted payloads, never random UUIDs or raw secret-bearing metadata.

## Runtime boundary

Slice H explicitly disables:

- cleanup execution;
- graph/codemap runtime indexing;
- graph node/edge writes;
- semantic memory durable writes;
- vector writes;
- embedding generation/storage;
- rollback execution;
- plugin execution;
- MCP/LSP/plugin server startup;
- monitor/watch daemon activation;
- external channels;
- approval relay;
- subagents and multi-agent teams;
- remote/container/cloud execution;
- hosted routines;
- marketplace installs;
- hosted push notifications;
- share links.

## Registry and service behavior

The lifecycle registry/service supports create/list/get operations for retention policies, cleanup previews, and approval handoffs. Lists are deterministic and read-only summaries may be rendered in CLI and workspace views. Workspace defaults may be seeded from Slice G lifecycle records, but seeding creates only metadata records and must not start runtime indexing, cleanup, approval relay, rollback, plugin, channel, subagent, or remote/container/cloud execution. Missing IDs must return helpful not-found behavior instead of stack traces.

## CLI commands

The Slice H CLI surface is read-only/planning-only:

- `/storage-lifecycle-retention`
- `/storage-lifecycle-retention --summary`
- `/storage-lifecycle-cleanup-preview`
- `/storage-lifecycle-cleanup-preview --summary`
- `/storage-lifecycle-handoff`
- `/storage-lifecycle-handoff --summary`

Unsupported arguments must render helpful usage output.

## SQLite metadata boundary

Slice H may create only these idempotent metadata tables:

- `phase3_storage_lifecycle_retention`
- `phase3_storage_lifecycle_cleanup_previews`
- `phase3_storage_lifecycle_approval_handoffs`
- `phase3_storage_lifecycle_retention_events`

Slice H must not add graph node tables, graph edge tables, vector tables, embedding tables, semantic-memory durable-write tables, rollback execution tables, plugin execution tables, external-channel runtime tables, or remote/container/cloud execution tables.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.
