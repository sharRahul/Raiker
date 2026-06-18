# Storage, Database, And Search Specification

Raiker must have a concrete storage design. This document defines what is stored, where it is stored, how SQLite is used, how graph relationships are queried, how semantic search is implemented, and how event logs/checkpoints/artifacts relate to the database.

---

## Storage Goals

Raiker storage must support:

1. append-only audit/event logs;
2. session and task state;
3. checkpoints and file snapshots;
4. governed memory;
5. semantic/vector search;
6. graph/codemap relationships;
7. plugin/channel/model/tool configuration;
8. approval history;
9. search and inspection from TUI/Web/Desktop;
10. export, backup, cleanup, and migration.

---

## Storage Architecture

Raiker uses a hybrid local storage model:

```text
.raiker/
  raiker.db                    # SQLite primary state database
  events/
    sess_<id>.jsonl             # append-only session event logs
  checkpoints/
    sess_<id>/
      ckpt_<id>.json             # checkpoint manifests
      snapshots/                 # file snapshots
  artifacts/
    task_<id>/                   # large tool outputs, reports, exports
  indexes/
    vector/                      # optional vector index files if not SQLite-native
    graph/                       # optional graph export/cache files
  config/
    policy.json
    models.json
    plugins.json
```

SQLite is the default local database because it is portable, inspectable, local-first, embeddable, and suitable for personal workstation/home-lab usage.

---

## What SQLite Stores

SQLite stores:

- sessions;
- turns;
- tasks;
- event metadata/index pointers;
- approvals;
- tools/actions/results metadata;
- checkpoints metadata;
- memory records;
- memory candidates;
- embeddings metadata;
- graph nodes;
- graph edges;
- graph snapshots;
- plugin registry;
- hook registry;
- channel registry;
- model profiles;
- execution profiles;
- UI dashboard state;
- migrations.

Large raw payloads remain in JSONL/artifact files when appropriate, with SQLite storing pointers, checksums, metadata, and searchable indexes.

---

## Why Not A Separate Graph Database By Default

Raiker should not require Neo4j or another external graph database for local-first operation.

Default graph storage uses SQLite tables plus recursive CTEs for relationship traversal. This gives local-first graph capability without running a separate service.

A future external graph adapter may be added, but the SQLite graph model is mandatory and must remain supported.

---

## SQLite Pragmas

Recommended defaults:

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA busy_timeout = 5000;
```

WAL mode allows the TUI/dashboard to read while background tasks write.

---

## Core Tables

### sessions

```sql
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  project_root TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  parent_session_id TEXT,
  forked_from_checkpoint_id TEXT,
  title TEXT,
  summary TEXT
);
```

### turns

```sql
CREATE TABLE turns (
  turn_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  parent_turn_id TEXT,
  turn_type TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt_text TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  summary TEXT
);
```

### tasks

```sql
CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  parent_turn_id TEXT REFERENCES turns(turn_id),
  parent_task_id TEXT,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  current_step TEXT,
  progress_percent INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
```

### events_index

The full event record is append-only JSONL. SQLite indexes event metadata.

```sql
CREATE TABLE events_index (
  event_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  jsonl_path TEXT NOT NULL,
  jsonl_offset INTEGER,
  payload_sha256 TEXT,
  risk_level TEXT,
  summary TEXT
);

CREATE INDEX idx_events_session_time ON events_index(session_id, timestamp);
CREATE INDEX idx_events_type_time ON events_index(event_type, timestamp);
CREATE INDEX idx_events_task_time ON events_index(task_id, timestamp);
```

---

## Approvals And Tool Actions

```sql
CREATE TABLE tool_actions (
  action_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  tool_name TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  status TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE policy_decisions (
  decision_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL REFERENCES tool_actions(action_id),
  decision TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE approvals (
  approval_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL REFERENCES tool_actions(action_id),
  status TEXT NOT NULL,
  approval_scope TEXT,
  approved_by TEXT,
  channel_message_id TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  expires_at TEXT
);
```

---

## Memory Tables

```sql
CREATE TABLE memory_records (
  memory_id TEXT PRIMARY KEY,
  memory_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  text TEXT NOT NULL,
  structured_json TEXT,
  provenance_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  sensitivity TEXT NOT NULL,
  trust_score REAL NOT NULL,
  retention TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  expires_at TEXT,
  deleted_at TEXT
);

CREATE TABLE memory_candidates (
  candidate_id TEXT PRIMARY KEY,
  source_event_id TEXT NOT NULL,
  memory_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  text TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  confidence REAL NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE memory_usage (
  usage_id TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL REFERENCES memory_records(memory_id),
  context_bundle_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  relevance_score REAL,
  used_at TEXT NOT NULL
);
```

---

## Semantic Search Storage

Raiker should support two default local semantic-search modes:

1. SQLite-native vector extension when available, such as `sqlite-vec` or equivalent.
2. External local vector index under `.raiker/indexes/vector/` with SQLite metadata pointers.

Embedding metadata table:

```sql
CREATE TABLE embeddings (
  embedding_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  model_profile_id TEXT NOT NULL,
  vector_backend TEXT NOT NULL,
  vector_ref TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  created_at TEXT NOT NULL,
  stale_at TEXT
);

CREATE INDEX idx_embeddings_source ON embeddings(source_type, source_id);
```

Semantic search must never return memory/file chunks without provenance, sensitivity, and trust metadata.

---

## Graph Tables

### graph_nodes

```sql
CREATE TABLE graph_nodes (
  node_id TEXT PRIMARY KEY,
  graph_snapshot_id TEXT NOT NULL,
  node_type TEXT NOT NULL,
  name TEXT NOT NULL,
  qualified_name TEXT,
  source_path TEXT,
  line_start INTEGER,
  line_end INTEGER,
  source_sha256 TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  stale_at TEXT
);

CREATE INDEX idx_graph_nodes_type_name ON graph_nodes(node_type, name);
CREATE INDEX idx_graph_nodes_qname ON graph_nodes(qualified_name);
CREATE INDEX idx_graph_nodes_source ON graph_nodes(source_path);
```

### graph_edges

```sql
CREATE TABLE graph_edges (
  edge_id TEXT PRIMARY KEY,
  graph_snapshot_id TEXT NOT NULL,
  from_node_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
  to_node_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
  relationship TEXT NOT NULL,
  confidence REAL NOT NULL,
  provenance_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  stale_at TEXT
);

CREATE INDEX idx_graph_edges_from ON graph_edges(from_node_id, relationship);
CREATE INDEX idx_graph_edges_to ON graph_edges(to_node_id, relationship);
CREATE INDEX idx_graph_edges_rel ON graph_edges(relationship);
```

---

## Recursive CTE Graph Queries

### Dependency traversal

```sql
WITH RECURSIVE dependency_tree(node_id, depth, path) AS (
  SELECT :start_node_id, 0, :start_node_id
  UNION ALL
  SELECT e.to_node_id, dependency_tree.depth + 1, path || '>' || e.to_node_id
  FROM graph_edges e
  JOIN dependency_tree ON e.from_node_id = dependency_tree.node_id
  WHERE e.relationship IN ('depends_on', 'imports', 'calls')
    AND dependency_tree.depth < :max_depth
    AND instr(path, e.to_node_id) = 0
)
SELECT * FROM dependency_tree;
```

### Impact analysis

```sql
WITH RECURSIVE impacted(node_id, depth) AS (
  SELECT :changed_node_id, 0
  UNION ALL
  SELECT e.from_node_id, impacted.depth + 1
  FROM graph_edges e
  JOIN impacted ON e.to_node_id = impacted.node_id
  WHERE e.relationship IN ('depends_on', 'imports', 'calls', 'tests')
    AND impacted.depth < :max_depth
)
SELECT n.* FROM impacted i JOIN graph_nodes n ON n.node_id = i.node_id;
```

### Test coverage lookup

```sql
SELECT test_node.*
FROM graph_edges e
JOIN graph_nodes test_node ON test_node.node_id = e.from_node_id
WHERE e.relationship = 'tests'
  AND e.to_node_id = :target_node_id;
```

---

## Search Strategy

Raiker search combines:

| Search type | Backend |
|---|---|
| file name | SQLite metadata + filesystem glob |
| text grep | brokered grep tool + optional FTS5 index |
| event search | SQLite events_index |
| memory keyword search | SQLite FTS5 over memory_records |
| semantic search | vector backend + metadata filters |
| graph search | SQLite graph tables + recursive CTEs |
| code symbols | LSP/symbol extraction + graph_nodes |

---

## FTS5 Tables

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
  memory_id UNINDEXED,
  text,
  tags,
  content='memory_records',
  content_rowid='rowid'
);

CREATE VIRTUAL TABLE event_fts USING fts5(
  event_id UNINDEXED,
  summary,
  event_type,
  content='events_index',
  content_rowid='rowid'
);
```

---

## Checkpoint Tables

```sql
CREATE TABLE checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  checkpoint_type TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  summary TEXT,
  last_event_id TEXT,
  can_restore_state INTEGER NOT NULL,
  can_restore_files INTEGER NOT NULL
);

CREATE TABLE file_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  checkpoint_id TEXT NOT NULL REFERENCES checkpoints(checkpoint_id),
  path TEXT NOT NULL,
  snapshot_path TEXT NOT NULL,
  sha256_before TEXT NOT NULL,
  sha256_after TEXT,
  change_type TEXT NOT NULL,
  size_bytes INTEGER,
  sensitivity TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

---

## Migrations

SQLite migrations must be explicit:

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  checksum TEXT NOT NULL
);
```

Rules:

- no destructive migration without backup;
- migration checksum recorded;
- rollback strategy documented;
- migration events emitted;
- tests run against fresh and migrated databases.

---

## Backup And Export

Backup must include:

- `raiker.db`;
- event JSONL files;
- checkpoint manifests;
- snapshots;
- artifacts;
- vector index files;
- graph caches;
- config.

Export must support:

- session export;
- task export;
- memory export;
- event audit export;
- graph export;
- plugin registry export.

Sensitive exports require approval.

---

## Dashboard Storage Metrics

Dashboard storage widget must show:

- database file size;
- event log size;
- checkpoints size;
- artifacts size;
- vector index size;
- graph node/edge counts;
- stale graph entries;
- memory record count;
- pending memory candidates;
- last migration version;
- last backup time.

---

## Testing Requirements

Tests must prove:

- SQLite schema creates successfully;
- WAL mode enabled;
- events are indexed after JSONL write;
- memory FTS search works;
- recursive CTE finds dependency paths;
- impact analysis returns reverse dependencies;
- vector metadata enforces provenance;
- checkpoint metadata links to snapshots;
- migrations are idempotent;
- dashboard metrics read from database;
- backup includes all required storage components.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Graph indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- Rollback execution remains disabled.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.

## Phase 3 Slice H Lifecycle Retention Metadata Tables

Slice H may create only these metadata tables: `phase3_storage_lifecycle_retention`, `phase3_storage_lifecycle_cleanup_previews`, `phase3_storage_lifecycle_approval_handoffs`, and `phase3_storage_lifecycle_retention_events`. Migrations are idempotent. Slice H must not create graph node/edge tables, vector tables, embedding tables, semantic-memory durable-write tables, rollback execution tables, plugin execution tables, external-channel runtime tables, or remote/container/cloud execution tables.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.
