# API And Contract Schemas

This document is the builder-facing schema reference for Raiker. It does not replace `docs/CONTRACTS.md`; it tightens the implementation details that must be reflected in code models, validators, tests, and client adapters.

All public contracts must be versioned. Unknown fields are rejected in Phase 1 unless a specific contract says otherwise.

---

## ID Prefix Rules

| Entity | Prefix | Example |
|---|---|---|
| Request | `req_` | `req_01H...` |
| Session | `sess_` | `sess_01H...` |
| Turn | `turn_` | `turn_01H...` |
| Task | `task_` | `task_01H...` |
| Event | `evt_` | `evt_01H...` |
| Plan | `plan_` | `plan_01H...` |
| Step | `step_` | `step_1` |
| Action | `act_` | `act_01H...` |
| Policy decision | `pol_` | `pol_01H...` |
| Approval | `appr_` | `appr_01H...` |
| Checkpoint | `ckpt_` | `ckpt_01H...` |
| Memory candidate | `memcand_` | `memcand_01H...` |
| Memory record | `mem_` | `mem_01H...` |
| Verification | `ver_` | `ver_01H...` |
| Error | `err_` | `err_01H...` |

Timestamps must be UTC ISO 8601 strings ending in `Z`.

---

## Shared Client Metadata

Every interface-originated envelope must preserve client metadata:

```json
{
  "type": "tui",
  "name": "raiker-tui",
  "version": "0.1.0",
  "interface_status": "equal_primary_when_enabled"
}
```

Allowed Phase 1 client type enum values:

```text
cli
tui
desktop
web_ui
dashboard
ide
voice
hotkeys
rest
webhooks
email
slack
teams
discord
signal
browser_extension
apple_mobile
android_mobile
mobile_companion
test_harness
```

Phase 1 tests must accept all enum values even when only the terminal client is implemented.

---

## PromptEnvelope Schema

Required fields:

```json
{
  "schema_version": "1.0",
  "request_id": "req_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "client": {
    "type": "tui",
    "name": "raiker-tui",
    "version": "0.1.0",
    "interface_status": "equal_primary_when_enabled"
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

Allowed `planning_mode` values: `auto`, `always`, `never_safe_only`.

Allowed `approval_mode` values: `interactive`, `deny_risky`, `allow_safe_only`.

---

## UIActionEnvelope Schema

Used for slash commands and interface actions such as `/models`, `/channels`, `/launch`, `/doctor`, `/checkpoints`, and task controls.

```json
{
  "schema_version": "1.0",
  "request_id": "req_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "client": {
    "type": "tui",
    "name": "raiker-tui",
    "version": "0.1.0",
    "interface_status": "equal_primary_when_enabled"
  },
  "action": {
    "action_type": "model_launch",
    "name": "/launch",
    "arguments": {
      "provider": "mock",
      "model": "mock-deterministic"
    }
  }
}
```

Allowed Phase 1 action types:

```text
submit_prompt
model_launch
list_models
list_channels
request_approval
deny_approval
show_diagnostics
exit_client
```

---

## ChannelMessageEnvelope Schema

Phase 1 may validate or preserve this schema for disabled/listable channel profiles, but must not activate external channels.

```json
{
  "schema_version": "1.0",
  "message_id": "chanmsg_01H...",
  "channel_profile_id": "slack-default",
  "session_id": "sess_01H...",
  "sender": {
    "sender_id": "external_user",
    "display_name": "Example User",
    "trust_state": "untrusted"
  },
  "message": {
    "text": "What is the task status?",
    "attachments": []
  },
  "routing": {
    "mode": "side_question",
    "approval_relay_allowed": false
  }
}
```

---

## ToolAction Schema

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

```text
read_file
list_directory
glob
grep
shell
ask_user
memory_candidate
```

`shell` exists only as an approval-gated local action proposal in Phase 1. It must not auto-run.

---

## PolicyDecision Schema

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

Allowed Phase 1 decisions: `allow`, `deny`, `needs_approval`.

---

## ApprovalRequest Schema

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

## ToolResult Schema

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
  "limits": {
    "truncated": false,
    "max_items": 200,
    "artifact_path": null
  },
  "started_at": "2026-06-17T12:00:00Z",
  "completed_at": "2026-06-17T12:00:01Z"
}
```

Allowed statuses: `success`, `failed`, `denied`, `approval_required`, `cancelled`.

---

## AgentResponse Schema

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

Allowed statuses: `completed`, `needs_approval`, `denied`, `failed`, `cancelled`.

---

## CheckpointManifest Schema

The Phase 1 checkpoint may be a stub, but the manifest shape must be compatible with later restore/fork flows.

```json
{
  "schema_version": "1.0",
  "checkpoint_id": "ckpt_01H...",
  "checkpoint_type": "turn_checkpoint",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "task_id": null,
  "created_at": "2026-06-17T12:00:02Z",
  "summary": "User asked to list project files.",
  "last_event_id": "evt_01H...",
  "runtime_state": "CLOSED",
  "files": [],
  "artifacts": [],
  "memory_candidates": [],
  "restore_policy": {
    "can_restore_state": true,
    "can_restore_files": false,
    "requires_approval": false
  }
}
```

---

## Schema Test Requirements

Tests must prove:

1. required fields are enforced;
2. unknown fields are rejected in Phase 1;
3. ID prefixes are validated;
4. timestamps are UTC ISO 8601;
5. all allowed client types are accepted;
6. invalid enum values are rejected;
7. approval binding rejects mismatched action IDs;
8. local action result returns `approval_required` unless approved;
9. response preserves client metadata;
10. checkpoint manifests include `last_event_id` and `runtime_state`.
