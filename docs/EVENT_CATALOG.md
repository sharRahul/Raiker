# Event Catalog

This document is the canonical event-name and event-payload catalog for Raiker. `docs/CONTRACTS.md` defines the event envelope. This file defines the event taxonomy, required event order, payload expectations, actors, and storage/indexing requirements.

Every meaningful runtime action must be represented as an append-only event. No interface, model, plugin, hook, channel, subagent, or execution adapter may create a hidden action path that is not reflected in events.

---

## Event Envelope

All events use this envelope:

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01H...",
  "timestamp": "2026-06-17T12:00:00Z",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "task_id": null,
  "event_type": "prompt_received",
  "actor": "agent_gateway",
  "payload": {},
  "parent_event_id": null
}
```

Required rules:

1. `event_id` is globally unique and starts with `evt_`.
2. `timestamp` is UTC ISO 8601.
3. Events are written once and never mutated.
4. JSONL stores the complete event.
5. SQLite `events_index` stores metadata, path, offset, checksum, summary, actor, and risk metadata.
6. Event payloads must not contain unredacted secrets.
7. Originating interface/client metadata must be preserved when relevant.

---

## Phase 1 Event Order: Simple Chat

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_skipped
response_created
checkpoint_created
turn_closed
```

The simple-chat sequence must not include tool or policy events unless the runtime proposes a tool action.

---

## Phase 1 Event Order: Filesystem Query

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_skipped or plan_created
action_proposed
action_validated
policy_decision
tool_started
tool_completed or tool_failed
verification_completed
response_created
checkpoint_created
turn_closed
```

A denied filesystem query must include `policy_decision` and must not include `tool_started`.

---

## Phase 1 Event Order: Local Action Proposal

```text
prompt_received
prompt_normalised
intent_classified
risk_classified
context_gathered
plan_created
action_proposed
action_validated
policy_decision
approval_requested
response_created
turn_closed
```

Phase 1 local actions must pause at approval. The sequence must not include `tool_started` unless explicit approval exists and the task scope includes executing that action.

---

## Phase 1 Canonical Events

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `global_command_invoked` | `terminal_launcher` | `argv`, `cwd`, `client_type` | Emitted when `raiker` is invoked. |
| `terminal_client_started` | `terminal_client` | `renderer`, `version`, `client_type` | Used for plain or Rich terminal shell. |
| `tui_started` | `tui_client` | `renderer`, `client_type` | Optional if Rich/Textual TUI is active. |
| `tui_prompt_submitted` | `tui_client` | `request_id`, `session_id`, `turn_id` | Client-side prompt submission before gateway. |
| `ui_action_submitted` | `client` | `action_type`, `client` | Interface-neutral action such as `/models`. |
| `prompt_received` | `agent_gateway` | `request_id`, `client` | First gateway event for user prompt. |
| `prompt_normalised` | `agent_gateway` | `request_id`, `normalisation_status` | Prompt converted to canonical envelope. |
| `intent_classified` | `runtime` | `intent`, `confidence`, `requires_tools` | Must match allowed intent enum. |
| `risk_classified` | `runtime` | `risk_level`, `reasons`, `requires_approval` | Must match risk enum. |
| `context_gathered` | `context_gatherer` | `sources`, `context_bundle_id` | Sources include provenance and sensitivity. |
| `plan_created` | `planner` | `plan_id`, `steps`, `requires_approval` | Required for risky/multi-step/code-changing tasks. |
| `plan_skipped` | `planner` | `reason` | Required when no plan is created. |
| `action_proposed` | `runtime` or `model_router` | `action_id`, `tool_name`, `arguments_summary` | Model output is still untrusted. |
| `action_validated` | `tool_broker` | `action_id`, `validation_status` | Argument/schema validation before policy. |
| `policy_decision` | `policy_engine` | `decision_id`, `action_id`, `decision`, `reasons` | Required before any tool starts. |
| `approval_requested` | `tool_broker` | `approval_id`, `action_id`, `risk_level`, `choices` | Bound to exact `action_id`. |
| `approval_received` | `approval_service` | `approval_id`, `action_id`, `approved_by` | Must include client/channel provenance. |
| `approval_denied` | `approval_service` | `approval_id`, `action_id`, `denied_by` | Denied action must not execute. |
| `tool_started` | `tool_broker` | `action_id`, `tool_name`, `started_at` | Must follow allow/approved policy. |
| `tool_stdout_chunk` | `tool_broker` | `action_id`, `chunk_ref` | Large chunks may be artifacts. |
| `tool_stderr_chunk` | `tool_broker` | `action_id`, `chunk_ref` | Must redact secrets. |
| `tool_completed` | `tool_broker` | `action_id`, `status`, `output_summary` | Output may be truncated. |
| `tool_failed` | `tool_broker` | `action_id`, `error_id`, `safe_user_message` | No raw tracebacks to user. |
| `tool_result_truncated` | `tool_broker` | `action_id`, `limit`, `artifact_path` | Required when limits are hit. |
| `verification_completed` | `verifier` | `verification_id`, `status`, `checks` | Stub allowed in Phase 1. |
| `memory_candidate_reviewed` | `memory_governance` | `candidate_id`, `decision` | Phase 1 may only create/defer candidates. |
| `response_created` | `runtime` | `response_id`, `status`, `summary` | Final or approval-required response. |
| `checkpoint_created` | `checkpoint_service` | `checkpoint_id`, `manifest_path`, `last_event_id` | Phase 1 writes checkpoint stub/manifest. |
| `turn_state_changed` | `runtime` | `from_state`, `to_state`, `reason` | Required when runtime state changes are logged. |
| `turn_closed` | `runtime` | `turn_id`, `status`, `last_event_id` | Terminal event for completed/denied/failed turn. |
| `error_recorded` | `runtime` | `error_id`, `error_type`, `recoverable`, `safe_user_message` | Error content must be safe. |

---

## Phase 2 Canonical Events: Task Lifecycle

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `task_created` | `task_manager` | `task_id`, `session_id`, `title`, `objective`, `status` | Emitted when a task is created. |
| `task_started` | `task_manager` | `task_id`, `session_id`, `started_at` | Emitted when a task actually begins execution. |
| `task_progress` | `task_manager` | `task_id`, `current_step`, `progress_percent`, `status` | Emitted when task progress or step changes. |
| `task_paused` | `task_manager` | `task_id`, `reason` | Emitted when a task is paused at a safe boundary. |
| `task_cancelled` | `task_manager` | `task_id`, `reason` | Emitted when a task is cancelled. |
| `task_completed` | `task_manager` | `task_id`, `summary` | Emitted when a task completes successfully. |
| `task_failed` | `task_manager` | `task_id`, `reason` | Emitted when a task fails. |

## Phase 2 Canonical Events: Side Questions / Interrupts / UI Actions

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `side_question_received` | `runtime` | `side_turn_id`, `parent_task_id`, `mode`, `question` | Emitted when a side question is received. |
| `side_question_answered` | `runtime` | `side_turn_id`, `answer_summary` | Emitted when a side question is answered. |
| `interrupt_received` | `runtime` | `task_id`, `interrupt_type` | Emitted when an interrupt is received. |
| `safe_boundary_reached` | `runtime` | `task_id`, `boundary_type` | Emitted when the runtime reaches a safe boundary. |
| `task_steered` | `runtime` | `task_id`, `new_instruction`, `requires_approval` | Emitted when a task is steered with a new instruction. |

## Later-Phase Event Families

These event names are reserved and must not be used with different meanings.

| Family | Reserved events | First active phase |
|---|---|---:|
| Background tasks | `task_created`, `task_started`, `task_progress`, `task_paused`, `task_cancelled`, `task_completed`, `task_failed` | Phase 2 |
| Side questions | `side_question_received`, `side_question_answered` | Phase 2 |
| Interrupts/steering | `interrupt_received`, `safe_boundary_reached`, `task_steered` | Phase 2 |
| Models | `model_profile_loaded`, `model_launch_requested`, `model_launch_completed`, `model_launch_failed`, `model_request_started`, `model_output_chunk`, `model_request_completed`, `model_request_failed` | Phase 1-2 |
| Hooks | `hook_registered`, `hook_started`, `hook_completed`, `hook_failed`, `hook_decision_proposed` | Phase 2 |
| Plugins | `plugin_discovered`, `plugin_manifest_loaded`, `plugin_manifest_invalid`, `plugin_permission_diff_created`, `plugin_enabled`, `plugin_disabled` | Phase 3 |
| Channels | `channel_profile_loaded`, `channel_link_requested`, `channel_linked`, `channel_message_received`, `channel_message_rejected`, `channel_unlinked` | Phase 3-4 |
| Checkpoints | `checkpoint_requested`, `checkpoint_created`, `checkpoint_restore_requested`, `checkpoint_restore_approved`, `checkpoint_restored`, `checkpoint_restore_failed`, `session_forked` | Phase 1-2 |
| Memory | `memory_candidate_created`, `memory_candidate_reviewed`, `memory_record_created`, `memory_record_updated`, `memory_record_forgotten`, `memory_used_in_context` | Phase 1-3 |
| Graph/codemap | `graph_index_requested`, `graph_snapshot_created`, `graph_node_created`, `graph_edge_created`, `graph_query_completed`, `graph_snapshot_marked_stale` | Phase 3 |
| Execution environments | `execution_profile_loaded`, `execution_started`, `execution_output_chunk`, `execution_completed`, `execution_failed`, `execution_cleaned_up` | Phase 4-5 |

---

## Event Indexing Requirements

Every event written to JSONL must produce one SQLite index row with:

- `event_id`;
- `session_id`;
- `turn_id`, if available;
- `task_id`, if available;
- `event_type`;
- `actor`;
- `timestamp`;
- `jsonl_path`;
- `jsonl_offset`, when available;
- `payload_sha256`;
- `risk_level`, when applicable;
- `summary`.

The event writer must flush events in deterministic order for a single turn. If async work is introduced later, event ordering must remain deterministic by event timestamp plus sequence counter or monotonic append order.

---

## Event Test Requirements

Tests must prove:

1. every Phase 1 event validates against the envelope;
2. missing required event fields are rejected;
3. simple chat emits the expected sequence;
4. filesystem query emits policy and tool events in order;
5. denied action does not emit `tool_started`;
6. approval-required local action does not execute by default;
7. JSONL append order matches runtime order;
8. SQLite `events_index` points to the written JSONL record;
9. client/interface metadata is preserved;
10. secret-like values are redacted or omitted.

## Phase 3 rollout slice A planning event names

These event names are reserved for the read-only workspace inspection and plugin registration planning boundary. They are deterministic planning/inspection events only and must not imply runtime activation:

| Event type | Meaning |
|---|---|
| `phase3.workspace.inspection.requested` | A read-only workspace inspection summary was requested through a shared client contract. |
| `phase3.plugin.manifest.validated` | A plugin manifest was validated as data without importing or executing plugin code. |
| `phase3.plugin.registration.planned` | A plugin registration plan was prepared with execution disabled. |
| `phase3.plugin.registration.denied` | A plugin registration plan was denied by manifest or policy checks. |
| `phase3.client.contract.inspected` | A future client contract parity surface was inspected. |

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

### Phase 3 Slice C/D planning and denial events

- `phase3.graph.plan.requested` — graph/codemap dry-run plan requested; does not imply indexing.
- `phase3.graph.plan.created` — graph/codemap dry-run plan rendered; no graph records written.
- `phase3.graph.indexing.denied` — runtime graph/codemap indexing denied by Phase 3 policy.
- `phase3.memory.review.listed` — memory review queue listed; no semantic write performed.
- `phase3.memory.candidate.classified` — deterministic local candidate classification occurred; no model call.
- `phase3.memory.candidate.reviewed` — review decision state changed; no semantic write performed.
- `phase3.memory.semantic_write.denied` — semantic/vector write denied by Phase 3 policy.

## Phase 3 Slice E Preview-planning Event Names

The following event names are reserved for approval-preview planning only. They must not be emitted to imply graph indexing, semantic memory writing, embeddings, vector writes, plugin execution, or remote/container execution occurred.

```text
phase3.approval.preview.created
phase3.approval.preview.rendered
phase3.graph.approval_preview.created
phase3.memory.approval_preview.created
phase3.approval.preview.execution_denied
```

Preview events describe contracts and UI rendering only. Execution remains disabled until a later phase adds policy, audit, rollback, retention, and full CI coverage.

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

### Phase 3 Slice F planning/audit events

The following event names are reserved for future audit logging and rollback planning. They indicate preview, planning, or denial only and do not imply execution occurred:

- `phase3.approval.audit.recorded`
- `phase3.approval.audit.rendered`
- `phase3.rollback.plan.created`
- `phase3.graph.rollback_plan.created`
- `phase3.memory.rollback_plan.created`
- `phase3.rollback.execution_denied`

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

### Phase 3 Slice G metadata lifecycle events

- `phase3.storage.lifecycle.record_planned` — metadata-only lifecycle planning record was prepared; no graph index, semantic memory, vector, embedding, or rollback execution occurred.
- `phase3.storage.lifecycle.record_listed` — lifecycle metadata was listed for inspection only.
- `phase3.storage.lifecycle.record_expired` — lifecycle metadata status was changed to expired only.
- `phase3.storage.lifecycle.record_superseded` — lifecycle metadata status was changed to superseded only.
- `phase3.storage.lifecycle.runtime_write_denied` — runtime storage write remained denied by policy.

## Phase 3 Slice H Metadata-Only Lifecycle Retention Events

These events are JSON-safe, redacted, metadata-only events. They must not trigger cleanup, graph/codemap indexing, graph node/edge writes, semantic/vector memory writes, embedding creation/storage, rollback execution, plugin execution, external-channel relay, subagent spawning, or remote/container/cloud execution.

| Event name | Meaning | Runtime boundary |
|---|---|---|
| `phase3.storage.lifecycle.retention.policy_planned` | Retention policy metadata was planned. | Metadata-only; execution disabled. |
| `phase3.storage.lifecycle.cleanup.preview_created` | Cleanup preview metadata was created. | Preview-only; cleanup execution denied. |
| `phase3.storage.lifecycle.cleanup.preview_listed` | Cleanup preview metadata was listed. | Read-only. |
| `phase3.storage.lifecycle.approval_handoff.planned` | Approval handoff metadata was planned. | Planning-only; no approval relay. |
| `phase3.storage.lifecycle.approval_handoff.blocked` | Approval handoff is blocked until future policy. | Planning-only; no execution. |
| `phase3.storage.lifecycle.cleanup.execution_denied` | Cleanup execution was denied by Slice H boundary. | No cleanup may run. |
| `phase3.storage.lifecycle.handoff.execution_denied` | Approval handoff execution was denied by Slice H boundary. | No approval relay or execution may run. |

## Phase 3 Slice I Lifecycle Evidence and Policy Simulation Events

These events are metadata-only. They are read-only/export-only/simulation-only and never execute cleanup, graph/codemap indexing, graph writes, semantic/vector memory writes, embedding generation/storage, rollback, plugin, channel, subagent, remote, container, or cloud behavior.

| Event name | Meaning | Runtime boundary |
|---|---|---|
| `phase3.storage.lifecycle.evidence.bundle_created` | Evidence bundle metadata was created for inspection/export. | Metadata-only; export-only; no execution. |
| `phase3.storage.lifecycle.evidence.bundle_listed` | Evidence bundles were listed. | Read-only; no execution. |
| `phase3.storage.lifecycle.evidence.export_rendered` | Redacted deterministic evidence JSON/text was rendered. | Export-only; no execution. |
| `phase3.storage.lifecycle.policy_simulation.created` | Policy simulation metadata was created. | Simulation-only; no cleanup or approval relay. |
| `phase3.storage.lifecycle.policy_simulation.listed` | Policy simulations were listed. | Read-only; no execution. |
| `phase3.storage.lifecycle.policy_simulation.rendered` | Simulation output was rendered. | Simulation-only; no execution. |
| `phase3.storage.lifecycle.policy_simulation.execution_denied` | Runtime execution remained denied during simulation. | No cleanup, graph, memory, vector, embedding, rollback, plugin, channel, subagent, remote, container, or cloud execution. |

## Phase 3 Slice J Metadata-Only Graph/Codemap Readiness Events

These event names are reserved for future append-only metadata reporting only. Slice J does not emit runtime graph indexing events and does not start workers, schedulers, file watchers, daemons, graph writes, codemap writes, runtime execution, or indexing jobs.

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `graph_codemap_readiness_metadata_created` | `graph_readiness_registry` | `readiness_id`, `metadata_only`, `ready_for_indexing`, `blockers` | Metadata-only readiness contract creation. |
| `graph_codemap_readiness_metadata_viewed` | `terminal_client` or `workspace_inspection` | `readiness_id`, `client_type`, `read_only` | Optional future view event; must remain read-only. |
| `graph_codemap_readiness_summary_viewed` | `workspace_inspection` | `metadata_only`, `ready_for_indexing`, `indexing_jobs_enabled`, `runtime_execution_enabled` | Optional summary view; must not imply runtime enablement. |


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Phase 3 remains incomplete and Phase 4 remains blocked.
