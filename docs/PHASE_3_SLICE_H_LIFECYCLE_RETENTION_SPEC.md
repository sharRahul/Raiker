# Phase 3 Slice H — Lifecycle Retention, Cleanup, and Approval-Handoff Planning

Slice H extends Slice G lifecycle metadata with retention policies, cleanup previews, expiry/supersede counts, and approval-handoff planning. It is metadata-only, preview-only, read-only, and non-executing.

## Contracts

- `StorageLifecycleRetentionPolicy`: deterministic `slrp_` ID, lifecycle target type, retention class, expiry rule, cleanup eligibility, legal/manual hold flags, redacted reason summary, metadata-only flag, and disabled runtime execution flags.
- `StorageLifecycleCleanupPreview`: deterministic `slcp_` ID, linked lifecycle IDs, expired/superseded candidate counts, redacted summaries, `can_cleanup_now=false`, `cleanup_execution_enabled=false`, and all graph/memory/vector/embedding/rollback/plugin/channel/subagent/remote/container execution disabled.
- `StorageLifecycleApprovalHandoff`: deterministic `slah_` ID, linked lifecycle IDs, source preview/audit/rollback IDs, target capability, approval state (`handoff_planned`, `blocked`, `requires_future_policy`), `can_execute_now=false`, `execution_enabled=false`, and redacted summary only.

## Runtime boundary

Slice H does not execute lifecycle cleanup, graph/codemap indexing, graph writes, semantic memory writes, vector writes, embedding creation/storage, rollback, plugin code, MCP/LSP/plugin servers, monitors, external channels, approval relay, subagents, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, or share links.
