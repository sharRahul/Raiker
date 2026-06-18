# API And Contract Schemas

This document is the builder-facing schema reference for Raiker. It does not replace `docs/CONTRACTS.md`; it tightens the implementation details that must be reflected in code models, validators, tests, and client adapters.

All public contracts must be versioned. Unknown fields are rejected in Phase 1 unless a specific contract says otherwise.

Raiker package/application versioning starts at `0.0.0`. Patch updates must progress through `0.0.1` to `0.0.99` before the project is bumped to `0.1.0`.

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
  "version": "0.0.0",
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
    "metadata": {}
  },
  "options": {
    "planning_mode": "auto",
    "approval_mode": "interactive",
    "model_profile": "mock-test",
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
    "version": "0.0.0",
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

## Phase 3 workspace inspection contract

`WorkspaceInspectionSummary` is a read-only service-layer contract shared by terminal, desktop, web, and dashboard clients. It includes `contract`, `runtime_status`, `recent_events`, `checkpoint_timeline`, `tasks`, `approvals`, `model_profiles`, `channel_connectors`, `capability_gates`, `semantic_memory`, `execution_profiles`, and `plugin_registration_plans` keys. Clients must not bypass this contract for privileged workspace reads.

## Phase 3 plugin registration plan contract

`PluginRegistrationPlan` contains `plugin_id`, `status`, `reasons`, `permissions`, `trust_level`, `execution_enabled`, `entrypoints`, and `events`. `execution_enabled` is always `false` in this slice.


## Phase 3 rollout slice B workspace view contract

Workspace view renderers consume the existing `workspace_inspection` output and expose derived read-only shapes for future clients. Renderers must be deterministic, JSON-safe, secret-redacting, and non-mutating. They must not read storage directly when the shared inspection output already provides data, execute tools, create approvals, call models, write memory, execute plugins, activate channels, or start remote/container execution.

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

## ApprovalPreview Contract — Phase 3 Slice E

`ApprovalPreview` is a preview-only contract. It is not an approval grant and cannot execute an action.

Required fields:

```json
{
  "preview_id": "aprev_graph_... or aprev_memory_...",
  "action_type": "graph_indexing_preview | semantic_memory_write_preview",
  "target_capability": "graph_codemap_indexing | semantic_memory_writes",
  "title": "Human-readable preview title",
  "summary": "Redacted deterministic summary",
  "risk_level": "low | medium | high",
  "requested_by": "local_user",
  "created_at": "UTC ISO timestamp",
  "requires_user_approval": true,
  "can_execute_now": false,
  "execution_enabled": false,
  "reasons": [],
  "policy_decision": "denied_or_preview_only",
  "expected_events": [],
  "reversible": false,
  "affected_paths": [],
  "affected_records": [],
  "safety_notes": []
}
```

Graph previews must target `graph_codemap_indexing`, include `graph_runtime_indexing_disabled`, and never write graph records. Semantic memory previews must target `semantic_memory_writes`, include `semantic_vector_writes_disabled`, redact secret-like values, and never create embeddings, vectors, or durable semantic memory records.

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
