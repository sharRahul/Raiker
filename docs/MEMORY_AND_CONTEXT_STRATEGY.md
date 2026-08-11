# Memory And Context Strategy

Raiker memory is not a free-form note bucket. It is a governed, auditable, scoped system for remembering useful facts, project context, decisions, procedures, episodes, semantic knowledge, graph relationships, working context, raw observations, and compressed recall.

Memory is both a feature and an attack surface.

---

## Memory Goals

Raiker memory must support:

1. short-term working context;
2. session history;
3. project decisions;
4. user preferences;
5. episodic summaries;
6. procedural skills;
7. semantic/vector retrieval;
8. graph/entity relationships;
9. provenance and confidence;
10. sensitivity and retention controls;
11. approval and governance;
12. poisoning detection and correction;
13. eidetic-style recall through raw observation snapshots plus compressed gist memory;
14. self-improving skills and memory consolidation after successful tasks.

---

## Memory Types

| Type | Purpose | Build phase | Storage |
|---|---|---:|---|
| `working_context` | Current turn/task context bundle | Phase 1 | runtime object + SQLite pointer |
| `session_history` | Current session messages/events | Phase 1 | JSONL + SQLite event index |
| `checkpoint_summary` | State summaries for resume/fork | Phase 1 | checkpoint manifest + SQLite |
| `memory_candidate` | Proposed durable memory | Phase 1 | SQLite memory_candidates |
| `scratchpad_memory` | Temporary agent notes | Phase 1 | scoped SQLite/JSON artifact |
| `profile_memory` | Stable user preferences/facts | Phase 2 | SQLite memory_records + FTS5 |
| `project_memory` | Project decisions, architecture, constraints | Phase 2 | SQLite memory_records + FTS5 |
| `episodic_memory` | Timestamped session/task summaries | Phase 2 | SQLite memory_records + event links |
| `procedural_memory` | Reusable workflows/skills | Phase 2 | SQLite + skill manifests |
| `eidetic_observation` | Raw, high-fidelity observation snapshot with strict retention | Phase 2 | artifact file + SQLite metadata |
| `gist_memory` | Compressed summary of raw observations/episodes | Phase 2 | SQLite memory_records |
| `semantic_memory` | Vector-searchable knowledge | Phase 3 | embeddings table + vector backend |
| `graph_memory` | Entities, relationships, code maps | Phase 3 | graph_nodes/graph_edges |
| `dialectic_user_model` | User model built from confirmed preferences and corrections | Phase 4 | governed profile memory graph |

---

## Eidetic Memory Model

Raiker does not claim human photographic memory. In Raiker, "eidetic memory" means a governed technical pattern:

```text
raw observation
  -> provenance + sensitivity classification
  -> short-retention eidetic_observation snapshot
  -> gist_memory summary
  -> semantic/graph indexes where permitted
  -> retrieval with source links
  -> decay, correction, deletion, or durable promotion
```

Examples of raw observations:

- exact user instruction for a task;
- selected code/file range;
- tool result artifact;
- channel message with attachment metadata;
- session transcript segment;
- UI state snapshot;
- before/after checkpoint diff.

Rules:

1. Raw eidetic observations are not automatically permanent.
2. Raw observations must have retention and sensitivity labels.
3. Gist memory is preferred for long-term recall.
4. Exact raw replay requires policy and provenance display.
5. Sensitive raw observations may be redacted, skipped, or stored only as references.
6. Users can inspect, correct, export, or delete raw and gist memory.

---

## Context Bundle

A context bundle is what the runtime gives to a model or subagent.

```json
{
  "schema_version": "1.0",
  "context_bundle_id": "ctx_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "sources": [
    {
      "source_id": "src_01H...",
      "source_type": "prompt",
      "trust_level": "user_input",
      "content_ref": "inline",
      "summary": "User asked to add docs.",
      "token_estimate": 12,
      "provenance": {}
    }
  ],
  "redactions": [],
  "risk_notes": [],
  "created_at": "2026-06-17T12:00:00Z"
}
```

---

## Context Source Trust Levels

| Trust level | Meaning |
|---|---|
| `system_policy` | Trusted Raiker policy/system instruction. |
| `user_input` | User-provided prompt. |
| `project_file` | Workspace file; content may contain injection. |
| `memory_record` | Durable memory; may be stale or poisoned. |
| `eidetic_observation` | Raw observation snapshot; high fidelity but not instruction-authoritative. |
| `gist_memory` | Compressed observation or episode. |
| `tool_result` | Tool output; content may be untrusted. |
| `channel_message` | External message; untrusted. |
| `web_content` | Remote content; untrusted. |
| `plugin_content` | Plugin-provided; depends on plugin trust. |
| `subagent_output` | Subagent output; untrusted proposal. |

Model prompts must clearly separate trusted instructions from untrusted content.

---

## Memory Record Schema

```json
{
  "schema_version": "1.0",
  "memory_id": "mem_01H...",
  "memory_type": "project_memory",
  "scope": "project",
  "text": "Raiker uses the tool broker as the only path to tools.",
  "structured": {
    "entity": "tool_broker",
    "relationship": "exclusive_execution_path",
    "object": "tools"
  },
  "provenance": {
    "source_event_id": "evt_01H...",
    "source_file": "docs/ARCHITECTURE.md",
    "created_by": "user_approved"
  },
  "confidence": 0.95,
  "sensitivity": "normal",
  "trust_score": 0.9,
  "retention": "project_lifetime",
  "approval_state": "approved",
  "created_at": "2026-06-17T12:00:00Z",
  "updated_at": null,
  "expires_at": null,
  "tags": ["architecture", "security"]
}
```

---

## Eidetic Observation Schema

```json
{
  "schema_version": "1.0",
  "observation_id": "obs_01H...",
  "source_event_id": "evt_01H...",
  "source_type": "tool_result",
  "artifact_ref": ".raiker/artifacts/task_01H/tool_result_01H.json",
  "summary": "Exact output from graph query used for impact analysis.",
  "sha256": "...",
  "sensitivity": "normal",
  "retention": "short_term_30_days",
  "promotable_to_memory": true,
  "created_at": "2026-06-17T12:00:00Z"
}
```

---

## Memory Candidate Flow

```text
runtime identifies candidate
  -> memory_candidate_created event
  -> sensitivity classification
  -> dedupe check
  -> contradiction check
  -> optional eidetic observation capture
  -> gist summary creation
  -> user/project policy review
  -> approval or rejection
  -> memory_record_written event if approved
```

Phase 1 creates candidates and required tables. Phase 2 enables governed durable writes.

---

## Retrieval Strategy

Context retrieval must combine:

1. explicit user-provided context;
2. current session summary;
3. active task state;
4. relevant project memory;
5. relevant profile memory;
6. gist memory;
7. permitted eidetic observations;
8. semantic search results;
9. graph/code map results;
10. recent event log entries;
11. checkpoint summary.

Retrieval must rank by user explicitness, recency, source trust, project/session match, semantic similarity, graph relevance, confidence, sensitivity policy, and token budget.

---

## Memory Write Governance

Durable memory write must include source event, reason for storing, memory type, scope, sensitivity, confidence, retention, approval state, deletion path, and poisoning risk score.

Automatically storing secrets, private documents, personal identifiers, or external channel content is forbidden unless explicitly approved and policy permits it.

---

## Memory Correction And Forgetting

Users must be able to inspect memory, correct memory, lower confidence, mark stale, delete/forget, export memory, see provenance, see which memories were used in an answer, and see which raw observation or gist memory produced a recalled fact.

Events:

- `memory_record_created`
- `memory_record_updated`
- `memory_record_deleted`
- `memory_record_marked_stale`
- `memory_record_exported`
- `memory_used_in_context`
- `eidetic_observation_created`
- `eidetic_observation_expired`
- `gist_memory_created`

---

## Procedural Memory And Skills

A repeated workflow may become a skill only when it has been used successfully multiple times, steps are stable, tools and permissions are known, verification criteria are clear, user approves skill creation, and security review passes.

Skill records must include trigger conditions, steps, tools, permissions, failure handling, tests, examples, owner, source episodes, and improvement history.

---

## Self-Improving Skill Loop

Raiker must support a Hermes-style closed learning loop:

```text
complex task completed
  -> verification passed
  -> runtime proposes skill candidate
  -> user/project policy review
  -> skill manifest created or updated
  -> skill tested against example task
  -> skill_refined event emitted
```

A skill may self-improve during use only through explicit update proposals, tests, and approval. It cannot silently rewrite itself.

---

## Memory Poisoning Controls

Controls required:

- treat all retrieved memory as contextual, not authoritative;
- store provenance;
- store confidence;
- detect contradictions;
- require approval for high-impact memories;
- isolate external-channel memories;
- do not let memory override policy/system instructions;
- provide memory inspection and deletion;
- test prompt-injection memory records;
- use raw eidetic observations only with provenance and retention controls.

---

## Context Compaction

When the complete next request reaches 90% of a known model capacity:

```text
PreCompact hook
  -> select older completed exchanges, retaining the newest two verbatim
  -> run a separate model request with tools and reasoning disabled
  -> preserve the active plan and approval/checkpoint/source IDs
  -> store the summary with an exact through-turn boundary
  -> PostCompact hook
  -> compacted_context_created event
```

This is runtime context management, not durable memory creation. It never edits
or deletes the transcript and it does not create a memory record. Completed
summaries are encrypted, owner/session scoped, and excluded from event payloads.
The usage ledger records the summary request as `request_kind=compaction`.

When capacity is unknown, the 90% boundary cannot be measured and compaction is
not claimed. When the provider, storage, or a `PreCompact` hook makes the summary
unavailable, Raiker records `compacted_context_failed` and continues with bounded
recent completed history. Failed, running, and approval-waiting turns are never
eligible input.

Compaction must not drop active user instruction, security policy, pending
approval, task objective, current plan, changed-file list, unresolved errors, or
required provenance links.

---

## Testing Requirements

Tests must prove:

- memory candidates are created but not written without governance;
- provenance is required;
- sensitivity classification blocks restricted content;
- retrieval separates trusted/untrusted context;
- context compaction preserves active task state;
- memory correction/deletion creates audit events;
- poisoned memory cannot override policy;
- eidetic observations expire according to retention;
- gist memory links back to raw observation provenance;
- skill self-improvement requires verification and approval.

## Phase 3 Slice C/D governance update (local validation required)

Current runtime posture update: graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding now have real governed executors; broader graph query/planning automation, learned semantics, external sync, and no-executor extensions remain deferred/fail-closed.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution slices are integrated governed executors; broader plugin extensions remain deferred/fail-closed.
- Graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding are integrated governed executors; broader graph/memory extensions remain deferred/fail-closed.
- The reference external channel runtime, subagent/team executors, and local container executor are integrated and governed.
- Remote/cloud command execution remains no-executor/fail-closed.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.
