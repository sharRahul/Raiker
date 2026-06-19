# Runtime Orchestration Specification

Raiker runtime orchestration coordinates prompts, planning, context, tools, approvals, hooks, subagents, background tasks, side questions, verification, checkpoints, and final responses.

The runtime must be deterministic in state transitions even when work is asynchronous.

---

## Runtime Goals

The runtime must support normal prompt turns, planned multi-step work, background tasks, side questions while tasks continue, interrupts and steering, approvals, tool batches, subagent delegation, verification, checkpoints, cancellation, and error recovery.

---

## Runtime State Machine

Primary turn states:

```text
RECEIVED
  -> NORMALISED
  -> CLASSIFIED
  -> CONTEXT_READY
  -> PLAN_READY or PLAN_SKIPPED
  -> POLICY_REVIEWED
  -> EXECUTING or WAITING_FOR_APPROVAL or DENIED
  -> OBSERVING
  -> VERIFYING
  -> MEMORY_REVIEWING
  -> RESPONDING
  -> CHECKPOINTING
  -> CLOSED
```

Failure states:

```text
FAILED
CANCELLED
PAUSED
WAITING_FOR_USER
```

---

## Background Task State Machine

```text
QUEUED
  -> RUNNING
  -> WAITING_FOR_APPROVAL
  -> WAITING_FOR_USER_ANSWER
  -> PAUSED
  -> RUNNING
  -> VERIFYING
  -> COMPLETED
```

Terminal states:

```text
COMPLETED
FAILED
CANCELLED
EXPIRED
```

---

## Task Contract

```json
{
  "schema_version": "1.0",
  "task_id": "task_01H...",
  "session_id": "sess_01H...",
  "parent_turn_id": "turn_01H...",
  "title": "Expand documentation",
  "objective": "Add missing Raiker platform specs.",
  "status": "running",
  "plan_id": "plan_01H...",
  "created_at": "2026-06-17T12:00:00Z",
  "updated_at": "2026-06-17T12:05:00Z",
  "progress": {
    "current_step": "Writing hooks spec",
    "completed_steps": 3,
    "total_steps": 12,
    "percent": 25
  },
  "controls": {
    "can_pause": true,
    "can_cancel": true,
    "can_steer": true,
    "can_ask_side_question": true
  }
}
```

---

## Side Question Runtime

A side question creates a child turn:

```json
{
  "schema_version": "1.0",
  "side_turn_id": "turn_side_01H...",
  "parent_task_id": "task_01H...",
  "mode": "read_only_status",
  "question": "What is it doing now?",
  "allowed_context": ["task_state", "event_log", "plan", "recent_tool_results"],
  "may_mutate_parent": false
}
```

Side question modes:

| Mode | Behaviour |
|---|---|
| `read_only_status` | Answer status/progress only. |
| `explain_last_event` | Explain last event/error/tool result. |
| `inspect_changes` | Summarise changed files. |
| `steering_proposal` | Draft a possible change, but do not apply. |
| `escalated_interrupt` | User explicitly asks to change active work. |

---

## Interrupt And Steering Runtime

Interrupt lifecycle:

```text
interrupt_received
  -> mark task interrupt_requested
  -> wait for safe boundary
  -> pause or cancel or steer
  -> log task_interrupted
```

Steering lifecycle:

```text
steering_instruction_received
  -> classify risk
  -> update plan if safe
  -> request approval if risky
  -> emit task_steered
```

The runtime must not modify an executing tool mid-flight except through cancellation APIs where safe.

---

## Parallel Tool Batches

Parallel safe tool batches are phase-scheduled for Phase 3+ implementation and are fully specified here.

Rules:

- all actions are policy-reviewed independently;
- batch has max concurrency;
- output order is deterministic by action ID;
- failures are isolated;
- PostToolBatch hooks run after all complete;
- event log records start/end per action and batch;
- cancellation can stop queued actions and request cancellation for running actions;
- TUI/Web/Desktop task panels must show batch progress.

---

## Verification

Verification checks whether the task result satisfies user intent.

Verification types:

- `contract_validation`;
- `test_execution`;
- `lint/typecheck`;
- `file_exists`;
- `diff_review`;
- `security_check`;
- `manual_review_required`;
- `model_judge` with strict schema.

Verification must produce:

```json
{
  "verification_id": "ver_01H...",
  "status": "passed",
  "checks": [
    {"name": "event_log_created", "status": "passed"}
  ],
  "notes": []
}
```

### Phase 1/2 context gathering and verification (implemented)

Context gathering and verification are no longer pass-through stubs. Both are
`implemented_verified` for the Phase 1/2-safe scope and are wired into the normal runtime turn.

Context gathering (`raiker/context/`): before the model loop, the runtime calls
`ContextGatherer.gather(...)`, which builds a bounded, deterministic `ContextBundle` from safe
local metadata sources only — `current_prompt`, `workspace_summary`, `recent_events`, `tasks`,
`checkpoints`, `approvals`, `memory_status`, `memory_candidates`, `model_profile`, and
`capability_status`. Every item records source type, trust level, provenance, sensitivity, and a
redaction flag. Secrets/tokens/emails/private keys are masked with deterministic placeholders,
budgeting is applied by item count and characters, and a metadata-only summary is emitted on the
`context_gathered` event (`context_bundle_id`, `source_types`, counts, `truncated`,
`redaction_applied`). The fixed `sources=["current_prompt"]` placeholder is removed. This is
bounded local-metadata context, not full repository intelligence, and it never enables graph
runtime, semantic search, vector memory, plugin execution, external channels, or
remote/container/cloud context.

Verification (`raiker/verification/`): a deterministic `Verifier` runs safety/result-shape checks
inside the loop and emits `verification_started`/`verification_completed`. It validates tool-call
schemas (unknown/invalid calls fail and never execute), confirms denied actions did not execute,
confirms approval-required actions stopped before execution with an approval record, validates
safe read-tool result shape, and confirms mutation proposals remain approval-gated. The verifier
result carries `safe_to_continue`; its output never exposes hidden reasoning, chain-of-thought,
scratchpads, or system prompts. This is safety/result-shape verification, not a
semantic-correctness proof. No disabled runtime flag is enabled by these steps.

---

## Error Handling

Runtime errors must be structured:

```json
{
  "error_id": "err_01H...",
  "error_type": "tool_failed",
  "message": "grep timed out",
  "recoverable": true,
  "safe_user_message": "Search timed out before completing.",
  "debug_ref": "evt_01H..."
}
```

Errors must not leak secrets.

---

## Runtime Events

Required events:

- `turn_state_changed`
- `task_created`
- `task_started`
- `task_progress`
- `task_paused`
- `task_cancelled`
- `task_steered`
- `task_completed`
- `task_failed`
- `side_question_received`
- `side_question_answered`
- `interrupt_received`
- `safe_boundary_reached`
- `verification_started`
- `verification_completed`
- `runtime_error_recorded`
- `tool_batch_started`
- `tool_batch_completed`

---

## Testing Requirements

Tests must prove:

- invalid state transition fails;
- side question runs without pausing task;
- interrupt waits for safe boundary;
- steering updates plan only after classification;
- cancelled task stops scheduled tool execution;
- verification result is logged;
- recoverable error leads to safe response;
- event order is deterministic;
- phase-scheduled parallel batches preserve deterministic result ordering.

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
