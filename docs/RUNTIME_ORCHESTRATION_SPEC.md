# Runtime Orchestration Specification

Raiker runtime orchestration coordinates prompts, planning, context, tools, approvals, hooks, subagents, background tasks, side questions, verification, checkpoints, and final responses.

The runtime must be deterministic in state transitions even when work is asynchronous.

---

## Runtime Goals

The runtime must support:

1. normal prompt turns;
2. planned multi-step work;
3. background tasks;
4. side questions while tasks continue;
5. interrupts and steering;
6. approvals;
7. tool batches;
8. subagent delegation;
9. verification;
10. checkpoints;
11. cancellation;
12. error recovery.

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

Future phases may allow parallel safe tools.

Rules:

- all actions are policy-reviewed independently;
- batch has max concurrency;
- output order is deterministic by action ID;
- failures are isolated;
- PostToolBatch hooks run after all complete;
- event log records start/end per action and batch.

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

---

## Testing Requirements

Tests must prove:

- invalid state transition fails;
- side question runs without pausing task;
- interrupt waits for safe boundary;
- steering updates plan only after classification;
- cancelled task stops future tool execution;
- verification result is logged;
- recoverable error leads to safe response;
- event order is deterministic.
