# Hybrid Memory Implementation Plan

## Status

This is the implementation contract for Raiker's archive-first, high-fidelity
memory system. It is intentionally incremental: existing governed memory,
SQLite event storage, project context, and capability gates remain the source
of truth until each phase below is implemented and verified.

The completed foundation is limited to safe project-tree correction:

- self-inclusive materialized project paths (`/root/child/`);
- transactional subtree move/archive updates;
- tri-state inherited project-memory mode (`inherit`, `enabled`, `disabled`).

No raw-observation worker, automatic durable-memory promotion, graph write, or
unattended cleanup is enabled by this plan.

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

- Migrate legacy paths to self-inclusive paths and validate parent/path parity.
- Add tri-state memory inheritance with backward-compatible Boolean input.
- Add archive/restore visibility and test sibling/subtree isolation.
- Acceptance: moves, archives, and deletes never affect siblings; nearest
  active explicit context setting is deterministic.

### Phase B — durable-memory lifecycle normalization

- Consolidate approved-memory metadata into SQLite as the retrieval authority;
  Markdown remains a human-readable export/cache, not a competing store.
- Add archive/restore and tombstone lifecycle fields and audit events.
- Add a human-only purge-preview endpoint listing dependent projections.
- Acceptance: archive and forget are reversible/tombstoned as specified;
  no agent-triggered hard delete path exists.

### Phase C — eidetic observations and gists

- Persist raw observation metadata with immutable artifact refs, checksum,
  provenance, sensitivity, and retention class.
- Create reviewable gist candidates; only governed approval promotes a gist to
  durable memory.
- Add expiry preview and an owner-approved cleanup executor.
- Acceptance: sensitive raw content is redacted/skipped; raw expiry never
  silently deletes a promoted durable memory.

### Phase D — retrieval indexes and graph projection

- Add SQLite FTS synchronization for active durable-memory records.
- Add vector and graph projections behind existing capability gates.
- Record projection source/version so archive, forget, correction, and purge
  fan out reliably.
- Acceptance: lexical, vector, and graph retrieval return only active,
  authorized source records and disclose provenance.

### Phase E — purge, backup disposition, and operations

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
