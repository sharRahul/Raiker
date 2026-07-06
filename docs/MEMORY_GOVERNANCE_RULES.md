# Memory Governance Rules

This document defines Raiker's memory write, update, use, correction, and forgetting rules. It complements `docs/MEMORY_AND_CONTEXT_STRATEGY.md` by making governance decisions implementable and testable.

Phase 1 may create memory candidates. It must not write durable long-term memory automatically.

Current backend truth (2026-06-21):

- `/memory-store` and `/memory-forget` are brokered approval-required requests by default.
- Approval resolution is metadata-only.
- `/approve` and `/deny` are metadata-only and do not execute pending memory mutations.
- Secret/credential-like durable memory content is denied before approval creation.
- The governed durable-memory write contract exists for broker/policy-gated execution paths and tests; it is not a broad user-enabled runtime write path.
- Semantic/vector runtimes are integrated real executors and governed per action; no-executor deferred capabilities remain disabled/fail-closed.

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
  "sensitivity": "project",
  "confidence": 0.9,
  "decision": "needs_user_review",
  "created_at": "2026-06-17T12:00:00Z",
  "resolved_at": null
}
```

Allowed candidate decisions in the current backend: `needs_user_review`, `approved_for_later`, `denied`.

---

## Durable Memory Record Schema

```json
{
  "schema_version": "1.0",
  "memory_id": "mem_01H...",
  "memory_type": "project",
  "scope": "project",
  "text": "All Raiker clients must enter through the Agent Gateway.",
  "provenance": {
    "source_event_id": "evt_01H...",
    "source_session_id": "sess_01H...",
    "source_turn_id": "turn_01H...",
    "source_type": "local_user"
  },
  "confidence": 0.95,
  "sensitivity": "project",
  "trust_score": 0.9,
  "retention": "until_project_forget",
  "approval_state": "approved_after_governed_path",
  "created_by": "local_terminal_command",
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
| `project` | Project-local durable memory | Use with provenance and scope. |
| `personal` | User-personal content | Use only when task-relevant; no hosted egress without policy. |
| `secret_like` | Secret-like opaque value | Deny durable storage. |
| `credential_like` | Credential/token/private-key-like material | Deny durable storage. |
| `unknown` | Unclassified content | Review before broad use. |

---

## Write Rules

1. Phase 1 may create candidates only.
2. Governed durable writes require memory type, scope, sensitivity, confidence, provenance, retention, approval state, and created_by metadata.
3. Model output alone is never sufficient provenance for durable memory.
4. Untrusted file/channel/tool output must not become durable memory without trust labels and review.
5. Sensitive memory must not be sent to hosted providers unless egress policy explicitly allows it.
6. Governed durable writes emit `memory_record_created`; governed forgetting emits `memory_record_forgotten`.
7. Forgetting creates a tombstone-style deleted record locally and removes the entry from normal reads/lists/search.

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
- `memory_record_forgotten`

---

## Acceptance Tests

Tests must prove:

1. Phase 1 does not write durable memory automatically;
2. memory candidates include provenance and sensitivity;
3. governed durable memory record rejects missing provenance/governance metadata;
4. secret-like values are not stored raw;
5. memory retrieval records usage attribution;
6. deleted/forgotten memory is not returned;
7. hosted egress rejects confidential/restricted memory unless policy allows;
8. poisoned/untrusted source defaults to candidate or rejected state;
9. memory correction creates an audit event.

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
- Legacy preview surfaces do not execute graph writes; the current graph indexing runtime is a separate governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic memory and vector embedding/search runtimes are separate governed real executors.
- Plugin slices, the reference external channel, subagent/team executors, and local container runtime are governed real executors; remote/cloud command execution remains no-executor/fail-closed.
- GitHub Actions remain paused due quota exhaustion; local/cloud validation evidence is mandatory.
- CI must be re-enabled later when quota is available and must not be claimed as passed while Actions are paused.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

## Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Legacy lifecycle/preview surfaces do not write graph data directly; current graph indexing is a governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic/vector runtimes are governed real executors.
- Rollback execution remains disabled.
- Plugin slices, the reference external channel, subagent/team executors, and local container runtime are governed real executors; remote/cloud command execution remains no-executor/fail-closed.
- GitHub Actions remain paused due quota/run-limit exhaustion; local/cloud validation evidence is mandatory and GitHub CI must be re-enabled later when quota is available.
