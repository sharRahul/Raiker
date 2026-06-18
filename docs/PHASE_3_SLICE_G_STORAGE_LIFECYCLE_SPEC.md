# Phase 3 Slice G — Storage Lifecycle Preparation

This document is the detailed implementation and builder handoff spec for Phase 3 Slice G.

Slice G is a **metadata-only storage lifecycle preparation slice**. It adds deterministic lifecycle records and inspection surfaces that allow future graph/codemap indexing, semantic-memory write governance, approval-audit review, and rollback-plan tracking to be represented safely before any runtime write path exists.

Slice G does **not** complete Phase 3.

---

## Current implementation status

Status: `implemented_verified_locally_metadata_only`

Merged implementation source: PR #26, `Add Phase 3 storage lifecycle preparation`.

Implemented code surfaces:

- `raiker/storage/lifecycle.py`
- `raiker/storage/lifecycle_registry.py`
- `raiker/storage/migrations.py`
- `raiker/storage/sqlite.py`
- `raiker/cli/commands.py`
- `raiker/workspace/inspection.py`
- `raiker/workspace/views.py`
- `tests/test_phase_3_storage_lifecycle.py`

Implemented CLI surfaces:

```text
/storage-lifecycle
/storage-lifecycle --summary
/storage-lifecycle --graph
/storage-lifecycle --memory
```

Validation reported by PR #26:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python -m apps.cli.main --help
python -m apps.cli.main --prompt "Hello Raiker"
```

The PR reported `143 passed` locally. GitHub Actions remain paused due quota/run-limit exhaustion, so future local/cloud agents must not claim hosted CI validation unless workflows are re-enabled and executed.

---

## Non-negotiable safety boundary

Slice G must remain metadata-only.

The following remain disabled:

- graph/codemap runtime indexing;
- graph node/edge writes;
- graph/codemap background indexing, watchers, daemons, or schedulers;
- semantic memory durable writes;
- vector table writes;
- embedding generation;
- embedding storage;
- rollback execution;
- plugin code execution;
- MCP/LSP/plugin server startup unless a later phase explicitly enables it;
- monitors/watchers;
- external channels;
- subagent runtime execution;
- multi-agent team execution;
- remote/container/cloud execution;
- hosted routines, marketplace installs, hosted push notifications, and share links.

A lifecycle record may describe a future storage lifecycle, but it must not activate that lifecycle.

---

## Lifecycle record contract

`StorageLifecycleRecord` represents one metadata-only planning record.

Required properties:

- deterministic `lifecycle_id`;
- JSON-safe serialisation;
- allowed `record_type` validation;
- allowed `status` validation;
- secret-like value redaction;
- lifecycle source linkage where available;
- redacted summary/count metadata only;
- hardcoded disabled runtime write flags.

Allowed record types should cover at least:

- graph/codemap lifecycle metadata;
- semantic memory lifecycle metadata;
- approval preview lifecycle metadata;
- approval audit lifecycle metadata;
- rollback plan lifecycle metadata.

Allowed statuses should cover at least:

- `planned`;
- `active_metadata_only` or equivalent metadata-only inspection state;
- `expired`;
- `superseded`;
- denied/non-executable status where applicable.

Status changes must not execute any write path. `expire` and `supersede` are metadata status changes only.

---

## Deterministic ID requirements

Lifecycle IDs must be stable for the same redacted logical payload.

Builder requirements:

1. Use stable JSON canonicalisation.
2. Sort dictionary keys.
3. Avoid process-random data in ID inputs.
4. Do not include raw secrets or raw candidate content in ID inputs.
5. Include enough source metadata to avoid collisions across graph, memory, audit, and rollback lifecycle records.
6. Keep the ID prefix stable and documented.

Tests must prove repeated construction from the same source payload yields the same `lifecycle_id`.

---

## Redaction requirements

Lifecycle records must store only safe summaries.

Never store raw:

- API keys;
- tokens;
- passwords;
- private keys;
- credential filenames or values;
- secret-looking memory candidates;
- raw prompt bodies containing credentials;
- raw rollback payloads if they contain sensitive values.

Allowed metadata:

- record type;
- target capability;
- status;
- redacted summary string;
- counts;
- source IDs;
- safe reasons;
- disabled runtime-write booleans;
- timestamps if deterministic/test-safe or externally supplied.

---

## Conversion helper requirements

Slice G includes helper conversions from:

- approval previews;
- approval audit records;
- rollback plans.

Conversion rules:

1. Preserve source IDs and source type.
2. Preserve target capability.
3. Preserve safe reason labels.
4. Store count metadata instead of raw payloads.
5. Store redacted summary only.
6. Set runtime write flags to false.
7. Set `can_execute_now=false` / equivalent where present.
8. Avoid creating graph nodes, graph edges, vectors, embeddings, or durable semantic-memory records.

---

## In-memory registry/service requirements

`raiker/storage/lifecycle_registry.py` is the current metadata-only service.

Required operations:

- `create_lifecycle_record`;
- `list_lifecycle_records`;
- `get_lifecycle_record`;
- `expire_lifecycle_record`;
- `supersede_lifecycle_record`;
- `storage_lifecycle_summary`;
- `render_lifecycle_summary`;
- workspace seeding from current preview/audit/rollback generators.

Registry behavior:

- deterministic output ordering;
- JSON-safe output;
- redacted summaries;
- no persistence of secrets;
- no runtime writes;
- no background jobs;
- no file-system mutation except the safe SQLite schema migration when storage is explicitly initialised;
- helpful errors for unknown lifecycle IDs.

---

## SQLite metadata schema boundary

Slice G may create metadata-only SQLite tables:

```text
phase3_storage_lifecycle
phase3_storage_lifecycle_events
```

Allowed table purpose:

- lifecycle metadata;
- lifecycle metadata events;
- status history;
- redacted source summaries;
- disabled runtime-write flags.

Explicitly forbidden in Slice G:

- graph node tables;
- graph edge tables;
- vector tables;
- embedding tables;
- semantic-memory durable write tables;
- rollback execution tables;
- plugin execution tables;
- external-channel tables that imply active channel runtime.

Migrations must be idempotent and safe to run repeatedly.

---

## Workspace integration requirements

Workspace inspection and workspace views must include lifecycle summaries in read-only form.

Required workspace summary fields should expose:

- total lifecycle record count;
- graph lifecycle count;
- memory lifecycle count;
- audit lifecycle count;
- rollback lifecycle count;
- expired/superseded counts;
- metadata-only flag;
- runtime write disabled flags.

The workspace view must not imply that graph indexing, semantic/vector writes, embeddings, or rollback execution are available.

---

## CLI rendering requirements

`/storage-lifecycle` must render read-only lifecycle metadata.

Required behavior:

```text
/storage-lifecycle
```

Shows safe lifecycle record summaries.

```text
/storage-lifecycle --summary
```

Shows aggregate metadata-only counts and disabled runtime write flags.

```text
/storage-lifecycle --graph
```

Shows graph/codemap lifecycle metadata only. It must state that graph runtime indexing remains disabled.

```text
/storage-lifecycle --memory
```

Shows semantic-memory lifecycle metadata only. It must state that semantic/vector writes and embeddings remain disabled.

Unknown arguments must return helpful usage output and must not fail with a stack trace.

---

## Event catalog requirements

Slice G reserves metadata lifecycle event names only.

Required events:

- `phase3.storage.lifecycle.record_planned`;
- `phase3.storage.lifecycle.record_listed`;
- `phase3.storage.lifecycle.record_expired`;
- `phase3.storage.lifecycle.record_superseded`;
- `phase3.storage.lifecycle.runtime_write_denied`.

Event payloads must be JSON-safe and redacted. Events must never include raw secrets, raw candidate memory, raw rollback payloads, vectors, embeddings, or graph records.

---

## Acceptance tests required for Slice G

Tests must prove:

1. lifecycle IDs are deterministic;
2. lifecycle records serialise to JSON;
3. secret-like values are redacted;
4. allowed record/status validation rejects invalid values;
5. runtime write flags remain disabled;
6. helper conversions from approval previews store summaries only;
7. helper conversions from approval audit records store summaries only;
8. helper conversions from rollback plans store summaries only;
9. registry create/list/get output is deterministic;
10. expire/supersede are metadata status changes only;
11. CLI surfaces render read-only metadata;
12. CLI usage errors are helpful;
13. workspace inspection includes lifecycle summary;
14. workspace views include lifecycle summary;
15. graph indexing remains disabled;
16. semantic/vector writes remain disabled;
17. embeddings are not created;
18. rollback execution remains disabled;
19. SQLite metadata tables are safe and idempotent;
20. no graph node/edge/vector/embedding tables are introduced.

---

## What local/cloud coding agents must not do next

Agents must not interpret Slice G as permission to implement runtime storage writes.

Do not add:

- graph indexing workers;
- file watchers;
- background graph daemons;
- vector databases;
- embedding providers;
- semantic memory durable writes;
- rollback execution;
- external channels;
- subagents;
- multi-agent teams;
- remote/container/cloud runners.

Next work must continue incrementally with explicit contracts, tests, docs, and disabled-by-default runtime flags.

---

## Suggested next slice candidates

Safe next slices may include one of the following, but only after docs/tests are updated first:

1. **Slice H — Lifecycle retention and cleanup planning**: add retention rules, cleanup previews, and expiry policy docs; still no runtime graph/memory/vector writes.
2. **Slice H — Lifecycle approval handoff contracts**: connect storage lifecycle metadata to future approval queues without executing writes.
3. **Slice H — Durable metadata-only lifecycle persistence review**: add safe query/read surfaces for the existing metadata tables; still no graph/vector tables.
4. **Slice H — Validation hardening**: add richer tests for schema idempotency, redaction, and CLI/workspace parity.

Any Slice H plan must preserve the non-activation rule.

## Phase 3 Slice H lifecycle retention update

Slice H adds metadata-only lifecycle retention policies, cleanup previews, expiry/supersede counts, and approval-handoff planning. The read-only commands are `/storage-lifecycle-retention`, `/storage-lifecycle-retention --summary`, `/storage-lifecycle-cleanup-preview`, `/storage-lifecycle-cleanup-preview --summary`, `/storage-lifecycle-handoff`, and `/storage-lifecycle-handoff --summary`. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, or remote/container/cloud execution.
