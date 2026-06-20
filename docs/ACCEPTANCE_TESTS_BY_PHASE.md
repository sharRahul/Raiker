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

### Completed Phase 3 A-P safe foundation/readiness acceptance

Completed Phase 3 A-P acceptance is limited to the non-runtime foundation that is implemented and locally testable now. Tests must prove:

- CLI functional testing covers the implemented terminal/slash-command surfaces.
- Desktop, Web, Dashboard, and future client workspace views are read-only shared contract views and do not mutate state.
- Plugin manifest planning validates manifests, permission diffs, and unsafe metadata without installing, enabling, or executing plugins.
- Approval previews and approval-audit/rollback-plan surfaces are preview-only and cannot execute deferred graph, memory, cleanup, rollback, plugin, channel, remote, or hosted runtime work.
- Readiness metadata is deterministic and JSON-renderable for graph, memory, approval, cleanup, remote, plugin, and channel readiness.
- Storage lifecycle metadata, retention metadata, cleanup previews, handoff records, evidence bundles, and policy simulations remain metadata-only.
- Disabled-runtime validation proves plugin execution, graph/codemap runtime indexing, semantic/vector writes, embeddings, approval execution, cleanup execution, rollback execution, external channels, subagents, remote/container/cloud execution, and hosted routines remain false.

### Deferred platform acceptance after Phase 3 A-P

The following acceptance criteria are specified for later app/runtime work and are **not required** to claim the current Phase 3 A-P safe foundation/readiness completion:

- Mobile stale approval rejection in launchable Apple/Android clients.
- Web/Dashboard event stream UI reading append-only events and SQLite state in a launchable app.
- Semantic search runtime enforcing provenance, sensitivity, and trust filters.
- Graph/codemap recursive CTE runtime impact analysis and query execution.
- Checkpoint restore/fork UI parity across launchable Desktop/Web/Dashboard/Mobile/IDE/API clients.

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
/launch --provider mock --model mock-deterministic  # test-only; normal CLI should report deterministic_test_provider_requires_test_mode
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

| Test file | Required assertions |
|---|---|
| `tests/test_phase_3_workspace_views.py` | Workspace view summaries are generated from shared inspection output, deterministic, JSON-serialisable, equivalent across terminal/desktop/web/dashboard, read-only, and redact secret-like values. |
| `tests/test_phase_3_workspace_views.py` | `/workspace-view` appears in `/help`, renders a deterministic read-only workspace summary, and leaves tasks and approvals unchanged. |

GitHub Actions are temporarily paused only because the Actions run limit/quota is exhausted. While paused, local validation evidence from `docs/LOCAL_VALIDATION_GATE.md` is mandatory and full CI must be re-enabled before release tagging or when quota is available again. Full Phase 3 remains incomplete, and plugin execution, graph/codemap runtime indexing, semantic/vector writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.

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

### Phase 3 Slice E: Approval-preview UX/contracts

Required test file: `tests/test_phase_3_approval_previews.py`.

Required assertions:

- Graph approval previews can be created from dry-run graph plans and always report `can_execute_now=false` and `execution_enabled=false`.
- Graph approval previews do not write graph indexes and unsafe graph plans are denied/preview-only.
- Semantic memory approval previews can be created from memory review items and always report `can_execute_now=false` and `execution_enabled=false`.
- Semantic memory approval previews do not write semantic memory, embeddings, or vectors.
- Secret-like memory candidates produce denied high-risk previews with redacted output.
- Preview rendering is deterministic.
- Workspace inspection includes `approval_preview_summary`.
- CLI preview commands are read-only/preview-only.
- Plugin execution, graph runtime indexing, semantic/vector writes, external channels, remote/container execution, subagents, and multi-agent teams remain disabled.

GitHub Actions remain paused due quota exhaustion; local validation evidence is mandatory and CI must be re-enabled later when quota is available.

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

## Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/completed/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/completed/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Phase 3 Slice Q1 documented default access shell (Primary/Main, Activity, Input, Status Bar) is implemented; advanced/optional/plugin panels remain specified, not implemented as a full app. | Partial (default access shell) | None. | Build advanced/optional panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |



## Phase 3 Slice Q1 — Documented Default Rich TUI Access Shell

Q1 acceptance (default layout only): the default layout renders the Primary/Main,
Activity, Input, and Status Bar panels; `raiker --prompt "Hello Raiker"` and
`raiker --prompt "/help"` still work; `/models`, `/model current`, `/model capabilities`,
`/status`, `/events`, `/approvals`, and `/review --summary` route through existing command
handlers; unsupported commands show a safe error; the plain fallback (`RAIKER_TUI=plain`)
remains available; accessibility safety labels (state, network, approvals, disabled
runtime) remain present in no-colour/ASCII/narrow modes; and TUI panel modules introduce no
tool/model/shell/process/network execution. Covered by
`tests/test_phase_3_slice_q1_rich_tui_default_layout.py`,
`tests/test_phase_3_slice_q1_rich_tui_accessibility.py`,
`tests/test_phase_3_slice_q1_rich_tui_command_access.py`,
`tests/test_phase_3_slice_q1_rich_tui_safety.py`, and
`tests/test_phase_3_slice_q1_docs_truthfulness.py`. Advanced/optional panels and
desktop/web/mobile/dashboard apps remain deferred and are not required for Q1 completion.
