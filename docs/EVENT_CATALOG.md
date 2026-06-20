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
- Slice K did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 memory MVP is implemented. Remaining Phase 4 capabilities (external channels, subagents, multi-agent, remote/container execution) remain blocked.

## Phase 3 Slice L — approval preview persistence readiness

Reserved metadata-only events only:

- `phase3.approval_readiness.metadata_created`
- `phase3.approval_readiness.summary_viewed`
- `phase3.approval_readiness.exported`

No runtime approval execution, approval relay, durable approval queue, worker, scheduler, daemon, external channel, runtime execution, or approval action dispatch events are enabled. Slice L did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Phase 3 Slice M reserved metadata-only events

Reserved only for future metadata records: `phase3.storage_cleanup_readiness.created`, `phase3.storage_cleanup_readiness.summary_rendered`, and `phase3.storage_cleanup_readiness.exported`. These are not runtime cleanup, deletion, purge, tombstone, rollback, worker, scheduler, daemon, dispatch, or execution events. Slice M did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice O reserved metadata-only events

Reserved event names only; no runtime dispatch events are introduced:

- `phase3.external_channels_notifications.readiness.metadata_defined`
- `phase3.external_channels_notifications.readiness.summary_rendered`
- `phase3.external_channels_notifications.readiness.sqlite_metadata_recorded`

These events are metadata-only reservations and do not represent channel dispatch, notification delivery, push notification, share-link, webhook, relay, worker, scheduler, daemon, or runtime execution events.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Slice P reserves metadata-only readiness surfaces and events for future remote/container/cloud execution. Reserved metadata-only events:

- `phase3.remote_container_cloud_readiness.metadata_created`
- `phase3.remote_container_cloud_readiness.summary_viewed`
- `phase3.remote_container_cloud_readiness.exported`

No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, approval relay, plugin execution, channel activation, cleanup execution, graph/codemap indexing, semantic memory writes, or runtime execution events are enabled. Slice P did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Raiker uses `httpx.AsyncClient` for async model transport and does not use the OpenAI SDK or Pydantic. FastAPI, LangChain, and LlamaIndex are deferred because no governed API, agent-framework, or retrieval integration is implemented in this change. llama.cpp is local-first through the async OpenAI-compatible path; Ollama, LM Studio, vLLM, generic endpoints, and OpenRouter are OpenAI-compatible profiles. OpenRouter is hosted and policy-gated. The deterministic provider is test-only, and production does not fall back to deterministic providers or silently switch from local to hosted providers.

Event/status labels distinguish `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Emitted model events must contain only safe metadata: provider, profile_id, model, endpoint_kind, duration_ms, finish_reason, tool_call_count, text_length, usage summary, error_class, safe_error_code, capability booleans, and reasoning settings. Raw prompts, completions, streamed chunks, Authorization headers, API keys, file contents, and tool outputs are not event payload material.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Minimal terminal shell/status rendering only; rich panels are specified, not implemented as a full app. | Partial/minimal | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |


## Phase 2.5 local code-review workflow events

The Phase 2.5 local code-review workflow (`/review`) emits metadata-only events. Payloads never
contain raw diffs, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, or
raw tool output. Allowed payload fields: `review_id`, `mode`, `files_reviewed`, `findings_count`,
`severity_counts`, `truncated`, `redaction_applied`, `untracked_count`.

| Event | When | Payload |
|---|---|---|
| `review_started` | A local review begins. | `review_id`, `mode` |
| `review_completed` | A local review finishes successfully. | `review_id`, `mode`, `files_reviewed`, `findings_count`, `severity_counts`, `truncated`, `redaction_applied`, `untracked_count` |
| `review_failed` | A local review raises an error. | `mode`, `error_class` |

Review is local CLI-only and read-only. It does not enable plugin execution, graph/codemap indexing,
semantic/vector memory writes, external channels, notifications, remote/container/cloud execution,
process/shell/network execution, or any runtime execution; those flags remain false.

## Phase 2.6 review-to-action proposal events

The Phase 2.6 proposal-only workflow (`/review --propose-fixes`) emits an additional metadata-only
event when proposals are generated. Payloads never contain raw diffs, raw file contents, secrets,
prompt text, private reasoning, chain-of-thought, raw tool output, or full proposal text that could
contain file content. Allowed payload fields: `review_id`, `proposal_count`,
`requires_approval_count`, `would_modify_files_count`, `risk_counts`.

| Event | When | Payload |
|---|---|---|
| `review_proposals_created` | `/review --propose-fixes` generates proposals from findings. | `review_id`, `proposal_count`, `requires_approval_count`, `would_modify_files_count`, `risk_counts` |

Phase 2.6 is proposal-only. No fixes are applied, no files are modified, no tests are run, and no
shell/process/network execution is used. No GitHub PR automation, UI/API/IDE/dashboard/mobile
surface, or model-assisted/semantic review is implemented. No Phase 3/4 runtime capability is
enabled; all disabled runtime flags remain false.

## Phase 3 Slice B proposal approval planning preview events

The Phase 3 Slice B approval planning preview workflow emits metadata-only events when previews
are created, listed, and viewed. Payloads never contain raw diffs, raw file contents, secrets,
prompt text, private reasoning, chain-of-thought, raw tool output, patch content, or executable
commands. Allowed payload fields: `preview_id`, `proposal_id`, `proposal_status`, `action_type`,
`risk_level`, `requires_approval`, `would_modify_files`, `status`, `blocking_condition_count`,
`safety_check_count`, `status_filter`, `limit`, `result_count`.

| Event | When | Payload |
|---|---|---|
| `proposal_approval_preview_created` | `/proposal <proposal_id> --approval-preview` generates a preview. | `preview_id`, `proposal_id`, `proposal_status`, `action_type`, `risk_level`, `requires_approval`, `would_modify_files`, `status`, `blocking_condition_count`, `safety_check_count` |
| `proposal_approval_preview_listed` | `/approval-previews` lists previews. | `status_filter`, `limit`, `result_count` |
| `proposal_approval_preview_viewed` | `/approval-preview <preview_id>` views one preview. | `preview_id`, `status` |

Phase 3 Slice B is preview-only. No approval execution, no proposal execution, no auto-fix, no
patch application, no file mutation, no staging/unstaging, no test execution, no GitHub PR
automation, no UI/API/IDE/dashboard/mobile, and no Phase 4. `approval_execution_enabled` remains
false. No Phase 3 runtime execution is implemented by this slice; all disabled runtime flags
remain false.

## Phase 3 Slice A proposal lifecycle events

The Phase 3 Slice A metadata-only proposal lifecycle workflow emits metadata-only events when
proposals are saved, listed, viewed, and status-transitioned. Payloads never contain raw diffs,
raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw tool output,
patch content, or executable commands. Allowed payload fields: `proposal_id`, `review_id`,
`finding_id`, `action_type`, `risk_level`, `requires_approval`, `would_modify_files`, `status`,
`previous_status`, `new_status`, `status_filter`, `limit`, `result_count`.

| Event | When | Payload |
|---|---|---|
| `proposal_lifecycle_created` | `/review --propose-fixes --save-proposals` persists a proposal as a lifecycle record. | `proposal_id`, `review_id`, `finding_id`, `action_type`, `risk_level`, `requires_approval`, `would_modify_files`, `status` |
| `proposal_lifecycle_status_changed` | `/proposal <proposal_id> --mark <status>` transitions a record's status (metadata only). | `proposal_id`, `previous_status`, `new_status` |
| `proposal_lifecycle_listed` | `/proposals` lists records. | `status_filter`, `limit`, `result_count` |
| `proposal_lifecycle_viewed` | `/proposal <proposal_id>` views one record. | `proposal_id`, `status` |

Phase 3 Slice A is metadata-only and proposal-only. No proposal execution, no auto-fix, no patch
application, no file mutation, no staging/unstaging, no test execution, no GitHub PR automation,
no UI/API/IDE/dashboard/mobile, no approval execution, and no Phase 4. `approval_execution_enabled`
remains false. No Phase 3 runtime execution is implemented by this slice; all disabled runtime
flags remain false.


## Phase 5 Governed Enterprise Events

The following event names are reserved for Phase 5 enterprise governance, managed policy, org roles, audit export, plugin marketplace, hosted routines, budget, and retention/backup operations.

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `managed_policy_applied` | `policy_engine` | `rule_id`, `effect` | Managed policy deny wins over user/project/plugin allow. |
| `managed_policy_override` | `policy_engine` | `rule_id`, `overridden_action_id`, `reason` | Emitted when a managed policy overrides a previous allow. |
| `user_created` | `user_service` | `user_id`, `display_name` | New user/identity record created. |
| `user_deactivated` | `user_service` | `user_id` | User deactivated; no new sessions permitted. |
| `role_created` | `role_service` | `role_id`, `name` | Role/group record created. |
| `role_granted` | `role_service` | `role_id`, `user_id` | User assigned to role. |
| `role_revoked` | `role_service` | `role_id`, `user_id` | User removed from role. |
| `audit_export_created` | `export_service` | `export_id`, `session_filter`, `event_count` | Audit export manifest created. |
| `audit_export_verified` | `export_service` | `export_id`, `hash_valid`, `event_count` | Export integrity verified against hash chain. |
| `plugin_marketplace_install_recorded` | `marketplace_service` | `record_id`, `plugin_id`, `version`, `status` | Marketplace plugin install/plan recorded. |
| `hosted_routine_created` | `routine_service` | `routine_id`, `name`, `routine_type` | Hosted routine metadata recorded. |
| `hosted_routine_triggered` | `routine_service` | `routine_id`, `trigger` | Hosted routine triggered (metadata only; no execution). |
| `hosted_routine_completed` | `routine_service` | `routine_id`, `status` | Hosted routine completed (metadata only). |
| `budget_recorded` | `budget_service` | `budget_id`, `max_cost`, `current_cost` | Budget record created/updated. |
| `budget_exceeded` | `budget_service` | `budget_id`, `current_cost`, `max_cost` | Budget threshold exceeded; execution denied. |
| `budget_reset` | `budget_service` | `budget_id`, `previous_cost` | Budget cost reset to zero. |
| `retention_policy_applied` | `retention_service` | `policy_id`, `target_type`, `retention_days` | Retention policy applied (metadata only; no cleanup). |
| `backup_created` | `backup_service` | `manifest_id`, `backup_type` | Backup manifest created. |
| `backup_restored` | `backup_service` | `manifest_id`, `scope_json` | Backup restore record (metadata only). |

## Phase 6 Channels, Subagents, Remote Execution Events

| Event | Actor | Required payload fields | Notes |
|---|---|---|---|
| `channel_paired` | `channel_service` | `pairing_id`, `connector_id` | Channel paired with sender allowlist. |
| `channel_unpaired` | `channel_service` | `pairing_id` | Channel pairing removed. |
| `channel_message_received` | `channel_service` | `pairing_id`, `sender` | Inbound channel message. |
| `channel_message_rejected` | `channel_service` | `pairing_id`, `reason` | Inbound channel message rejected by policy. |
| `approval_relay_requested` | `relay_service` | `relay_id`, `pairing_id`, `action_id` | Approval relay requested over channel. |
| `approval_relay_approved` | `relay_service` | `relay_id`, `resolved_by` | Approval relay resolved (approved). |
| `approval_relay_denied` | `relay_service` | `relay_id`, `resolved_by` | Approval relay resolved (denied). |
| `approval_relay_denied_by_default` | `relay_service` | `pairing_id` | Approval relay denied because no explicit policy exists. |
| `subagent_contract_created` | `subagent_service` | `subagent_id`, `parent_task_id`, `mode` | Subagent contract created (no spawn). |
| `subagent_spawn_denied` | `subagent_service` | `subagent_id`, `reason` | Subagent spawn denied by policy. |
| `team_ledger_created` | `team_service` | `team_id`, `name`, `mode` | Multi-agent team ledger created. |
| `team_work_proposed` | `team_service` | `team_id`, `work_description` | Team work proposed (no execution). |
| `team_execution_denied` | `team_service` | `team_id`, `reason` | Team execution denied by policy. |
| `remote_execution_planned` | `execution_service` | `profile_id`, `profile_type` | Remote execution plan created (no execution). |
| `remote_execution_denied` | `execution_service` | `profile_id`, `reason` | Remote execution denied by policy. |
| `execution_budget_recorded` | `budget_service` | `budget_id`, `max_cost`, `current_cost` | Execution budget recorded. |
| `execution_cleanup_planned` | `cleanup_service` | `budget_id`, `planned_action` | Execution cleanup planned (no execution). |

## Raiker TUI (native interactive shell)

Raiker TUI adds **no new events**. The native interactive shell renders the existing command/runtime events and streams `TEXT_DELTA`/`LIFECYCLE`/`FINAL` from `AgentGateway.astream_prompt` into the transcript. No new storage is added.
