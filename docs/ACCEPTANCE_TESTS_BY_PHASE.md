# Acceptance Tests By Phase

This document defines the acceptance tests that prove Raiker is implemented according to the documentation. It complements `docs/VERIFICATION_PLAN.md` by grouping tests by phase and by implementation gate.

A feature is not complete until its acceptance tests exist and pass.

---

## Global Acceptance Rules

Every phase must preserve these rules:

1. Every enabled interface enters through the Agent Gateway.
2. No tool executes without a policy decision.
3. Denied actions do not execute.
4. Approval-required actions bind approval to the exact action ID.
5. Events are append-only and indexed in SQLite.
6. Runtime transitions follow the canonical state machine.
7. Checkpoints are written where the phase requires them.
8. Memory writes are governed and auditable.
9. Phase-scheduled features remain disabled until explicitly in scope.
10. No interface becomes privileged because it was implemented earlier.

---

## Phase 1: Secure Local Interface Core

### Contract Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_contracts.py` | PromptEnvelope validates; invalid required fields fail; schema version required; allowed client types accepted; invalid client types rejected. |
| `tests/test_id_helpers.py` | IDs have correct prefixes; timestamps are UTC ISO 8601. |
| `tests/test_equal_interface_invariant.py` | Docs/config do not define terminal/TUI as canonical or exclusive; all enabled clients use shared contracts. |

### Storage And Events Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_storage_sqlite.py` | Fresh `.raiker/raiker.db` creates schema tables; migrations table exists; WAL and foreign keys are enabled. |
| `tests/test_event_log.py` | JSONL appends one object per line; events are never rewritten; SQLite indexes event metadata; event order matches runtime order. |
| `tests/test_event_catalog.py` | Required Phase 1 event names are recognised; unknown event names fail unless explicitly versioned. |

### Policy And Broker Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_policy_engine.py` | Inside-workspace read/list/glob/grep allowed; outside-workspace access denied; local command returns `needs_approval`; policy reasons included. |
| `tests/test_tool_broker.py` | Unknown tool fails safely; action without policy cannot execute; denied action does not execute; output limits and structured errors are returned. |
| `tests/test_path_safety.py` | Path traversal and symlink escape are blocked unless policy explicitly allows. |

### Tool Acceptance

| Tool | Required assertions |
|---|---|
| `read_file` | Reads text inside workspace; missing file returns structured error; outside workspace denied; binary handling explicit. |
| `list_directory` | Stable sorted output; bounded entries; outside workspace denied. |
| `glob` | Workspace-scoped; bounded results; deterministic ordering. |
| `grep` | Text-only; bounded results; no secret leakage in logs. |
| `shell` | Proposal only; requires approval; does not execute by default. |

### Runtime Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_runtime_state_machine.py` | Valid simple-chat and filesystem transitions reach `CLOSED`; invalid transitions fail; denied and approval-required paths do not execute. |
| `tests/test_classifier_planner.py` | Simple chat requires no tools; filesystem prompt maps to `filesystem_query`; local command maps to approval-gated action; plan-created/skipped events include reasons. |
| `tests/test_verification_stub.py` | Tool success verifies passed; denied/failed actions verify partial/failed with reason; verification event emitted. |

### Model And Registry Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_mock_model_provider.py` | Mock provider is deterministic; no network or local model install required. |
| `tests/test_model_profile_registry.py` | Model profiles load; `mock` profile exists; unknown provider fails clearly; disabled hosted providers do not run. |
| `tests/test_channel_connector_registry.py` | Connector profiles load; disabled profiles are listable; Apple and Android mobile profiles exist; disabled connector cannot receive messages. |

### Gateway, Session, Checkpoint Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_agent_gateway.py` | Valid envelope reaches runtime; invalid envelope returns structured failure; client metadata preserved. |
| `tests/test_session_manager.py` | Session create/load works; turn IDs tracked; event/checkpoint paths attach to session. |
| `tests/test_checkpoint_service.py` | Checkpoint manifest path deterministic; completed turn writes checkpoint stub; manifest includes last event ID and summary. |

### Terminal MVP Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_global_command.py` | Installed `raiker` command opens configured terminal client or documented bootstrap module path. |
| `tests/test_terminal_client_smoke.py` | Terminal prompt creates PromptEnvelope, calls gateway, renders response, creates event log and checkpoint. |
| `tests/test_terminal_approvals.py` | Approval card is shown; action does not run by default; approval request event exists. |
| `tests/test_terminal_registry_panels.py` | `/channels` and `/models` list registry profiles; disabled profiles visible as disabled. |

---

## Phase 2: Rich Local Workspace

### Phase 2 Foundation Acceptance (Slice: task/status/event/checkpoint inspection)

| Test file | Required assertions |
|---|---|
| `tests/test_phase_2_task_manager.py` | Task rows are created/listed/updated deterministically; task events are appended and indexed; task manager lifecycle works. |
| `tests/test_phase_2_event_viewer.py` | Events can be listed by session, turn, task, type; event index rows are readable; event payload is readable; read-only queries do not mutate. |
| `tests/test_phase_2_checkpoint_timeline.py` | Checkpoints can be listed by session; checkpoint metadata is readable; listing is deterministic. |
| `tests/test_phase_2_terminal_commands.py` | `/status` shows session/workspace state; `/tasks` lists tasks; `/events` lists recent events; `/checkpoints` lists checkpoint metadata; commands do not execute tools. |

### Phase 2 Full Acceptance

Acceptance tests must prove:

- Task rows are created/listed/updated deterministically.
- Task lifecycle events are appended and indexed.
- Task manager does not execute tools.
- Event viewer queries are read-only and bounded.
- `/status`, `/tasks`, `/events`, `/checkpoints` commands render state without tool execution.
- CI runs on every PR and push to main.
- Rich TUI task panel updates from event stream.
- Background tasks can pause, cancel, steer, and resume at safe boundaries.
- Side questions do not corrupt active task state.
- File edits create snapshots before mutation.
- Checkpoint restore requires approval when files change.
- Local model providers are launched or connected through model profiles.
- Memory writes require governance approval.
- Hooks run only through the hook engine and cannot bypass policy.
- Scoped command allowlists remain auditable.

---

## Phase 3: Desktop, Web, Mobile, Plugins, Graph, Semantic Memory

Acceptance tests must prove:

- Desktop, Web, Dashboard, Apple mobile, Android mobile, IDE, and API clients use the same Agent Gateway.
- Mobile approval rejects stale action state.
- Web/Dashboard event stream reads append-only events and SQLite state.
- Plugin manifests validate before install/enable.
- Disabled plugins cannot contribute tools, hooks, commands, channels, or panels.
- Plugin permission diff detects expanded permissions.
- Semantic search enforces provenance, sensitivity, and trust filters.
- Graph/codemap recursive CTE impact analysis works.
- Checkpoint restore/fork has interface-equivalent actions across enabled clients.

---

## Phase 4: Channels, Multi-Agent, Remote Execution

Acceptance tests must prove:

- Unknown channel senders are rejected or forced into pairing.
- Channel messages create ChannelMessageEnvelope and enter the Agent Gateway.
- Channel approval relay is disabled by default and action-bound when enabled.
- Subagents have bounded tools, model profile, memory scope, runtime, and depth.
- Parent runtime verifies subagent outputs.
- Cancellation cascades to subagents and remote jobs.
- Container/SSH/VPS execution profiles enforce resource, egress, and cleanup policy.
- Remote execution artifacts are captured and event logged.

---

## Phase 5: Governed Enterprise/Home-Lab Platform

Acceptance tests must prove:

- Managed policy precedence works.
- Event integrity checks detect tampering.
- Signed plugins validate signatures and checksums.
- Multi-user permissions isolate sessions, approvals, memory, and secrets.
- Audit export includes events, policy decisions, approvals, tool actions, checkpoints, and config versions.
- Hosted provider budgets block over-limit requests.
- Enterprise/home-lab deployment config does not weaken local-first defaults.

---

## Manual Acceptance Script For Phase 1

After Phase 1 implementation, a human or builder agent must run:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Manual terminal actions:

```text
Hello Raiker
List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

Expected results:

- simple prompt completes;
- filesystem query goes through policy and broker;
- local action prompt pauses for approval;
- event JSONL exists;
- SQLite event index exists;
- checkpoint manifest exists;
- `/channels` and `/models` display disabled/listable profiles;
- no hosted/network/plugin/channel/subagent runtime is active unless explicitly in phase scope.

### Phase 3 rollout slice A acceptance evidence

| Test file | Required assertions |
|---|---|
| `tests/test_phase_3_capability_states.py` | Phase 3 capability states cannot jump directly to runtime; unknown capabilities are denied; Phase 4 gates remain disabled. |
| `tests/test_phase_3_workspace_inspection.py` | Desktop, web, and dashboard inspection requests return equivalent shared read-only data shapes and do not mutate tasks, approvals, memory, channels, plugins, or execution. |
| `tests/test_phase_3_equal_workspace_clients.py` | Future clients share `UIActionEnvelope` metadata and no client is privileged or allowed direct tool calls. |
| `tests/test_phase_3_plugin_policy.py` | Plugin registration planning validates manifests, denies unsafe prefixes, approval-gates risky permissions, treats entrypoints as metadata, and never enables execution. |
| `tests/test_phase_3_terminal_commands.py` | `/workspace`, `/clients`, `/plugins`, and `/plugin-plan <manifest_path>` are inspection-only and return helpful output. |


### Phase 3 rollout slice B acceptance evidence

Slice B acceptance tests cover the read-only workspace view/API foundation: views are generated from the shared inspection contract, text output is deterministic, JSON/dashboard views are JSON-serialisable, terminal/desktop/web/dashboard clients receive equivalent read-only data, secret-like fields are redacted, unknown fields are handled safely, and rendering does not mutate tasks, approvals, semantic memory candidates, plugins, channels, or remote/container execution gates. Evidence: `tests/test_phase_3_workspace_views.py` and `/workspace-view` assertions in `tests/test_phase_3_terminal_commands.py`.
