# Runtime State Machine

This document is the canonical transition table for Raiker turn execution. `docs/RUNTIME_ORCHESTRATION_SPEC.md` describes orchestration behaviour; this file defines exact Phase 1 states, legal transitions, emitted events, guards, and terminal conditions.

The runtime must be deterministic. A client implementation may render state differently, but it must not create different state semantics.

---

## Phase 1 Turn States

| State | Meaning |
|---|---|
| `RECEIVED` | Gateway has accepted a request envelope. |
| `NORMALISED` | Request has been normalised and validated into canonical contracts. |
| `CLASSIFIED` | Intent and risk have been classified. |
| `CONTEXT_READY` | Approved context sources have been gathered or explicitly skipped. |
| `PLAN_READY` | A plan exists because the task requires one. |
| `PLAN_SKIPPED` | Runtime explicitly skipped planning with a reason. |
| `POLICY_REVIEWED` | At least one proposed action has a policy decision, or no action was needed. |
| `EXECUTING` | Broker is executing an allowed tool action. |
| `WAITING_FOR_APPROVAL` | Runtime is paused for user approval on an exact action. |
| `DENIED` | Policy denied the proposed action. |
| `OBSERVING` | Runtime is collecting tool/model result observations. |
| `VERIFYING` | Runtime is checking whether outcome satisfies intent. |
| `RESPONDING` | Runtime is creating the user-visible response. |
| `CHECKPOINTING` | Defined in the state machine but not currently emitted by the runtime orchestrator. |
| `CLOSED` | Defined in the state machine; gateway finalisation closes the turn after checkpoint/event finalisation. |
| `FAILED` | Turn failed with structured error. |
| `CANCELLED` | Turn was cancelled by user/runtime control. |

Phase 2 adds durable `PAUSED`, `WAITING_FOR_USER`, and background task states. Phase 1 may represent approval waiting through `WAITING_FOR_APPROVAL` only.

---

## Legal Phase 1 Transitions

| From | To | Required event | Guard |
|---|---|---|---|
| `RECEIVED` | `NORMALISED` | `prompt_normalised` | Envelope validates. |
| `RECEIVED` | `FAILED` | `error_recorded` | Envelope invalid and cannot be safely normalised. |
| `NORMALISED` | `CLASSIFIED` | `intent_classified`, `risk_classified` | Prompt text or UI action is available. |
| `CLASSIFIED` | `CONTEXT_READY` | `context_gathered` | Context sources are approved or intentionally empty. |
| `CONTEXT_READY` | `PLAN_READY` | `plan_created` | Planning required by risk/task rules. |
| `CONTEXT_READY` | `PLAN_SKIPPED` | `plan_skipped` | Planning not required and reason is logged. |
| `PLAN_READY` | `POLICY_REVIEWED` | `policy_decision` | At least one action was proposed and reviewed. |
| `PLAN_SKIPPED` | `POLICY_REVIEWED` | `policy_decision` or no-op state event | Tool action exists or no tool is required. |
| `POLICY_REVIEWED` | `EXECUTING` | `tool_started` | Policy decision is `allow` or action has exact approval. |
| `POLICY_REVIEWED` | `WAITING_FOR_APPROVAL` | `approval_requested` | Policy decision is `needs_approval`. |
| `POLICY_REVIEWED` | `DENIED` | `policy_decision` | Policy decision is `deny`. |
| `POLICY_REVIEWED` | `RESPONDING` | `response_created` | No tool action is needed. |
| `EXECUTING` | `OBSERVING` | `tool_completed` or `tool_failed` | Broker returned a structured result. |
| `WAITING_FOR_APPROVAL` | `RESPONDING` | `response_created` | Phase 1 returns approval-required response. |
| `WAITING_FOR_APPROVAL` | `EXECUTING` | deferred | Approval execution relay is not implemented in the current backend. |
| `WAITING_FOR_APPROVAL` | `DENIED` | `approval_denied` | User denied the exact action. |
| `DENIED` | `RESPONDING` | `response_created` | Denial reason is safe to show. |
| `OBSERVING` | `VERIFYING` | `verification_completed` | Verification check can run or stub result is available. |
| `VERIFYING` | `RESPONDING` | `response_created` | Response can be assembled. |
| `RESPONDING` | `CHECKPOINTING` | optional internal transition | State exists in the machine but current gateway finalisation appends `checkpoint_created`. |
| `CHECKPOINTING` | `CLOSED` | optional internal transition | Gateway finalisation appends `turn_closed`. |
| Any non-terminal state | `FAILED` | `error_recorded` | Structured recoverable/unrecoverable error. |
| Any non-terminal state | `CANCELLED` | `turn_closed` or `error_recorded` | User/runtime cancellation. |

---

## Invalid Transitions

These transitions must fail tests:

| Invalid transition | Reason |
|---|---|
| `RECEIVED` -> `EXECUTING` | Bypasses normalisation, classification, context, and policy. |
| `CLASSIFIED` -> `EXECUTING` | Bypasses context/planning/policy. |
| `PLAN_READY` -> `EXECUTING` | Bypasses policy review. |
| `POLICY_REVIEWED` -> `EXECUTING` without `allow` or exact approval | Violates approval policy. |
| `WAITING_FOR_APPROVAL` -> `EXECUTING` with changed arguments | Approval must bind to exact `action_id`. |
| `DENIED` -> `EXECUTING` | Denied action must not execute. |
| `RESPONDING` -> `EXECUTING` | Final response stage cannot start new tool action. |
| `CLOSED` -> any non-fork state | Closed turns are immutable. |

---

## State Transition Event Payload

When `turn_state_changed` is emitted, payload must include:

```json
{
  "from_state": "CLASSIFIED",
  "to_state": "CONTEXT_READY",
  "reason": "approved_context_sources_gathered",
  "state_sequence": 4
}
```

`state_sequence` is monotonic inside a turn. It is used to prove deterministic ordering when events are consumed by TUI, dashboard, web, mobile, or channel clients.

---

## Planning Guard Rules

A plan is required when the task:

- has more than one action;
- writes, edits, deletes, moves, or patches files;
- runs a local command;
- changes code;
- uses network;
- creates a background task;
- uses a linked channel;
- spawns a subagent;
- affects data, cost, security, privacy, or execution environment.

A plan may be skipped only for simple chat and single safe read-only filesystem/search actions. The skipped reason must be logged.

---

## Phase 1 Terminal Behaviour

The terminal client may be the first implemented client, but it is only a client of the same gateway. Terminal prompt flow must be:

```text
terminal input
  -> PromptEnvelope
  -> AgentGateway
  -> SessionManager
  -> RuntimeStateMachine
  -> EventLog/SQLite
  -> AgentResponse
  -> terminal renderer
```

The terminal client must not directly call tools, read files, run commands, write memory, or create checkpoints outside the shared runtime path.

---

## State Machine Test Requirements

Tests must prove:

1. valid simple-chat sequence reaches `CLOSED`;
2. valid filesystem-query sequence reaches `CLOSED`;
3. local command request reaches `WAITING_FOR_APPROVAL` and does not execute;
4. denied outside-workspace read reaches `DENIED` then safe response;
5. invalid transitions raise structured errors;
6. closed turn cannot be mutated;
7. state transition events include monotonic `state_sequence`;
8. client/interface metadata is preserved through the state loop;
9. terminal path uses the same gateway as test/non-terminal client envelopes.
