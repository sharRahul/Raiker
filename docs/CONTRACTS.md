> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Raiker Contracts

This document defines the implementation contracts that builder agents must follow.

Contracts are deliberately explicit so local and cloud builder models can implement modules without guessing. Phase 1 implements the minimum contract subset, while phase-scheduled features extend the same schemas rather than inventing parallel shapes.

All primary interfaces use the same contracts. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients must not create separate prompt, approval, checkpoint, memory, model, or task-control schemas.

Raiker package/application versioning starts at `0.0.0`. Patch updates must progress through `0.0.1` to `0.0.99` before the project is bumped to `0.1.0`.

---

## Contract Design Rules

1. Every public contract must have a schema version.
2. IDs must be strings.
3. Timestamps must be ISO 8601 UTC strings ending in `Z`.
4. Unknown fields should be rejected during Phase 1 unless explicitly allowed.
5. Contract tests must validate required fields and common invalid inputs.
6. Events must be append-only and never mutated after write.
7. Phase-scheduled capabilities must extend these contracts through versioned fields or new versioned contracts.
8. The originating interface/client identity must be preserved for audit and routing.
9. No interface may bypass these contracts because it is terminal, mobile, chat, desktop, web, or programmatic.

---

## PromptEnvelope

Used by every client to submit work. In Phase 1, the first implemented user-facing path is the configured local terminal client opened by the global `raiker` command. That path is not contractually primary over other interfaces.

```json
{
  "schema_version": "1.0",
  "request_id": "req_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "client": {
    "type": "tui",
    "name": "raiker-tui",
    "version": "0.0.0",
    "interface_status": "equal_primary_when_enabled"
  },
  "user": {
    "id": "local_user",
    "display_name": null
  },
  "prompt": {
    "text": "List files in this project",
    "attachments": [],
    "metadata": {
      "entry_command": "raiker"
    }
  },
  "options": {
    "planning_mode": "auto",
    "approval_mode": "interactive",
    "model_profile": "raiker-local-llama-cpp",
    "max_tool_calls": 10000
  }
}
```

Required fields:

- `schema_version`
- `request_id`
- `session_id`
- `turn_id`
- `client.type`
- `client.name`
- `client.version`
- `client.interface_status`
- `prompt.text`
- `options.planning_mode`
- `options.approval_mode`

Allowed `client.type` values include:

- `cli`
- `tui`
- `desktop`
- `web_ui`
- `dashboard`
- `ide`
- `voice`
- `hotkeys`
- `rest`
- `webhooks`
- `email`
- `slack`
- `teams`
- `discord`
- `signal`
- `browser_extension`
- `apple_mobile`
- `android_mobile`
- `mobile_companion`
- `test_harness`

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
  "task_id": null,
  "event_type": "prompt_received",
  "actor": "agent_gateway",
  "payload": {
    "client_type": "tui"
  },
  "parent_event_id": null
}
```

Required event types for Phase 1:

- `global_command_invoked`
- `terminal_client_started`
- `tui_started`
- `tui_prompt_submitted`
- `ui_action_submitted`
- `prompt_received`
- `prompt_normalised`
- `intent_classified`
- `risk_classified`
- `context_gathered`
- `plan_created`
- `plan_skipped`
- `action_proposed`
- `action_validated`
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
- `turn_state_changed`
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
- `local_action_request`
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
- `critical`
- `blocked`

Minimum Phase 1 risk rules:

- simple chat: `low`
- file read/list/glob/grep inside workspace: `medium`
- file write/delete: `high`, phase-scheduled for Phase 2 implementation, and denied in Phase 1 unless a Phase 1 task explicitly changes the rule
- local action that can affect the machine: `high` and approval required
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
  "schema_version": "1.0",
  "action_id": "act_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "task_id": null,
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
- `ask_user`
- `memory_candidate`

`shell` exists only as an approval-gated local action proposal in Phase 1. It must not auto-run.

---

## PolicyDecision

```json
{
  "schema_version": "1.0",
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

## ApprovalRequest

```json
{
  "schema_version": "1.0",
  "approval_id": "appr_01H...",
  "action_id": "act_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "tool_name": "shell",
  "arguments_preview": {
    "command": "pytest tests/test_policy_engine.py"
  },
  "risk_level": "high",
  "policy_reasons": ["shell_requires_approval"],
  "expected_effect": "Runs tests in the current workspace.",
  "choices": ["approve_once", "deny"],
  "expires_at": null
}
```

Approvals must bind to exact `action_id`; changed arguments require a new action and approval.

---

## ToolResult

```json
{
  "schema_version": "1.0",
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
- `cancelled`

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
  "checkpoint_path": ".raiker/checkpoints/sess_01H/ckpt_01H.json",
  "client": {
    "type": "tui",
    "name": "raiker-tui",
    "interface_status": "equal_primary_when_enabled"
  }
}
```

Allowed statuses:

- `completed`
- `needs_approval`
- `denied`
- `failed`
- `cancelled`

---

## Checkpoint

```json
{
  "schema_version": "1.0",
  "checkpoint_id": "ckpt_01H...",
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

- valid terminal-originated `PromptEnvelope` is accepted;
- valid non-terminal `client.type` values are accepted by contract tests even when their runtime implementations are phase-scheduled;
- missing required `PromptEnvelope` field is rejected;
- invalid planning mode is rejected;
- valid `AgentEvent` is accepted;
- event without timestamp is rejected;
- local action produces `needs_approval` policy decision;
- workspace file read is allowed;
- outside-workspace file read is denied;
- denied action produces no tool execution;
- completed turn writes checkpoint;
- interface/client identity is preserved in events and responses.

## Runtime mode activation contract

- Command: `/runtime-mode activate <mode> --as <principal_id> --reason <reason>`
- Authority: `RuntimeAuthority.activate_runtime_mode()`
- Persistence: `runtime_mode_state` SQLite table
- Gate: `runtime_gate_manager` role required
- Events: `runtime_mode_activated`

## Capability gate transition contract

- Command: `/capability-gate enable <capability> --state <state> --as <principal_id> --reason <reason>`
- Authority: `RuntimeAuthority.enable_capability_gate()`
- Persistence: `capability_gate_state` SQLite table
- Gate: `runtime_gate_manager` role required
- Events: `capability_gate_enabled`, `capability_gate_disabled`

## Principal resolution contract

- CLI handler: `resolve_local_principal(workspace_root)`
- Behavior: loads owner principal from SQLite store; validates active status, human-only role, single match
- Returns: `(principal, error_message)` tuple
- On failure: returns `(None, "denied: <reason>")` — no fallback to synthetic principal
- Audit: events `principal_resolved` and `principal_resolution_failed`
