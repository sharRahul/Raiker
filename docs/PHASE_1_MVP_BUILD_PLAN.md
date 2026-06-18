# Phase 1 MVP Build Plan

This plan decomposes Raiker Phase 1 into small implementation tasks suitable for local or cloud builder models.

This document is the single source of truth for Phase 1 build scope. The previous Phase 1 alignment addendum has been merged into this plan so builders do not need to reconcile separate Phase 1 instructions.

Phase 1 objective:

```text
Build a local agent runtime core opened first through the global `raiker` terminal command, with explicit contracts, deterministic state transitions, append-only event logging, SQLite bootstrap, static policy review, a tool broker for safe filesystem/search tools, approval-gated local action proposals, a mock model provider, checkpoint stubs, connector/model registries, and tests.
```

The Phase 1 terminal client is the first implementation target only. It is not the privileged human interface. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Phase 1 Alignment Rules

### Phase Scheduling Rule

Phase-scheduled features are fully specified elsewhere in the docs. Phase 1 does not wire those features into active behaviour, but it must preserve their contracts, registries, storage boundaries, gateway paths, event shapes, client metadata, and policy boundaries.

A builder must not treat phase scheduling as missing design, lower priority interface status, or permission to create a terminal-only architecture.

### Equal Primary Interface Rule

All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. This includes CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, chat clients, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients.

Phase 1 may implement the terminal client first, but no code, contract, event, policy rule, storage table, or runtime path may describe the terminal client as the only primary human interface or grant it a private bypass path.

### Global Command Rule

The final Phase 1 deliverable must expose the global `raiker` command. Running `raiker` must open the configured local terminal client.

During early bootstrapping, module-based commands may be used temporarily, but they must be documented as temporary and must not replace the final global command requirement.

### Builder Working Rule

When working on Phase 1, a builder must:

---

## Phase 3 Slice G impact on Phase 1

Phase 3 Slice G does not change Phase 1 scope or acceptance. Phase 1 remains the secure local runtime core with SQLite bootstrap and append-only event logging only.

Builders must understand the Slice G storage lifecycle tables as later-phase metadata-only additions. They are not Phase 1 graph tables, vector tables, semantic-memory write tables, or runtime execution tables.

Phase 1 invariants that still apply to Slice G and future slices:

- SQLite bootstrap does not imply permission to add active write paths.
- Tool broker and policy review remain mandatory before any action can execute.
- Event and storage schemas must be documented before implementation.
- Equal-interface metadata must be preserved even when later workspace/CLI surfaces expand.
- No terminal path may bypass the Agent Gateway to reach Slice G lifecycle metadata.

When a local or cloud builder starts from Phase 1 docs and sees Slice G references, it must continue to `docs/PHASE_3_SLICE_G_STORAGE_LIFECYCLE_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/EVENT_CATALOG.md`, and `docs/VERIFICATION_PLAN.md` before changing any lifecycle code.
