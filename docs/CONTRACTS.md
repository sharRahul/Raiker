# Raiker Contracts

This document defines the implementation contracts that builder agents must follow.

Contracts are deliberately explicit so local and cloud builder models can implement modules without guessing. Phase 1 implements the minimum contract subset, while phase-scheduled features extend the same schemas rather than inventing parallel shapes.

---

## Contract Design Rules

1. Every public contract must have a schema version.
2. IDs must be strings.
3. Timestamps must be ISO 8601 UTC strings.
4. Unknown fields should be rejected during Phase 1 unless explicitly allowed.
5. Contract tests must validate required fields and common invalid inputs.
6. Events must be append-only and never mutated after write.
7. Phase-scheduled capabilities must extend these contracts through versioned fields or new versioned contracts.

---

## PromptEnvelope

Used by every client to submit work.

```json
{
  "schema_version": "1.0",
  "request_id": "req_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "client": {
    "type": "cli",
    "name": "raiker-cli",
    "version": "0.1.0"
  },
  "user": {
    "id": "local_user",
    "display_name": null
  },
  "prompt": {
    "text": "List files in this project",
    "attachments": [],
    "metadata": {}
  },
  "options": {
    "planning_mode": "auto",
    "approval_mode": "interactive",
    "model_profile": "mock",
    "max_tool_calls": 10
  }
}
```

Required fields:

- `schema_version`
- `request_id`
- `session_id`
- `turn_id`
- `client.type`
- `prompt.text`
- `options.planning_mode`
- `options.approval_mode`

Allowed `planning_mode` values:

- `auto`
- `always`
- `never_safe_only`

Allowed `approval_mode` values:

- `interactive`
- `deny_risky`
- `allow_safe_only`

---

## AgentEvent

Every meaningful activity is recorded as an event.

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01H...",
  "timestamp": "2026-06-17T12:00:00Z",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "event_type": "prompt_received",
  "actor": "agent_gateway",
  "payload": {},
  "parent_event_id": null
}
```

Required event types for Phase 1:

- `prompt_received`
- `prompt_normalised`
- `intent_classified`
- `risk_classified`
- `context_gathered`
- `plan_created`
- `plan_skipped`
- `action_proposed`
- `policy_decision`
- `approval_requested`
- `approval_received`
- `approval_denied`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `verification_completed`
- `memory_candidate_reviewed`
- `response_created`
- `checkpoint_created`
- `turn_closed`
- `error_recorded`

---

## IntentClassification

```json
{
  "intent": "filesystem_query",
  "confidence": 0.84,
  "requires_tools": true,
  "requires_plan": false,
  "notes": "User asked to list project files."
}
```

Allowed Phase 1 intents:

- `chat`
- `filesystem_query`
- `code_inspection`
- `code_change_request`
- `shell_request`
- `unknown`

---

## RiskClassification

```json
{
  "risk_level": "medium",
  "reasons": ["filesystem_read"],
  "requires_approval": false
}
```

Allowed risk levels:

- `low`
- `medium`
- `high`
- `blocked`

Minimum Phase 1 risk rules:

- simple chat: `low`
- file read/list/glob/grep inside workspace: `medium`
- file write/delete: `high`, phase-scheduled for Phase 2 implementation, and denied in Phase 1 unless a Phase 1 task explicitly changes the rule
- local command execution: `high` and approval required
- network access: `high` or `blocked` depending on policy
- access outside workspace: `blocked` by default

---

## Plan

```json
{
  "plan_id": "plan_01H...",
  "summary": "Inspect files and answer the user.",
  "steps": [
    {
      "step_id": "step_1",
      "description": "List the repository root.",
      "expected_action": "list_directory",
      "risk_level": "medium"
    }
  ],
  "requires_approval": false
}
```

A plan must be logged when the runtime decides a plan is required. If skipped, a `plan_skipped` event must include the reason.

---

## ToolAction

```json
{
  "action_id": "act_01H...",
  "tool_name": "list_directory",
  "arguments": {
    "path": "."
  },
  "risk_level": "medium",
  "requires_approval": false,
  "proposed_by": "agent_runtime"
}
```

Allowed Phase 1 tools:

- `read_file`
- `list_directory`
- `glob`
- `grep`
- `shell`

Phase-scheduled tools are listed in `docs/TOOLS_AND_PERMISSIONS_SPEC.md` and must use this same action contract when wired.

---

## PolicyDecision

```json
{
  "decision_id": "pol_01H...",
  "action_id": "act_01H...",
  "decision": "allow",
  "reasons": ["workspace_read_allowed"],
  "requires_user_approval": false,
  "policy_version": "phase1-static-v1"
}
```

Allowed decisions:

- `allow`
- `deny`
- `needs_approval`

---

## ToolResult

```json
{
  "action_id": "act_01H...",
  "tool_name": "list_directory",
  "status": "success",
  "output": {
    "entries": ["README.md", "docs"]
  },
  "error": null,
  "started_at": "2026-06-17T12:00:00Z",
  "completed_at": "2026-06-17T12:00:01Z"
}
```

Allowed statuses:

- `success`
- `failed`
- `denied`
- `approval_required`

---

## AgentResponse

```json
{
  "schema_version": "1.0",
  "request_id": "req_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "status": "completed",
  "message": "I found README.md and docs/ in the project root.",
  "events_path": ".raiker/events/sess_01H.jsonl",
  "checkpoint_path": ".raiker/checkpoints/sess_01H/turn_01H.json"
}
```

Allowed statuses:

- `completed`
- `needs_approval`
- `denied`
- `failed`

---

## Checkpoint

```json
{
  "schema_version": "1.0",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "created_at": "2026-06-17T12:00:02Z",
  "runtime_state": "CLOSED",
  "summary": "User asked to list project files. The root directory was listed.",
  "last_event_id": "evt_01H...",
  "memory_candidates": []
}
```

---

## Phase 1 Contract Tests

Minimum tests:

- valid `PromptEnvelope` is accepted;
- missing required `PromptEnvelope` field is rejected;
- invalid planning mode is rejected;
- valid `AgentEvent` is accepted;
- event without timestamp is rejected;
- local command action produces `needs_approval` policy decision;
- workspace file read is allowed;
- outside-workspace file read is denied;
- denied action produces no tool execution;
- completed turn writes checkpoint.
