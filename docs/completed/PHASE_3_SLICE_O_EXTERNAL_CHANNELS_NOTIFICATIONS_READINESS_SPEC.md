# Phase 3 Slice O: External Channels/Notifications Readiness — Metadata Only

## Slice name and purpose

Phase 3 Slice O defines deterministic metadata-only readiness surfaces for future external channels, notification delivery, push notifications, share links, webhook-style delivery, client transport readiness, and channel dispatch readiness.

## Scope

Slice O is readiness-only. It may create JSON-safe contracts, summaries, read-only CLI output, workspace-view fields, event-catalog reservations, and an optional SQLite metadata table. It must not activate runtime behavior.

## Required pre-enablement gates

Future work must define and independently approve policies for external channels, notifications, push delivery, share links, webhooks, client transports, hosted channels, hosted routines, approval relay runtime, channel relay runtime, workers/schedulers/daemons, data-exposure review, audit events, runtime execution, and tests.

## Required blockers

Readiness contracts must include a required non-empty blockers list. As long as blockers exist, readiness cannot become executable.

## Disabled runtime flags

All Slice O contracts must report these flags as `false`: external channels, notifications, push notifications, share links, webhook dispatch, client transport, hosted channels, hosted routines, approval relay runtime, channel relay runtime, notification workers, channel workers, worker queues, workers, schedulers, file watchers, daemons, and runtime execution.

## Non-goals

Slice O does not enable external channels, notification sending, push records, share links, webhook dispatch state, channel relays, hosted channels/routines, workers, queues, schedulers, watchers, daemons, plugin/server startup, cleanup execution, graph/codemap indexing, semantic memory writes, approval execution, remote/container/cloud execution, or marketplace installs.

## CLI/API/storage/workspace/catalog/event expectations

The `/channel-readiness` CLI is read-only and supports default, `--summary`, and `--json` modes. API helpers create/list/get/summarize/render metadata only. SQLite persistence is optional and limited to `phase3_external_channels_notifications_readiness`. Workspace inspection and views expose metadata-only flags and blocker counts. Event catalogs reserve Slice O metadata-only event names only.

## Acceptance criteria

Contracts are deterministic, JSON-safe, and use stable `ecnr_` readiness IDs. Registry listing is sorted. Invalid inputs raise clear `ValueError` exceptions. Runtime flags remain disabled. Forbidden runtime tables/events are absent.

## Test requirements

Tests must cover deterministic IDs, disabled flags, blocker validation, JSON-safe metadata validation, deterministic serialization, registry behavior, SQLite metadata table boundaries, CLI modes and invalid usage, workspace summaries, and docs/catalog/event consistency.

## Phase status

Phase 3 remains incomplete after Slice O. Phase 4 remains blocked until Phase 3 is complete and runtime enablement gates are explicitly satisfied in a later approved slice.
