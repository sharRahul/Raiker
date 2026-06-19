# Phase 2 Rich Local Workspace Build Plan

This plan decomposes Raiker Phase 2 into small implementation tasks suitable for local or cloud builder models.

The Phase 2 objective:

```text
Build a rich local workspace on top of the Phase 1 runtime core, adding task management, event inspection, checkpoint timeline, status/approval UX, side questions, interrupt/steer controls, local model provider discovery, governed memory views, and inspection commands — without making the terminal/TUI the privileged or canonical interface.
```

All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. Phase 2 may expand the terminal/TUI first, but no code, contract, event, policy rule, storage table, or runtime path may describe the terminal client as the only primary human interface or grant it a private bypass path.

---


## Phase 3 Slice G/H Impact on Phase 2

Phase 2 remains the rich local workspace foundation. Slice G/H depends on Phase 2 task, event, checkpoint, approval, and memory concepts, but it does not expand Phase 2 runtime authority. Lifecycle status changes remain metadata-only. Approval-preview, approval-audit, rollback-plan, cleanup-preview, and handoff surfaces remain read-only or planning-only. Semantic/vector memory writes, embeddings, rollback execution, plugin execution, channels, subagents, and remote/container/cloud execution remain disabled.

## Phase 2 Status Vocabulary

| Status | Meaning | Builder action |
|---|---|---|
| `phase_2_required` | Required for the Phase 2 scope. | Build in Phase 2 task order. |
| `specified_not_implemented` | The behaviour is documented, but code is not present yet. | Implement only through a named task and tests. |
| `implemented_verified` | Code and tests satisfy the acceptance criteria for the active change set. | Keep stable; regressions must fail CI. |
| `blocked_by_spec_gap` | Required behaviour is not detailed enough to implement safely. | Update docs before code. |

---

## Phase 2 Alignment Rules

### Phase Scheduling Rule
Phase 3+ features (Desktop UI, Web UI, Dashboard, mobile apps, plugins, graph/codemap, vector memory writes, external channel wiring, remote execution, subagents) must remain disabled. Phase 2 does not wire those features into active behaviour.

### Equal Primary Interface Rule
All implemented and enabled clients are equal-status primary interfaces through the same Agent Gateway. Phase 2 may expand the terminal/TUI first, but it must not become the privileged or canonical interface.

### Version Rule
Version remains `0.0.0` until all Phase 1 and Phase 2 patch increments (`0.0.1` through `0.0.99`) are consumed.

### CI Gate Rule
Every implementation PR must pass CI before merging. See `.github/workflows/ci.yml`.

---

## Phase 2 Task IDs

| Task ID | Title | Slice |
|---|---|---|
| RAIKER-1001 | Phase 2 status ledger and build-plan setup | Foundation |
| RAIKER-1002 | CI baseline and validation gate | Foundation |
| RAIKER-1101 | Task record contract and storage helpers | Task management |
| RAIKER-1102 | Background task manager service | Task management |
| RAIKER-1103 | Task lifecycle events and event indexing | Task management |
| RAIKER-1201 | Side-question child-turn contract | Side questions |
| RAIKER-1202 | Read-only side-question runtime path | Side questions |
| RAIKER-1301 | Interrupt, pause, cancel, and steer action contracts | Interrupt/steer |
| RAIKER-1302 | Safe-boundary interrupt handling | Interrupt/steer |
| RAIKER-1401 | Approval inbox query/list/resolve service | Approvals |
| RAIKER-1402 | Approval slash commands and action-bound approval resolution | Approvals |
| RAIKER-1501 | Checkpoint timeline listing | Checkpoints |
| RAIKER-1502 | Checkpoint restore/fork planning path, restore disabled until approved | Checkpoints |
| RAIKER-1601 | Event viewer query service | Event viewer |
| RAIKER-1602 | /events terminal command | Event viewer |
| RAIKER-1701 | /status and /tasks terminal commands | Terminal commands |
| RAIKER-1801 | stat_path and diff_files tools | File tools |
| RAIKER-1802 | write_file/edit_file/apply_patch proposal path with snapshot and approval | File tools |
| RAIKER-1901 | git status/diff/log wrappers with policy | Git wrappers |
| RAIKER-2001 | Local provider health-check abstraction | Model providers |
| RAIKER-2002 | llama.cpp server profile detection, disabled unless server is reachable | Model providers |
| RAIKER-2101 | Memory candidate listing and governed memory status view | Memory |
| RAIKER-2201 | Phase 2 integration validation and status update | Validation |

---

## Phase 2 Dependency Graph

```text
RAIKER-1001 Phase 2 plan
  -> RAIKER-1002 CI baseline
    -> RAIKER-1101 task contract and storage
      -> RAIKER-1102 task manager
        -> RAIKER-1103 task events and indexing
    -> RAIKER-1601 event query service
      -> RAIKER-1602 /events terminal command
    -> RAIKER-1701 /status and /tasks terminal commands
    -> RAIKER-1501 checkpoint timeline
    -> RAIKER-1401 approval inbox service
  -> RAIKER-1201 side-question contract
    -> RAIKER-1202 side-question runtime
  -> RAIKER-1301 interrupt/steer contracts
    -> RAIKER-1302 safe-boundary handling
  -> RAIKER-1402 approval terminal commands
  -> RAIKER-1502 checkpoint restore/fork
  -> RAIKER-1801 stat_path/diff_files
    -> RAIKER-1802 write/edit/patch with snapshots
  -> RAIKER-1901 git wrappers
  -> RAIKER-2001 local provider health check
    -> RAIKER-2002 llama.cpp server detection
  -> RAIKER-2101 memory candidate listing
    -> RAIKER-2201 integration validation
```

---

## Phase 2 Build Slices

| Slice | Task IDs | Output | Must not do |
|---|---|---|---|
| Foundation | RAIKER-1001 to RAIKER-1002 | CI, status ledger, build plan | No runtime behaviour change. |
| Task management | RAIKER-1101 to RAIKER-1103 | Task storage, manager, events | No tool execution. |
| Event viewer | RAIKER-1601 to RAIKER-1602 | Event query service and /events | No event log mutation. |
| Terminal inspection | RAIKER-1701, RAIKER-1501 | /status, /tasks, /checkpoints | No restore/fork execution. |
| Side questions | RAIKER-1201 to RAIKER-1202 | Child-turn contract and runtime | No active task mutation. |
| Interrupt/steer | RAIKER-1301 to RAIKER-1302 | Interrupt contracts and safe-boundary handling | No silent cancellation. |
| Approvals | RAIKER-1401 to RAIKER-1402 | Approval inbox service and commands | No auto-approval. |
| File tools | RAIKER-1801 to RAIKER-1802 | stat_path, diff_files, write/patch proposal | No unrestricted file mutation. |
| Git wrappers | RAIKER-1901 | Git status/diff/log with policy | No git push/merge without approval. |
| Model providers | RAIKER-2001 to RAIKER-2002 | Health check, llama.cpp server detection | No hosted model calls. |
| Memory | RAIKER-2101 | Memory candidate listing | No durable memory writes. |
| Validation | RAIKER-2201 | Integration tests and status update | No unverified completion claim. |

---

## Task Specifications

### RAIKER-1001: Phase 2 status ledger and build-plan setup

**Objective:** Create the Phase 2 build plan document and update all control docs for Phase 2 readiness.

**Canonical docs:** `docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/BUILD_ORDER.md`

**Files affected:** `docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md` (new), `docs/IMPLEMENTATION_STATUS.md`, `docs/BUILD_ORDER.md`, `docs/ACCEPTANCE_TESTS_BY_PHASE.md`

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** None

**Policy/security impact:** None

**Tests required:** None — documentation only

**Acceptance criteria:**
- Phase 2 build plan exists with all task IDs;
- `docs/IMPLEMENTATION_STATUS.md` has a Phase 2 status table;
- `docs/BUILD_ORDER.md` has a Phase 2 dependency graph;
- `docs/ACCEPTANCE_TESTS_BY_PHASE.md` covers the first Phase 2 slice.

**Must not do:** Do not claim any Phase 2 code is implemented.

### RAIKER-1002: CI baseline and validation gate

**Objective:** Add CI workflow so future Phase 2 PRs cannot silently regress.

**Canonical docs:** `docs/VERIFICATION_PLAN.md`, `.github/workflows/ci.yml`

**Files affected:** `.github/workflows/ci.yml` (new), `docs/VERIFICATION_PLAN.md`

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** None

**Policy/security impact:** CI must not require secrets or network access.

**Tests required:** None — infrastructure only

**Acceptance criteria:**
- CI runs on `pull_request` and `push` to `main`;
- CI runs `pytest`, `ruff`, `mypy` with Python 3.11;
- `docs/VERIFICATION_PLAN.md` references CI and requires CI pass for PRs.

**Must not do:** Do not add secrets, hosted model tests, or complex matrix builds.

### RAIKER-1101: Task record contract and storage helpers

**Objective:** Add task dataclass/contract and SQLite store helpers for task CRUD.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`

**Files affected:** `raiker/contracts/models.py`, `raiker/storage/sqlite.py`, `raiker/tasks/` (new directory)

**Contracts affected:** Task contract — used by `raiker/contracts/models.py`

**Events emitted:** None in this task — events are emitted by the manager

**Storage affected:** `tasks` table (already exists in schema), `insert_task`, `load_task`, `list_tasks`, `update_task_status`, `update_task_progress` helpers

**Policy/security impact:** None — task records are read/write by the runtime in the local `.raiker/` database

**Tests required:** Task storage helper tests

**Acceptance criteria:**
- `Task` dataclass has `task_id`, `session_id`, `parent_turn_id`, `title`, `objective`, `status`, `current_step`, `progress_percent`, `created_at`, `updated_at`, `completed_at`;
- SQLite helpers exist for `insert_task`, `load_task`, `list_tasks`, `update_task_status`, `update_task_progress`;
- Tasks table matches the schema in `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`;
- Tests prove deterministic CRUD behaviour.

**Must not do:** Do not wire task events or manager lifecycle yet.

### RAIKER-1102: Background task manager service

**Objective:** Implement the task manager service that creates, updates, completes, fails, and cancels tasks.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`

**Files affected:** `raiker/tasks/manager.py`, `raiker/tasks/__init__.py`

**Contracts affected:** TaskRecord (used internally)

**Events emitted:** `task_created`, `task_progress`, `task_cancelled`, `task_completed`, `task_failed`

**Storage affected:** `tasks` table

**Policy/security impact:** Tasks cannot execute tools — they represent work metadata only.

**Tests required:** Task manager lifecycle tests

**Acceptance criteria:**
- `create_task` creates a task row and emits `task_created`;
- `update_progress` updates progress and emits `task_progress`;
- `complete_task` completes and emits `task_completed`;
- `fail_task` fails and emits `task_failed`;
- `cancel_task` cancels and emits `task_cancelled`;
- `list_tasks` returns tasks in deterministic order.

**Must not do:** Do not add background execution, subagent spawning, or auto-retry.

### RAIKER-1103: Task lifecycle events and event indexing

**Objective:** Ensure task lifecycle events are emitted and indexed consistently.

**Canonical docs:** `docs/EVENT_CATALOG.md`

**Files affected:** `raiker/events/writer.py`, `raiker/events/types.py`

**Contracts affected:** AgentEvent payloads for task events

**Events emitted:** `task_created`, `task_started`, `task_progress`, `task_cancelled`, `task_completed`, `task_failed`

**Storage affected:** `events_index` table gets task_id indexed

**Policy/security impact:** Events must preserve client metadata where applicable.

**Tests required:** Task event emission and indexing tests

**Acceptance criteria:**
- Task events include `task_id` in the payload;
- Task events are appended to JSONL and indexed in SQLite;
- Event payload specs are added to `docs/EVENT_CATALOG.md`.

**Must not do:** Do not add task events without verifying `docs/EVENT_CATALOG.md` payload specs first.

### RAIKER-1201: Side-question child-turn contract

**Objective:** Define the side-question contract for child turns that read but do not mutate active tasks.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`

**Files affected:** `raiker/contracts/models.py`, `docs/EVENT_CATALOG.md`

**Contracts affected:** SideTurn contract

**Events emitted:** Reserved `side_question_received`, `side_question_answered`

**Storage affected:** Turns table with `turn_type`

**Policy/security impact:** Side questions must not mutate parent task state.

**Tests required:** Side-question contract validation tests

**Acceptance criteria:**
- `SideTurn` dataclass has `side_turn_id`, `parent_task_id`, `mode`, `question`, `allowed_context`, `may_mutate_parent`;
- Modes match `docs/RUNTIME_ORCHESTRATION_SPEC.md`.

**Must not do:** Do not wire side questions into active runtime or terminal yet.

### RAIKER-1202: Read-only side-question runtime path

**Objective:** Wire a read-only side-question path that answers from event log without stopping active work.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`

**Files affected:** `raiker/runtime/orchestrator.py`

**Contracts affected:** SideTurn, PromptEnvelope

**Events emitted:** `side_question_received`, `side_question_answered`

**Storage affected:** Turns table

**Policy/security impact:** Side questions must not pause the active task.

**Tests required:** Side-question runtime tests

**Acceptance criteria:**
- Side question creates a child turn;
- Active task state is readable but not mutable;
- Side question events are appended and indexed.

**Must not do:** Do not add terminal/Q syntax for side questions in this task.

### RAIKER-1301: Interrupt, pause, cancel, and steer action contracts

**Objective:** Define action contracts for task controls.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`

**Files affected:** `raiker/contracts/models.py`, `docs/API_AND_CONTRACT_SCHEMAS.md`

**Contracts affected:** UIActionEnvelope action types

**Events emitted:** Reserved

**Storage affected:** None

**Policy/security impact:** Interrupt/steer must be action-bound and must not bypass policy.

**Tests required:** Interrupt contract validation tests

**Acceptance criteria:**
- `UIActionEnvelope.action_type` includes `pause_task`, `cancel_task`, `steer_task`, `resume_task`;
- Payload includes `task_id`, `reason`, and (for steer) `new_instruction`.

**Must not do:** Do not wire interrupt handling into the runtime yet.

### RAIKER-1302: Safe-boundary interrupt handling

**Objective:** Implement safe-boundary detection and interrupt routing in the runtime.

**Canonical docs:** `docs/RUNTIME_ORCHESTRATION_SPEC.md`

**Files affected:** `raiker/runtime/orchestrator.py`, `raiker/runtime/state_machine.py`

**Contracts affected:** None — runtime internal

**Events emitted:** `interrupt_received`, `safe_boundary_reached`, `task_cancelled`, `task_steered`

**Storage affected:** Tasks table status updates

**Policy/security impact:** Interrupt must not bypass approval or execute tools directly.

**Tests required:** Interrupt runtime tests

**Acceptance criteria:**
- Interrupt pauses after safe boundary;
- Cancel terminates task and logs cancellation;
- Steer updates plan after classification and optional approval.

**Must not do:** Do not add terminal interrupt keys yet.

### RAIKER-1401: Approval inbox query/list/resolve service

**Objective:** Add a service to query, list, and resolve pending approval requests.

**Canonical docs:** `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md`

**Files affected:** `raiker/approvals/` (new directory)

**Contracts affected:** ApprovalRequest

**Events emitted:** None — resolves existing approvals

**Storage affected:** `approvals` table queries

**Policy/security impact:** Approvals must remain action-bound.

**Tests required:** Approval inbox service tests

**Acceptance criteria:**
- `list_pending_approvals` returns unresolved approvals;
- `resolve_approval(approval_id, decision)` updates approval status;
- Approval resolution validates action binding.

**Must not do:** Do not add terminal approval commands yet.

### RAIKER-1402: Approval slash commands and action-bound approval resolution

**Objective:** Add `/approvals` and approve/deny terminal commands through the gateway.

**Canonical docs:** `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`

**Files affected:** `raiker/cli/commands.py`

**Contracts affected:** UIActionEnvelope

**Events emitted:** `ui_action_submitted`, `approval_received`, `approval_denied`

**Storage affected:** Approvals table

**Policy/security impact:** Approval must bind to exact `action_id`.

**Tests required:** Terminal approval command tests

**Acceptance criteria:**
- `/approvals` lists pending approvals;
- Approve/deny actions resolve the correct approval;
- Approval events are logged.

**Must not do:** Do not add auto-approval or session-scoped approval.

### RAIKER-1501: Checkpoint timeline listing

**Objective:** Add a service to list checkpoint metadata for a session.

**Canonical docs:** `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`

**Files affected:** `raiker/checkpoints/service.py`

**Contracts affected:** CheckpointManifest

**Events emitted:** None — read-only inspection

**Storage affected:** `checkpoints` table

**Policy/security impact:** None — read-only

**Tests required:** Checkpoint listing tests

**Acceptance criteria:**
- `list_checkpoints(session_id, limit=50)` returns checkpoint metadata;
- `get_checkpoint(checkpoint_id)` returns a single checkpoint manifest path;
- Results are in deterministic order.

**Must not do:** Do not add restore or fork execution.

### RAIKER-1502: Checkpoint restore/fork planning path

**Objective:** Add checkpoint restore and fork action contracts with approval requirement.

**Canonical docs:** `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md`

**Files affected:** `raiker/contracts/models.py`, `raiker/checkpoints/service.py`

**Contracts affected:** UIActionEnvelope with `checkpoint_restore` and `checkpoint_fork` action types

**Events emitted:** `checkpoint_restore_requested`, `session_forked`

**Storage affected:** Sessions table `forked_from_checkpoint_id`

**Policy/security impact:** Restore/fork requires approval when files may change.

**Tests required:** Checkpoint restore/fork tests

**Acceptance criteria:**
- Restore request creates an approval requirement;
- Fork creates a new session with `forked_from_checkpoint_id`.

**Must not do:** Do not execute file restore without approval.

### RAIKER-1601: Event viewer query service

**Objective:** Add a service to query events from the events_index table.

**Canonical docs:** `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`

**Files affected:** `raiker/events/query.py` (new)

**Contracts affected:** None — reads events_index

**Events emitted:** None — read-only

**Storage affected:** `events_index` table (read-only queries)

**Policy/security impact:** Must never mutate JSONL logs. Must not leak raw secrets.

**Tests required:** Event query tests

**Acceptance criteria:**
- `list_events(session_id, turn_id, task_id, event_type, limit)` returns index rows;
- `get_event_index(event_id)` returns a single event index row;
- `read_event_payload(event_id)` reads the JSONL payload if practical;
- Safe fallback if payload cannot be read.

**Must not do:** Do not mutate event logs.

### RAIKER-1602: /events terminal command

**Objective:** Add `/events` terminal command that lists recent events.

**Canonical docs:** `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`

**Files affected:** `raiker/cli/commands.py`

**Contracts affected:** UIActionEnvelope

**Events emitted:** `ui_action_submitted`

**Storage affected:** Events read

**Policy/security impact:** Read-only — must not execute tools.

**Tests required:** Terminal event command tests

**Acceptance criteria:**
- `/events` lists recent events in stable order;
- Events show event type, actor, timestamp;
- Command does not execute tools.

**Must not do:** Do not add event filtering by payload content.

### RAIKER-1701: /status and /tasks terminal commands

**Objective:** Add `/status` and `/tasks` terminal commands.

**Canonical docs:** `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`

**Files affected:** `raiker/cli/commands.py`

**Contracts affected:** UIActionEnvelope

**Events emitted:** `ui_action_submitted`

**Storage affected:** Tasks read

**Policy/security impact:** Read-only — must not execute tools.

**Tests required:** Terminal status/task command tests

**Acceptance criteria:**
- `/status` shows session ID, model profile, event path, checkpoint path, pending approvals count;
- `/tasks` lists tasks with ID, title, status, progress;
- Commands do not execute tools.

**Must not do:** Do not add task mutation through these commands.

### RAIKER-1801: stat_path and diff_files tools

**Objective:** Implement safe `stat_path` and `diff_files` tools through the broker.

**Canonical docs:** `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/SECURITY_AND_POLICY.md`

**Files affected:** `raiker/tools/filesystem.py`, `raiker/tools/__init__.py`

**Contracts affected:** ToolAction

**Events emitted:** `action_proposed`, `policy_decision`, `tool_started`, `tool_completed`

**Storage affected:** Tool actions table

**Policy/security impact:** Must enforce workspace scoping and path safety.

**Tests required:** stat_path and diff_files tests

**Acceptance criteria:**
- `stat_path` returns metadata inside workspace;
- `diff_files` returns diff between two files;
- Outside-workspace paths are denied.

**Must not do:** Do not add write tools in the same task.

### RAIKER-1802: write_file/edit_file/apply_patch proposal path with snapshot and approval

**Objective:** Implement approval-gated file mutation tools with before-snapshot.

**Canonical docs:** `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/SECURITY_AND_POLICY.md`, `docs/CHECKPOINTING_AND_REWIND_SPEC.md`

**Files affected:** `raiker/tools/filesystem.py`, `raiker/checkpoints/service.py`

**Contracts affected:** ToolAction, ApprovalRequest

**Events emitted:** `action_proposed`, `policy_decision`, `approval_requested`, `tool_started`, `tool_completed`, `file_snapshot_created`

**Storage affected:** Tool actions, approvals, file_snapshots tables

**Policy/security impact:** File mutation must require approval. Before-snapshot must be created.

**Tests required:** File mutation approval and snapshot tests

**Acceptance criteria:**
- `write_file` proposal requires approval;
- `edit_file` proposal creates a before-snapshot;
- `apply_patch` proposal creates a before-snapshot;
- Without explicit approval, the action is not executed.

**Must not do:** Do not allow unrestricted file mutation.

### RAIKER-1901: git status/diff/log wrappers with policy

**Objective:** Add git status/diff/log tool wrappers routed through the broker.

**Canonical docs:** `docs/TOOLS_AND_PERMISSIONS_SPEC.md`

**Files affected:** `raiker/tools/git.py` (new)

**Contracts affected:** ToolAction

**Events emitted:** `action_proposed`, `policy_decision`, `tool_started`, `tool_completed`

**Storage affected:** Tool actions table

**Policy/security impact:** Git commands must be policy-reviewed.

**Tests required:** Git wrapper tests

**Acceptance criteria:**
- `git_status` runs inside workspace;
- `git_diff` runs inside workspace;
- `git_log` runs inside workspace;
- Outside-workspace paths are denied.

**Must not do:** Do not add git push/merge without explicit approval.

### RAIKER-2001: Local provider health-check abstraction

**Objective:** Add a health-check abstraction for local model providers.

**Canonical docs:** `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`

**Files affected:** `raiker/models/health.py` (new)

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** None

**Policy/security impact:** Health check must not send prompts.

**Tests required:** Provider health check tests

**Acceptance criteria:**
- Health check interface supports `check(profile) -> bool`;
- Mock provider returns healthy;
- Unknown provider returns unhealthy.

**Must not do:** Do not add network calls in health checks.

### RAIKER-2002: llama.cpp server profile detection

**Objective:** Add profile detection for the llama.cpp server (the native default backend), disabled unless the server is reachable.

**Canonical docs:** `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json`

**Files affected:** `raiker/models/health.py`

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** None

**Policy/security impact:** Must not send prompts; health probe hits only the local `/health` endpoint.

**Tests required:** llama.cpp server detection tests (stub HTTP)

**Acceptance criteria:**
- The llama.cpp server profile can be detected via the `/health` check;
- If the server is not reachable, Raiker falls back to the mock provider;
- Detection does not leak prompts.

**Must not do:** Do not auto-start a server; do not send prompts during detection.

### RAIKER-2101: Memory candidate listing and governed memory status view

**Objective:** Add a read-only view of memory candidates and memory governance status.

**Canonical docs:** `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/MEMORY_GOVERNANCE_RULES.md`

**Files affected:** `raiker/memory/` (new directory)

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** Memory_candidates table (read-only)

**Policy/security impact:** Must not write durable memory.

**Tests required:** Memory candidate listing tests

**Acceptance criteria:**
- `list_candidates(session_id, limit)` returns candidate metadata;
- `count_pending_candidates()` returns count of deferred candidates;
- Interface does not write durable memory.

**Must not do:** Do not add durable memory write path.

### RAIKER-2201: Phase 2 integration validation and status update

**Objective:** Run full Phase 2 integration validation and update status ledger.

**Canonical docs:** `docs/VERIFICATION_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md`

**Files affected:** `docs/IMPLEMENTATION_STATUS.md`

**Contracts affected:** None

**Events emitted:** None

**Storage affected:** None

**Policy/security impact:** None

**Tests required:** Integration smoke tests

**Acceptance criteria:**
- All Phase 2 implemented tasks pass validation;
- Status ledger reflects `implemented_verified` for implemented tasks;
- Phase 1 baseline remains intact.

**Must not do:** Do not mark Phase 2 as fully complete.

---

## Must Not Build In Phase 2

Phase 2 must not actively wire:

- Desktop UI;
- Web UI;
- Dashboard;
- Apple/Android mobile runtime;
- external chat/email/channel transports;
- plugin execution;
- graph/codemap runtime indexing;
- vector/semantic memory writes;
- subagent teams;
- autonomous multi-agent orchestration;
- remote/container execution;
- hosted model calls;
- unrestricted shell execution;
- automatic write/edit/patch execution without approval.

Phase 2 may include disabled/listable profiles, schemas, tables, and extension boundaries.

---

## Builder Working Rules

1. Choose exactly one task ID from this plan.
2. Read the canonical implementation docs for that task.
3. Preserve equal-interface contracts.
4. Implement the smallest production-quality change that satisfies the task.
5. Add or update tests.
6. Keep version at `0.0.0`.
7. Report temporary bootstrap limitations honestly.