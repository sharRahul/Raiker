# Memory Governance Rules

This document defines Raiker's memory write, update, use, correction, and forgetting rules. It complements `docs/MEMORY_AND_CONTEXT_STRATEGY.md` by making governance decisions implementable and testable.

Phase 1 may create memory candidates. It must not write durable long-term memory automatically.

---

## Memory Types

| Type | Purpose | First active phase | Default write policy |
|---|---|---:|---|
| `scratchpad` | Current turn/task working notes | Phase 1 | Runtime-local; not durable memory. |
| `memory_candidate` | Proposed durable memory pending governance | Phase 1 | Allowed to create, not auto-persist. |
| `profile` | User preferences and stable user-provided facts | Phase 2 | Requires approval/governance. |
| `project` | Project-specific conventions and decisions | Phase 2 | Requires project scope and provenance. |
| `episodic` | Task/session summaries | Phase 2 | Requires event provenance and retention. |
| `procedural` | Reusable workflows/skills | Phase 2-3 | Requires verification and approval. |
| `semantic` | Embedding-backed memory chunks | Phase 3 | Requires sensitivity and provenance filters. |
| `graph` | Entity/relationship memory | Phase 3 | Requires source and staleness rules. |
| `eidetic_observation` | Raw observation metadata/artifact | Phase 2 | Retention-controlled. |
| `gist` | Compressed summary of raw observation | Phase 2 | Derived from governed observation. |

---

## Memory Candidate Schema

```json
{
  "schema_version": "1.0",
  "candidate_id": "memcand_01H...",
  "source_event_id": "evt_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "memory_type": "project",
  "scope": "project",
  "text": "Raiker Phase 1 must keep terminal/TUI as the first client only, not the privileged interface.",
  "sensitivity": "normal",
  "confidence": 0.9,
  "decision": "deferred",
  "reason": "Requires governance before durable write.",
  "created_at": "2026-06-17T12:00:00Z",
  "resolved_at": null
}
```

Allowed candidate decisions: `deferred`, `approved`, `rejected`, `needs_user_review`, `expired`.

---

## Durable Memory Record Schema

```json
{
  "schema_version": "1.0",
  "memory_id": "mem_01H...",
  "memory_type": "project",
  "scope": "project",
  "text": "All Raiker clients must enter through the Agent Gateway.",
  "structured": {},
  "provenance": {
    "source_event_id": "evt_01H...",
    "source_session_id": "sess_01H...",
    "source_type": "user_confirmed"
  },
  "confidence": 0.95,
  "sensitivity": "normal",
  "trust_score": 0.9,
  "retention": "until_project_forget",
  "approval_state": "approved",
  "created_at": "2026-06-17T12:00:00Z",
  "updated_at": null,
  "expires_at": null,
  "deleted_at": null
}
```

---

## Sensitivity Levels

| Level | Meaning | Default behaviour |
|---|---|---|
| `public` | Safe project/public info | May be used in context if relevant. |
| `normal` | Non-sensitive user/project memory | Use with provenance. |
| `confidential` | Private data, business context, internal details | Use only when task-relevant; no hosted egress without policy. |
| `secret` | Credentials/tokens/private keys or equivalent | Do not store raw values; references only. |
| `restricted` | Regulated or highly sensitive info | Requires explicit policy and audit. |

---

## Write Rules

1. Phase 1 may create candidates only.
2. Durable writes require memory type, scope, sensitivity, confidence, provenance, retention, and approval state.
3. Model output alone is never sufficient provenance for durable memory.
4. Untrusted file/channel/tool output must not become durable memory without trust labels and review.
5. Sensitive memory must not be sent to hosted providers unless egress policy explicitly allows it.
6. Memory writes must emit events and be queryable from SQLite.
7. Memory correction and forgetting must be supported before memory is presented as durable user/profile memory.

---

## Use Rules

Memory retrieval into context must record:

- memory ID;
- context bundle ID;
- session ID;
- turn ID;
- relevance score;
- sensitivity;
- reason used;
- whether hosted egress is allowed.

The runtime must prefer recent, high-trust, scope-matching memory and must avoid using stale or deleted memory.

---

## Poisoning Controls

Raiker must defend against poisoned memory by requiring:

- provenance;
- source trust label;
- confidence score;
- sensitivity label;
- correction path;
- deletion/forgetting path;
- stale detection;
- event-linked audit trail.

A memory extracted from a prompt-injected document, unpaired channel, or untrusted tool output should default to candidate state or rejection.

---

## Required Events

- `memory_candidate_created`
- `memory_candidate_reviewed`
- `memory_record_created`
- `memory_record_updated`
- `memory_record_forgotten`
- `memory_record_expired`
- `memory_used_in_context`
- `memory_export_requested`
- `memory_export_completed`
- `memory_export_denied`

---

## Acceptance Tests

Tests must prove:

1. Phase 1 does not write durable memory automatically;
2. memory candidates include provenance and sensitivity;
3. durable memory record rejects missing provenance;
4. secret-like values are not stored raw;
5. memory retrieval records usage attribution;
6. deleted/forgotten memory is not returned;
7. hosted egress rejects confidential/restricted memory unless policy allows;
8. poisoned/untrusted source defaults to candidate or rejected state;
9. memory correction creates an audit event.

## Phase 3 Slice C/D governance update (local validation required)

Full Phase 3 is not complete. Slice C adds graph/codemap governance and dry-run planning only: graph/codemap runtime indexing remains disabled, no background indexer is started, and no durable graph nodes or edges are written. Slice D adds semantic memory governance and a review queue only: semantic/vector memory writes remain disabled, no embeddings are created, and no vector records are written.

Safety status for this slice:

- GitHub Actions remain paused due quota exhaustion; do not claim GitHub CI passed while paused.
- Local validation evidence remains mandatory under `docs/LOCAL_VALIDATION_GATE.md`.
- Plugin execution remains disabled.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- External channels remain disabled.
- Subagents and multi-agent teams remain disabled.
- Remote/container execution remains disabled.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.

## Phase 3 Slice E Semantic Memory Approval Preview

Semantic memory approval previews wrap `MemoryReviewItem` values to show what a future governed semantic-memory write would require. They are not approvals to execute, and approving a candidate for later does not write memory or run indexing.

Rules:

- `target_capability` is `semantic_memory_writes`.
- `can_execute_now` is `false`.
- `execution_enabled` is `false`.
- `policy_decision` is `denied_or_preview_only`.
- `semantic_vector_writes_disabled` is included in reasons.
- Secret-like or credential-like candidates produce denied high-risk previews with redacted output.
- Preview creation does not write durable semantic memory, create embeddings, or create vectors.

Semantic/vector writes remain disabled and full Phase 3 is not complete.

## Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled; no embeddings or vectors are created.
- Plugin execution, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

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
