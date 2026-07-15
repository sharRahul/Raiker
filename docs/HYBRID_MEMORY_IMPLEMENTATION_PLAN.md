# Hybrid Memory Implementation Plan

## Status

This is the implementation contract for Raiker's archive-first, high-fidelity
memory system. It is intentionally incremental: existing governed memory,
SQLite event storage, project context, and capability gates remain the source
of truth until each phase below is implemented and verified.

All five phases below are implemented for the local SQLite deployment and
verified by focused lifecycle tests. The deliberate boundary remains: no
raw-content capture worker, automatic durable-memory promotion, unattended
cleanup, external graph service, or vector/HNSW deployment. Existing gated
vector/graph runtimes can register source-versioned projections while SQLite
remains authoritative and filters every recalled source record.

## Product rules

1. Raiker archives by default. Archive is reversible and excludes data from
   normal active views and retrieval.
2. Only a human can request forget or permanent purge. The model has no purge
   tool; it may only prepare a confirmation payload.
3. Important durable memories default to `until_forget`; temporary raw data
   expires unless explicitly promoted, pinned, or held.
4. Every recalled fact has provenance, scope, sensitivity, confidence,
   retention, and a source link. Recalled content remains data, never trusted
   instructions.
5. Retrieval is scope- and policy-filtered before ranking. Fast retrieval must
   never bypass user visibility, archive state, incognito, or sensitivity rules.

## Architecture

```text
user/tool/event
  -> immutable event or artifact reference
  -> eidetic observation (optional high-fidelity metadata)
  -> gist/candidate (reviewable compression)
  -> approved durable memory
  -> lexical/vector indexes and entity graph projections
  -> bounded, provenance-labelled retrieval context

project tree: parent_id + derived self-inclusive path
entity graph: nodes + typed many-to-many edges
```

The project tree is only for ownership, archive boundaries, sessions, and
nearest-ancestor context. Facts such as people, documents, decisions, and code
relationships belong in a separate graph projection. SQLite remains the
local-first primary database; external graph/vector backends are adapters, not
authoritative stores.

## Data contract

### Project hierarchy and inherited context

`projects.parent_id` is the structural authority. `projects.path` is a derived,
self-inclusive optimization. A project path always ends with `/`; therefore a
subtree query uses `path LIKE :node_path || '%'`.

`project_contexts.memory_mode` is one of:

| Value | Meaning |
|---|---|
| `inherit` | Use the nearest active ancestor's explicit setting; false if none exists. |
| `enabled` | Include approved memory in this project scope. |
| `disabled` | Exclude approved memory in this scope and descendants that inherit. |

Context merge is deterministic: instructions append root-to-leaf, attachment
references union/deduplicate root-to-leaf, and the nearest explicit scalar mode
wins. A recursive CTE is the correctness fallback; the materialized path is a
read optimization only.

### Memory lifecycle

Every memory-bearing record must have `record_id`, `scope`, `source_event_id`,
`sensitivity`, `retention_class`, `created_at`, `updated_at`, `archived_at`,
`forgotten_at`, and a content checksum or immutable artifact reference.

| State | Retrieval | Physical data |
|---|---|---|
| active | eligible when policy allows | retained |
| archived | excluded from default retrieval | retained and restorable |
| forgotten | excluded from all retrieval | tombstone plus governed purge queue |
| purged | unavailable | source, indexes, artifacts, and backup disposition recorded |

`purged` is a lifecycle result, not a plain SQL delete. It requires a user
confirmation bound to the exact target and impact summary, then records the
handling of database rows, FTS rows, vectors, graph edges, artifacts, exports,
and backups.

### Retention classes

| Class | Default use | Expiry |
|---|---|---|
| `turn_only` | scratch/tool intermediates | turn close |
| `short_term_7_days` | raw replay/debug evidence | seven days |
| `short_term_30_days` | project continuity | thirty days |
| `project_lifetime` | project decisions and approved gists | project remains retained |
| `until_forget` | user-pinned important information | user forgets/purges |
| `legal_hold` | managed exception | no automatic cleanup |

## Retrieval contract

Retrieval is bounded and follows this order:

1. current prompt, active task, and session summary;
2. explicit project context and direct scoped durable memories;
3. exact lexical search over active, permitted records;
4. entity-graph neighborhood when relationship traversal is requested;
5. semantic/vector candidates, reranked and policy-filtered;
6. raw observation only for an approved exact-replay request.

Each result carries its source ID, trust label, and token budget. Vector or
graph hit lists cannot reveal content that the normal governed read path would
deny. Retrieval never treats memory as system or user instruction.

## Delivery phases

### Phase A — hierarchy and context correctness

**Complete.** Self-inclusive paths, parent/path validation, deterministic
nearest-ancestor context merge, subtree isolation, and archive/restore tests
are in place.

- Migrate legacy paths to self-inclusive paths and validate parent/path parity.
- Add tri-state memory inheritance with backward-compatible Boolean input.
- Add archive/restore visibility and test sibling/subtree isolation.
- Acceptance: moves, archives, and deletes never affect siblings; nearest
  active explicit context setting is deterministic.

### Phase B — durable-memory lifecycle normalization

**Complete.** SQLite is the retrieval authority; Markdown is the readable
export/cache. Archive/restore, tombstones, human-confirmed purge preview and
disposition records are implemented. The model has no purge executor.

- Consolidate approved-memory metadata into SQLite as the retrieval authority;
  Markdown remains a human-readable export/cache, not a competing store.
- Add archive/restore and tombstone lifecycle fields and audit events.
- Add a human-only purge-preview endpoint listing dependent projections.
- Acceptance: archive and forget are reversible/tombstoned as specified;
  no agent-triggered hard delete path exists.

### Phase C — eidetic observations and gists

**Complete.** Eidetic records store only checksum/provenance/retention and an
optional artifact reference. Gists remain `pending_review`; owner-confirmed
expiry cleanup accepts only IDs returned by the preview and never touches a
durable memory.

- Persist raw observation metadata with immutable artifact refs, checksum,
  provenance, sensitivity, and retention class.
- Create reviewable gist candidates; only governed approval promotes a gist to
  durable memory.
- Add expiry preview and an owner-approved cleanup executor.
- Acceptance: sensitive raw content is redacted/skipped; raw expiry never
  silently deletes a promoted durable memory.

### Phase D — retrieval indexes and graph projection

**Complete.** SQLite FTS indexes only active durable records. Source-versioned
`fts`, `vector`, and `graph` projection mappings are lifecycle-aware; archive,
restore, forget, and purge update eligibility. Owner-started reconciliation
repairs mappings and rebuilds FTS. Actual vector/graph creation remains behind
the existing capability gates.

- Add SQLite FTS synchronization for active durable-memory records.
- Add vector and graph projections behind existing capability gates.
- Record projection source/version so archive, forget, correction, and purge
  fan out reliably.
- Acceptance: lexical, vector, and graph retrieval return only active,
  authorized source records and disclose provenance.

### Phase E — purge, backup disposition, and operations

**Complete.** Exact-ID human confirmation performs the purge and records both
completed locations and the retained-backup notice. Owner-started export,
import, and reconciliation are available; no cleanup/reconciliation daemon is
enabled.

- Implement the human-confirmed purge executor and dependency completion log.
- Define backup retention/disposition reporting; do not claim immediate backup
  erasure when a retained backup still contains data.
- Add export/import and integrity/reconciliation jobs that are owner-started.
- Acceptance: every purge reports completed and pending storage locations.

## Migration and rollout

1. Back up `.raiker/raiker.db` and record its checksum.
2. Apply additive migrations first; do not drop existing memory data.
3. Backfill/project-path validate in one transaction, with a read-only repair
   preview for inconsistent trees.
4. Keep old Boolean project-context API input for one release; emit only the
   tri-state field in new clients.
5. Build indexes from active source records only. Reconcile projection counts
   before enabling any retrieval gate.
6. Roll out each executor disabled by default, then owner-enable it after the
   phase's acceptance tests and audit checks are green.

## Security and safety requirements

- Foreign keys enabled for every SQLite connection; invalid parents fail closed.
- Project path is never used as the sole authorization decision.
- Archive is allowed only in the caller's granted scope; purge is human-only.
- Secrets/credentials are never automatically promoted to durable memory.
- Raw observations, external content, vector previews, graph properties, and
  imported data are untrusted model context.
- Cleanup is preview-first and idempotent. Legal/manual holds override expiry.
- Purge confirmations include target identity, subtree count, artifact count,
  index/projection count, and backup-disposition notice.

## Verification matrix

| Area | Required proof |
|---|---|
| hierarchy | sibling isolation, cycle rejection, path/parent parity, archive/restore |
| inheritance | root-to-leaf instructions, attachment union, nearest explicit mode |
| lifecycle | archive, forget/tombstone, restore, purged projection reconciliation |
| retrieval | scope/sensitivity/incognito/archive filtering before ranking |
| safety | no agent purge route; confirmation required; audit event completeness |
| migration | fresh install plus populated legacy database upgrade |
| quality | focused tests, full Python suite, ruff, mypy, web check/lint/test/build |

## Explicit non-goals for the first delivery

- No external Neo4j dependency.
- No automatic “remember everything forever” capture.
- No automatic hard-delete or cleanup worker.
- No vector/HNSW deployment until corpus size and latency measurements justify
  it; SQLite FTS and exact scoped retrieval come first.

## Production-readiness roadmap

The completed local-first delivery above is the foundation, not a claim of
market leadership. The following work is required before Raiker can make a
defensible production-grade memory claim. Each stage has an explicit exit
criterion; later stages do not weaken the completed safety rules.

### Deployment scope

Raiker is a self-hosted, multi-user application for a single personal device
or user-owned AI host: laptops, desktops, Macs, local AI devices, and optional
home NAS hardware. Each local user has a separate principal and workspace; it
is not a shared enterprise service or a hosted SaaS. Long-term backup is
opt-in: users may keep it local or select a NAS, mounted drive, or supported
cloud-storage provider. Raiker must encrypt and verify those backups, expose
their retention/deletion disposition, and never silently upload a workspace.

### Stage F — retrieval authority and measured quality

**In progress.** `RAIKER-2009` makes approved-memory SQLite rows and active-only
FTS authoritative for governed retrieval. `RAIKER-2010` adds immutable
correction/supersession links, temporal eligibility, human correction control,
and persisted aggregate lexical, vector, graph, and hybrid evaluation runs.
Each aggregate identifies its backend version, scope, workload, and a
non-sensitive latency distribution. `memory-eval-v1` reports
precision, Recall@k, MRR, nDCG, policy leaks, p50/p95 latency, token use, and
local compute/storage cost. Broader corpus workloads and production thresholds
remain pending. `memory-eval-v1` now provides a deterministic
scoped, sensitive, archived, forgotten, corrected, and time-qualified corpus
and CI enforces zero policy leaks plus exact
precision/recall for that corpus; broader workload, latency, and cost budgets
remain pending. `RetrievalBudget` now also gates token and retrieved-storage
regressions; production thresholds still require the live benchmark.

1. Make SQLite's active-memory row and its FTS record the single retrieval
   source; synchronize text, search opt-out, expiry, archive, forget, and
   correction in one transaction.
2. Add a versioned evaluation corpus with scoped, sensitive, archived,
   forgotten, corrected, and time-qualified cases.
3. Measure Precision@k, Recall@k, MRR, nDCG, policy-leak count, p50/p95
   latency, token use, and compute/storage cost per lexical, vector, graph,
   and hybrid strategy. Persist only aggregate, non-sensitive evaluation
   results.
4. Add correction/supersession links and valid-time/effective-time fields so a
   fact can be represented as `was_true`, `currently_true`, or `superseded`.
   Older facts remain evidence but are never preferred over an active
   correction.
5. Expose human controls for what is remembered, why it was proposed/approved,
   scope, sensitivity, retention/expiry, correction, archive, forget, and
   purge; record the responsible human and evidence IDs for each decision.

**Exit:** CI fails on a policy leak or an agreed quality/latency/cost regression
budget; every reported metric identifies corpus version, backend version,
scope, workload, and latency distribution.

### Stage G — gated semantic and entity retrieval

**In progress (first slice).** Active non-sensitive approved memories can now be projected
through the existing governed local-vector or provider-vector capability; the vector mapping and
entity graph edges are evidence-bound and lifecycle-filtered. The bounded hybrid
assembler deduplicates active lexical/vector/graph candidates. Provider-backed
runtime retrieval, entity extraction, and runtime integration remain pending.
Inferred relationship proposals are evidence-bound and remain in a human review
queue until an explicit approval creates the graph edge.

1. Implement approved-memory vector projection using the existing
   `vector_embedding_runtime` capability, with model/version, checksum, and
   projection mapping recorded for every vector.
2. Build a separate typed entity/relationship projection for people, projects,
   decisions, and documents; require evidence IDs and confidence on every edge.
3. Query lexical, vector, and graph candidates independently, enforce policy
   and scope before ranking, deduplicate by durable memory ID, then rerank with
   deterministic, observable weights.
4. Keep raw content out of runtime events and show source IDs/trust labels in
   the assembled context.
5. Route inferred facts through a human review queue. Sensitive, uncertain, or
   conflicting inferences must never auto-promote; consolidation may merge only
   when it preserves every source evidence ID, uncertainty, and prior version.

**Exit:** capability-off and policy-denied paths are proven no-ops; enabled
retrieval meets the Stage F recall/latency budgets without a visibility leak.

### Stage H — self-hosted multi-user security, backup, and privacy operations

**In progress (backup catalog slice).** Backup manifests now record encryption
key identifiers, retention/legal-hold state, restore verification, erasure
requests, and completed erasure. SQLite, FTS, and vector/graph metadata now
use SQLCipher through `pysqlcipher3static` (the `pysqlcipher3` DB-API); the
workspace app key derives the SQLCipher key and legacy plaintext databases are
converted without retaining a plaintext copy. This distribution provides FTS4,
not FTS5, so lexical ranking is deterministic recency order rather than BM25.
Memory and backup lifecycle actions are metadata-audited, and lifecycle-audit
rows are append-only at the SQLite layer. Raiker supports multiple local users
on one device through separate principals and workspaces, not enterprise
multi-tenant hosting. User-selected NAS, mounted-drive, and cloud backup
destinations remain pending.

1. Enforce principal and workspace ownership on every memory row, projection,
   export, backup, and maintenance job. Test cross-user/workspace reads,
   writes, retrieval, projection, export, backup, restore, and confused-deputy
   attempts on the same host.
2. Encrypt durable rows, artifacts, indexes, and backups at rest with a
   per-workspace data key. Define local device-owner/user recovery, key
   rotation, revocation, and access rules without requiring hosted enterprise
   KMS or SaaS accounts.
3. Add opt-in NAS, mounted-drive, and cloud-provider backup adapters. The
   catalog must record encrypted snapshots, destination, retention/hold
   deadlines, restore tests, erasure requests, deletion completion, and every
   backup still pending expiry or erasure.
4. Add immutable lifecycle audit records for recall, correction, export,
   import, archive, forget, purge, legal-hold changes, backup access, and admin
   access.

**Exit:** self-hosted security review, restoration and migration-rollback
drills, verified-erasure/pending-backup disposition drill, and same-device
multi-user isolation suite all pass with documented evidence.

### Stage I — reliability and scale

**In progress (maintenance slice).** An owner-started read-only integrity report
detects stale FTS/projection/graph state, checksum mismatches, orphaned or
missing Markdown artifacts, failed purge locations, and project path
inconsistencies. SQLite
now provides idempotent maintenance jobs with leases, retry/dead-letter state,
bounded one-at-a-time owner execution, and per-workspace rate limits for
reconciliation and integrity scans. Aggregate queue depth, worker state,
dead-letter count, and completion latency are available for monitoring. Memory lifecycle audit rows cover archive,
restore, forget, purge, and correction. Monitoring and load/failure exercises
remain pending.

1. Move projection/reconciliation work to owner-enabled, idempotent jobs with
   leases, retries, dead-letter reporting, bounded concurrency, per-workspace rate
   limits, and queue/worker/latency/error monitoring.
2. Add integrity scanners for orphaned artifacts, stale FTS/vector/graph rows,
   checksum mismatches, path inconsistencies, and failed purge locations.
3. Load-test realistic local corpus sizes, backup destinations, and concurrent
   local operations; set published p50/p95 latency, recovery-time, and
   recovery-point objectives.
4. Run load, soak, and chaos/failure-injection tests for interrupted writes,
   queue duplication, index rebuilds, restore, migration rollback, key rotation,
   backup corruption, and provider outages.

**Exit:** documented SLOs are met under load and failure injection; operational
dashboards and runbooks are exercised by people other than the implementer.

### Stage J — evidence of leadership

1. Run a representative pilot with informed users, opt-in data, incident
   review, and correction/deletion feedback loops.
2. Publish a reproducible benchmark and methodology comparing retrieval
   quality, provenance, safety, deletion disposition, and cost against named
   alternatives.
3. Obtain an independent security/privacy assessment and regularly repeat the
   benchmark and disaster-recovery exercises.

**Exit:** Raiker may describe itself as production-proven only after the
published evidence supports that claim. “Best” remains a comparative claim and
must be tied to a disclosed benchmark, population, and date.

## Live-validation runbook and pending external actions

The items below require a real deployment, people, or infrastructure outside
this repository. They are deliberately not marked complete by local tests.
Record the date, operator, environment, inputs, result, and evidence location
for every step before changing the corresponding stage status.

### 1. Release preflight and encrypted-database conversion

1. Start with a disposable copy of a representative workspace and retain an
   encrypted backup plus its checksum before upgrading Raiker.
2. Install locked dependencies with `poetry install`, then verify the runtime
   by opening the store through Raiker and checking `PRAGMA cipher_version`.
   Do not use the standard-library `sqlite3` module to inspect the encrypted
   database.
3. For a legacy database, start Raiker once and verify that the database header
   is not `SQLite format 3`, the expected memory rows remain readable through
   the application, and no `*.plaintext-backup` file remains after a successful
   conversion. Retain the pre-upgrade encrypted backup until acceptance.
4. Roll back only by restoring that retained backup with its matching app key;
   never attempt to decrypt or edit the production file with an unapproved
   tool. Document the restore time and any incompatibilities found.

### 2. Backup, erasure, and recovery drill

1. Use the production backup system to create an encrypted snapshot, register
   its key ID, retention deadline, and storage location in Raiker's backup
   catalog, then perform a restore into an isolated workspace.
2. Compare restored memory counts, content checksums, FTS search results,
   vector mappings, graph edges, and audit records against the source. Record
   RPO/RTO and mark the manifest restore-verified only when this comparison
   passes.
3. Exercise legal hold, archive, forget, and confirmed purge on test data. For
   every purge, show the user the primary-store result and every backup that is
   still pending expiry or erasure; complete and audit the backup-erasure work
   when the backup platform supports it.
4. Perform a migration-rollback and corrupted-backup recovery drill. Escalate
   any inability to restore, erase, or report a pending backup as a release
   blocker.

### 3. Self-hosted multi-user security and recovery review

1. Have an independent reviewer inspect key creation, storage, rotation,
   revocation, recovery, logs, exports, backups, and SQLCipher connection
   initialization. Confirm keys and raw memory never appear in logs or error
   telemetry.
2. Run the same-device multi-user isolation suite. Test that different local
   principals and workspaces cannot read, write, retrieve, project, export,
   back up, or restore each other's data, including confused-deputy attempts.
3. Document device-owner/user recovery, key rotation, local access rules, and
   NAS/mounted-drive/cloud backup setup. The current local app-key derivation
   is not a substitute for documented per-workspace backup-key recovery.

### 4. Retrieval benchmark and pilot

1. Build a consented, de-identified, versioned benchmark that includes normal,
   scoped, sensitive, archived, forgotten, corrected, and temporal facts.
2. Run lexical, vector, graph, and hybrid retrieval independently. Publish
   corpus and backend versions, Precision@k, Recall@k, MRR, nDCG, policy leaks,
   p50/p95 latency, token use, storage/compute cost, and test hardware.
3. Set explicit release budgets from this baseline and make CI reject
   regressions. Do not extrapolate the deterministic local `memory-eval-v1`
   fixture to production quality.
4. Run a small opt-in pilot with clear remember/why/scope/expiry/correction/
   forget controls. Collect support incidents and correction/deletion feedback;
   do not silently promote sensitive, uncertain, or conflicting inferences.

### 5. Operational load and failure testing

1. Define target local corpus sizes, concurrent operations, p50/p95 latency,
   RPO, and RTO. Run load and soak tests at those targets and retain reports.
2. Inject interrupted writes, duplicate jobs, expired leases, index rebuilds,
   provider outages, backup corruption, key rotation, and restore failures.
   Confirm idempotency, rate limits, dead-letter visibility, integrity scans,
   and safe recovery in every case.
3. Have an operator other than the implementer run the dashboard and recovery
   runbooks. Publish open incidents and remediation before claiming
   production-proven reliability.

### Completion evidence checklist

Keep links to the following beside the relevant stage exit criterion: CI run,
dependency/SBOM scan, local security review, encrypted-backup and restore
report, erasure disposition report, workspace-isolation report, benchmark, pilot
report, load/soak/chaos reports, and independent runbook exercise. Until that
evidence exists, Stages F--J remain in progress and Raiker must not be marketed
as the best or as production-proven.
