# Eidetic Memory And Learning Specification

Raiker uses "eidetic memory" as a technical design pattern, not a claim of human photographic memory.

In Raiker, eidetic memory means governed high-fidelity recall: raw observations are captured with provenance, sensitivity, retention, checksum, and storage references; then compressed into gist memory and optionally indexed semantically or linked into graph memory.

---

## Goals

Raiker must support:

1. raw observation capture;
2. short-retention high-fidelity recall;
3. compressed gist memory;
4. episodic timeline reconstruction;
5. skill learning from successful task trajectories;
6. user/profile modelling only from confirmed facts;
7. memory correction and forgetting;
8. semantic, keyword, and graph retrieval;
9. poisoning detection;
10. dashboard visibility into memory health.

---

## Memory Flow

```text
agent event or tool result
  -> classify sensitivity
  -> decide whether raw observation is allowed
  -> write artifact if raw capture is allowed
  -> write eidetic_observations row
  -> create gist_memory candidate
  -> dedupe and contradiction check
  -> user/project/managed policy review
  -> write memory record if approved
  -> optionally create embedding
  -> optionally link graph nodes/edges
  -> expose usage in context bundle
```

---

## SQLite Tables

### eidetic_observations

```sql
CREATE TABLE eidetic_observations (
  observation_id TEXT PRIMARY KEY,
  source_event_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  source_type TEXT NOT NULL,
  artifact_ref TEXT,
  content_sha256 TEXT NOT NULL,
  summary TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  retention TEXT NOT NULL,
  promotable_to_memory INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  deleted_at TEXT
);

CREATE INDEX idx_eidetic_session_time ON eidetic_observations(session_id, created_at);
CREATE INDEX idx_eidetic_source_event ON eidetic_observations(source_event_id);
CREATE INDEX idx_eidetic_retention ON eidetic_observations(retention, expires_at);
```

### gist_memories

```sql
CREATE TABLE gist_memories (
  gist_id TEXT PRIMARY KEY,
  source_observation_id TEXT REFERENCES eidetic_observations(observation_id),
  source_event_id TEXT NOT NULL,
  memory_record_id TEXT,
  summary TEXT NOT NULL,
  compression_method TEXT NOT NULL,
  confidence REAL NOT NULL,
  sensitivity TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_gist_source_observation ON gist_memories(source_observation_id);
```

### skill_learning_events

```sql
CREATE TABLE skill_learning_events (
  learning_event_id TEXT PRIMARY KEY,
  source_task_id TEXT NOT NULL,
  skill_id TEXT,
  proposal_status TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  improvement_summary TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
```

---

## Retention Classes

| Retention | Meaning |
|---|---|
| `turn_only` | Delete after turn closes unless checkpoint needs it. |
| `short_term_7_days` | Keep for short debugging/replay. |
| `short_term_30_days` | Keep for task/project continuity. |
| `project_lifetime` | Keep while project memory exists. |
| `manual_keep` | User explicitly preserved it. |
| `legal_hold` | Managed retention; cannot be auto-deleted. |

---

## Retrieval Modes

| Mode | Purpose |
|---|---|
| `gist_first` | Retrieve compressed memories before raw observations. |
| `exact_replay` | Retrieve raw observation only after policy allows it. |
| `episode_walk` | Reconstruct task/session timeline from events and observations. |
| `skill_trace` | Retrieve successful task trajectories used to create a skill. |
| `contradiction_check` | Compare candidate memory with existing records. |
| `user_model_check` | Retrieve confirmed user facts/preferences only. |

---

## Self-Improving Skill Loop

Raiker must support a closed learning loop similar to self-improving agent systems:

```text
complex task completed
  -> verification passed
  -> trajectory summarised
  -> skill_candidate_created event
  -> user/project policy review
  -> skill manifest proposed
  -> tests/examples generated
  -> approval required
  -> skill installed or updated
  -> skill_learning_event recorded
```

The agent must not silently rewrite or create skills. A skill improvement is a proposal until approved and tested.

---

## Dashboard Requirements

Memory dashboard must show:

- memory records by type;
- pending candidates;
- eidetic observations by retention class;
- observations expiring soon;
- gist memories created;
- skill learning proposals;
- stale memories;
- contradiction warnings;
- poisoned memory warnings;
- deletion/export actions.

---

## Events

Required events:

- `eidetic_observation_created`
- `eidetic_observation_skipped`
- `eidetic_observation_expired`
- `eidetic_observation_deleted`
- `gist_memory_created`
- `gist_memory_used_in_context`
- `skill_candidate_created`
- `skill_learning_event_created`
- `skill_update_proposed`
- `skill_update_approved`
- `skill_update_rejected`

---

## Security Rules

1. Raw observations are not trusted instructions.
2. Raw observations must have provenance and retention.
3. Sensitive raw observations require redaction or skip policy.
4. Exact replay requires provenance display.
5. Memory cannot override policy or system instructions.
6. Skills cannot self-install without approval.
7. External-channel observations are isolated by channel trust.
8. Deletion must remove or tombstone raw observation metadata and artifacts according to policy.

---

## Tests

Tests must prove:

- raw observation metadata is written with checksum;
- sensitive observation can be skipped;
- gist memory links to source observation;
- expired observations are cleaned up;
- exact replay requires policy;
- skill candidate requires verified task;
- skill update cannot install without approval;
- poisoned memory cannot override policy.
