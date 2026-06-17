# Memory And Context Strategy

Raiker memory is not a free-form note bucket. It is a governed, auditable, scoped system for remembering useful facts, project context, decisions, procedures, episodes, semantic knowledge, graph relationships, and working context.

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
12. poisoning detection and correction.

---

## Memory Types

| Type | Purpose | Phase |
|---|---|---:|
| `working_context` | Current turn/task context bundle | Phase 1 |
| `session_history` | Current session messages/events | Phase 1 |
| `checkpoint_summary` | State summaries for resume/fork | Phase 1 |
| `memory_candidate` | Proposed durable memory | Phase 1 |
| `profile_memory` | Stable user preferences/facts | Phase 2 |
| `project_memory` | Project decisions, architecture, constraints | Phase 2 |
| `episodic_memory` | Timestamped session/task summaries | Phase 2 |
| `procedural_memory` | Reusable workflows/skills | Phase 2 |
| `semantic_memory` | Vector-searchable knowledge | Phase 3 |
| `graph_memory` | Entities, relationships, code maps | Phase 3 |
| `scratchpad_memory` | Temporary agent notes | Phase 1/2 |

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

## Memory Candidate Flow

```text
runtime identifies candidate
  -> memory_candidate_created event
  -> sensitivity classification
  -> dedupe check
  -> contradiction check
  -> user/project policy review
  -> approval or rejection
  -> memory_record_written event
```

Phase 1 creates candidates only. Durable writes are Phase 2.

---

## Retrieval Strategy

Context retrieval must combine:

1. explicit user-provided context;
2. current session summary;
3. active task state;
4. relevant project memory;
5. relevant profile memory;
6. semantic search results;
7. graph/code map results;
8. recent event log entries;
9. checkpoint summary.

Retrieval must rank by:

- user explicitness;
- recency;
- source trust;
- project/session match;
- semantic similarity;
- graph relevance;
- confidence;
- sensitivity policy;
- token budget.

---

## Memory Write Governance

Durable memory write must include:

- source event;
- reason for storing;
- memory type;
- scope;
- sensitivity;
- confidence;
- retention;
- approval state;
- deletion path;
- poisoning risk score.

Automatically storing secrets, credentials, private documents, personal identifiers, or external channel content is forbidden unless explicitly approved and policy permits it.

---

## Memory Correction And Forgetting

Users must be able to:

- inspect memory;
- correct memory;
- lower confidence;
- mark stale;
- delete/forget;
- export memory;
- see provenance;
- see which memories were used in an answer.

Events:

- `memory_record_created`
- `memory_record_updated`
- `memory_record_deleted`
- `memory_record_marked_stale`
- `memory_record_exported`
- `memory_used_in_context`

---

## Procedural Memory And Skills

A repeated workflow may become a skill only when:

- it has been used successfully multiple times;
- steps are stable;
- tools and permissions are known;
- verification criteria are clear;
- user approves skill creation;
- security review passes.

Skill records must include:

- trigger conditions;
- steps;
- tools;
- permissions;
- failure handling;
- tests;
- examples;
- owner.

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
- test prompt-injection memory records.

---

## Context Compaction

When context becomes too large:

```text
PreCompact hook
  -> summarise low-priority context
  -> preserve active instructions and approvals
  -> preserve pending tool/action IDs
  -> preserve task state
  -> PostCompact hook
  -> compacted_context_created event
```

Compaction must not drop:

- active user instruction;
- security policy;
- pending approval;
- task objective;
- current plan;
- changed-file list;
- unresolved errors.

---

## Testing Requirements

Tests must prove:

- memory candidates are created but not written in Phase 1;
- provenance is required;
- sensitivity classification blocks secrets;
- retrieval separates trusted/untrusted context;
- context compaction preserves active task state;
- memory correction/deletion creates audit events;
- poisoned memory cannot override policy.
