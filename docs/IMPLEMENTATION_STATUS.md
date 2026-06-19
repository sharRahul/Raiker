# Implementation Status

This document is the implementation control ledger for Raiker. It converts the existing phase blueprint into a builder-proof status view so a local or cloud coding agent can tell what is specified, what is implemented, what is intentionally disabled, and what must not be built yet.

A feature marked as specified is not automatically implemented. A feature marked as phase-scheduled is not permission to invent behaviour in code. A feature may only be marked `implemented_verified` when the implementation maps to documented task IDs, required tests exist, and validation has passed for the current change set.

---

## Status Vocabulary

| Status | Meaning | Builder action |
|---|---|---|
| `specified_not_implemented` | The behaviour is documented, but code is not present yet. | Implement only through a named task and tests. |
| `phase_1_required` | Required for the Phase 1 MVP. | Build in Phase 1 task order. |
| `phase_scheduled_disabled` | Contract/profile/storage boundary may exist, but runtime wiring is disabled until a later phase. | Preserve contracts and registries; do not activate. |
| `implemented_unverified` | Code exists, but current acceptance validation is missing, incomplete, or not yet recorded for the active change set. | Run/repair tests before marking complete. |
| `implemented_verified` | Code and tests satisfy the acceptance criteria for the active change set. | Keep stable; regressions must fail CI. |
| `blocked_by_spec_gap` | Required behaviour is not detailed enough to implement safely. | Update docs before code. |
| `out_of_scope` | Deliberately not a Raiker goal. | Do not implement unless the non-goal is changed through ADR. |

---

## Known Documentation/Code Gaps (Review 2026-06-19)

A repository review (`docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md`) verified the following gaps
where documentation runs ahead of code. These are recorded here so the ledger stays trustworthy;
none of them change the validator-required Phase 1/2/3 markers below.

| Area | Documented as | Verified code reality | Honest status |
|---|---|---|---|
| Hooks | Full lifecycle spec (`docs/HOOKS_SPEC.md`) | No `raiker/hooks/` module exists at all | `specified_not_implemented` |
| Local model providers | Ollama/llama.cpp/LM Studio profiles | `raiker/models/router.py` raises `provider_not_wired_in_phase_1`; only `mock` runs | `specified_not_implemented` (mock only) |
| Local provider health-check | Phase 2 `implemented_verified` | True — but it only **detects** a binary; it does not run inference | accurate, scope-clarified |
| Verifier / verification step | "verify results" loop phase | `raiker/runtime/verifier.py` is a pass-through stub | `stub` |
| Context gathering | repository understanding feeding the model | orchestrator records fixed `sources=["current_prompt"]` | `stub` |
| Code review workflow | implied by "coding platform" | no review module present | `specified_not_implemented` |

These do not activate or disable any runtime capability; they correct the *claimed* maturity only.
Close them via named phase tasks with tests before marking any `implemented_verified`.

---

## Phase 1 MVP Status

Post-restore audit note: the long-form Phase 1 build plan is restored and remains the detailed scope source for implemented/verified Phase 1 behavior. Later Slice G/H lifecycle metadata does not change Phase 1 runtime scope.

PR #6 added the initial Phase 1 MVP runtime core.
PR #8 reconciled documentation and version baseline.
PR #11 removed generated Python bytecode artifacts and strengthened .gitignore.

**Validation status (2026-06-17):** The full validation set was run on the `phase-1-runtime-core-validation-baseline` branch. All validation commands pass, event sequences are verified, and security invariants hold. The Phase 1 final acceptance criteria are met. See the validation PR for exact command outputs and artifact inspection results.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---:|---:|---|---|
| Python package scaffold | `phase_1_required` | `implemented_verified` | `docs/PHASE_1_MVP_BUILD_PLAN.md`, `docs/ARCHITECTURE.md` | import/package smoke |
| Global `raiker` command | `phase_1_required` | `implemented_verified` | `README.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_scaffold.py`, terminal smoke |
| Equal-interface metadata | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/FEATURE_COVERAGE_MATRIX.md` | `tests/test_equal_interface_invariant.py` or equivalent invariant coverage |
| PromptEnvelope contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | `tests/test_contracts.py` |
| AgentEvent contract | `phase_1_required` | `implemented_verified` | `docs/CONTRACTS.md`, `docs/EVENT_CATALOG.md` | `tests/test_event_log.py` |
| SQLite bootstrap | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_storage_sqlite.py` |
| Append-only JSONL event writer | `phase_1_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_event_log.py` |
| Static policy engine | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_policy_engine.py` |
| Tool broker skeleton | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | `tests/test_tool_broker.py` |
| `read_file` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | path safety tests |
| `list_directory` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stable sorted output tests |
| `glob` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | bounded result tests |
| `grep` | `phase_1_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | text-only and bounded output tests |
| Local action proposal | `phase_1_required` | `implemented_verified` | `docs/SECURITY_AND_POLICY.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval-required tests |
| Mock model provider | `phase_1_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | deterministic output tests |
| Model profile registry | `phase_1_required` | `implemented_verified` | `config/model-profiles.json`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | registry load tests |
| Channel connector registry | `phase_1_required` | `implemented_verified` | `config/channel-connectors.json`, `docs/CHANNELS_SPEC.md` | disabled/listable tests |
| Runtime state machine | `phase_1_required` | `implemented_verified` | `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | transition tests |
| Agent gateway | `phase_1_required` | `implemented_verified` | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` | gateway validation tests |
| Session manager | `phase_1_required` | `implemented_verified` | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | create/load tests |
| Checkpoint stub | `phase_1_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | write/read stub tests |
| Terminal client MVP | `phase_1_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` | terminal smoke tests |

---

## Phase-Scheduled Disabled Capabilities

The following capabilities may have config profiles, schemas, or storage boundaries in Phase 1, but must not be wired into active behaviour until their phase task explicitly allows it.

| Capability | First active phase | Required Phase 1 behaviour |
|---|---|---:|---|
| Desktop UI | Phase 3 | Preserve equal-interface contracts only. |
| Web UI and dashboard | Phase 3 | Preserve action parity and storage metrics contracts only. |
| Apple mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Android mobile app | Phase 3 | Connector profile may be disabled/listable; no active transport. |
| Plugin execution | Phase 3 | Validate/describe manifest shape only; no plugin code execution. |
| Semantic/vector memory writes | Phase 3 | Preserve storage metadata boundaries; no active embedding writes. |
| Graph/codemap runtime indexing | Phase 3 | Preserve schema/spec only; no runtime indexing. |
| External channels | Phase 4 | Profiles disabled unless explicitly paired in later phase. |
| Subagents and multi-agent teams | Phase 4 | Contracts/spec only; no spawning. |
| Remote/container execution | Phase 4 | Execution profiles disabled; no command routing. |
| Hosted model billing controls | Phase 5 | Hosted providers disabled until policy and budgets exist. |

---

## Phase 2 Rich Local Workspace Status

Post-restore audit note: the long-form Phase 2 build plan is restored and remains the detailed scope source for implemented/verified Phase 2 behavior. Later Slice G/H lifecycle metadata depends on Phase 2 concepts but does not expand Phase 2 runtime authority.

PR #12 established the Phase 2 build plan, CI baseline, task manager, event viewer, checkpoint timeline, and inspection commands. This table tracks all Phase 2 capabilities.

| Area | Required status | Current repository status | Canonical docs | Required tests |
|---|---|---|---|---|
| Phase 2 build plan and status ledger | `phase_2_required` | `implemented_verified` | `docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md` | doc consistency |
| CI baseline | `phase_2_required` | `implemented_verified` | `.github/workflows/ci.yml`, `docs/VERIFICATION_PLAN.md` | workflow syntax |
| Task record contract and storage helpers | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Background task manager service | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | `tests/test_phase_2_task_manager.py` |
| Task lifecycle events and event indexing | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | task event tests |
| Event viewer query service | `phase_2_required` | `implemented_verified` | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_event_viewer.py` |
| Checkpoint timeline listing | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | `tests/test_phase_2_checkpoint_timeline.py` |
| /status terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /tasks terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /events terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| /checkpoints terminal command | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | `tests/test_phase_2_terminal_commands.py` |
| Side-question child-turn contract | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` | side-question contract tests |
| Read-only side-question runtime | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | side-question runtime tests |
| Interrupt/steer action contracts | `phase_2_required` | `implemented_verified` | `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt contract tests |
| Safe-boundary interrupt handling | `phase_2_required` | `implemented_verified` | `docs/RUNTIME_ORCHESTRATION_SPEC.md` | interrupt runtime tests |
| Approval inbox service | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | approval inbox tests |
| Approval terminal commands | `phase_2_required` | `implemented_verified` | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | terminal approval tests |
| Checkpoint restore/fork planning | `phase_2_required` | `implemented_verified` | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | restore/fork tests |
| stat_path and diff_files tools | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | stat/diff tests |
| write_file/edit_file/apply_patch | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | file mutation approval tests |
| git status/diff/log wrappers | `phase_2_required` | `implemented_verified` | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | git wrapper tests |
| Local provider health-check | `phase_2_required` | `implemented_verified` | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | health check tests |
| Memory candidate listing | `phase_2_required` | `implemented_verified` | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` | memory candidate tests |
| Phase 2 integration validation | `phase_2_required` | `implemented_verified` | `docs/VERIFICATION_PLAN.md` | integration smoke tests |

---

## Phase 3 and Phase 4 Planning Status

Detailed Phase 3 and Phase 4 plans are now recorded in `docs/PHASE_3_BUILD_PLAN.md` and `docs/PHASE_4_BUILD_PLAN.md`. Safe foundations now include disabled/listable capability gates, plugin manifest validation without code execution, graph/codemap planning schemas, semantic-memory disabled status reporting, remote/container execution profiles, subagent planning, external-channel activation status, and terminal inspection commands. Tests prove these foundations are discoverable and remain non-executable until policy, storage, approval, and lifecycle controls are complete.

| Phase | Implemented foundation | Runtime state | Evidence |
|---|---|---|---|
| Phase 3 | Capability gates, `/capabilities`, plugin manifest validation, graph/codemap planning, semantic-memory status, `/semantic-memory` | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |
| Phase 4 | Capability gates, `/execution-profiles`, remote/container execution planning, subagent planning, external-channel activation status | Disabled/non-executing | `tests/test_phase_3_phase_4_implementation.py` |

## Validation Evidence (2026-06-18)

**Local validation** was performed on `main` (no fixes needed — all checks passed):

| Aspect | Detail |
|---|---|
| **Date/time** | 2026-06-18 07:51 UTC |
| **OS** | Windows (PowerShell) |
| **Python version** | 3.13.5 |
| **Virtual environment** | `.venv` |
| **Commands run** | `ruff check .`, `mypy raiker apps tests`, `pytest`, `scripts/validate_phase_status.py`, `raiker --help`, `raiker --prompt "Hello Raiker"`, comprehensive smoke script |
| **Test result** | 93/93 passed |
| **Ruff** | All checks passed |
| **Mypy** | No issues (87 files) |
| **Phase status validation** | Passed |
| **Fixes made** | None — all checks passed on first run |
| **Phase 3 runtime disabled** | plugin_execution, graph_codemap_indexing, semantic_memory_writes all confirmed disabled |
| **Phase 4 runtime disabled** | external_channels, subagents, multi_agent_teams, remote_execution, container_execution all confirmed disabled |
| **Assessments** | Phase 1 and Phase 2 remain `implemented_verified`. Phase 3/4 safe foundations are correct, discoverable, tested, and non-executing. No runtime features were activated.|

## Status Update Rule

A builder may change a row to `implemented_verified` only when all of these are true:

1. The implementation maps to a Phase 1 task ID or later phase task ID.
2. The implementation follows the canonical docs listed in this file.
3. Required tests exist and pass for the active change set.
4. Validation output is included in the PR.
5. Event names, storage tables, contracts, and policy decisions match the specs.
6. The equal primary-interface invariant remains intact.

If any of these are false, the correct status is `implemented_unverified` or `blocked_by_spec_gap`.

---

## Documentation Gap Handling

When a builder finds conflicting or incomplete documentation, it must stop the implementation task and create a documentation update first. The documentation update must identify:

- affected feature;
- build phase;
- conflicting files;
- chosen canonical behaviour;
- contracts affected;
- storage affected;
- events emitted;
- policy/security impact;
- tests required.

Undocumented behaviour is not approved Raiker behaviour.

## Phase 3 rollout slice A status — 2026-06-18

Phase 3 is **not complete**. The first rollout slice is `implemented_verified` after adding read-only workspace contract parity and plugin policy/registration planning.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3101 desktop/web/dashboard contract parity foundation | `implemented_verified` | `raiker/workspace/inspection.py`, `tests/test_phase_3_workspace_inspection.py`, `tests/test_phase_3_equal_workspace_clients.py` |
| RAIKER-3201 plugin execution policy boundary without execution | `implemented_verified` | `raiker/plugins/policy.py`, `raiker/plugins/registry.py`, `tests/test_phase_3_plugin_policy.py` |
| Phase 3 capability state model | `implemented_verified` | `raiker/phase_gates.py`, `tests/test_phase_3_capability_states.py` |
| Read-only CLI inspection commands | `implemented_verified` | `/workspace`, `/clients`, `/plugins`, `/plugin-plan <manifest_path>`, `tests/test_phase_3_terminal_commands.py` |

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

## Temporary CI Pause — GitHub Actions quota exhausted

- GitHub Actions are temporarily paused or unavailable due run-limit/quota exhaustion.
- Local validation is mandatory while Actions are paused; use `docs/LOCAL_VALIDATION_GATE.md` as the source of truth for required commands and evidence.
- Full CI must be re-enabled before future release tagging or when quota becomes available.
- This is not a waiver of validation requirements.

## Phase 3 rollout slice B status — 2026-06-18

Phase 3 is **not complete**. Slice B adds the RAIKER-3501 read-only rich workspace view/API foundation while preserving all disabled runtime gates.

| Slice | Status | Evidence |
|---|---:|---|
| RAIKER-3501 read-only rich workspace view/API foundation | `implemented_verified` after local validation evidence is recorded | `raiker/workspace/views.py`, `tests/test_phase_3_workspace_views.py` |
| `/workspace-view` read-only CLI summary | `implemented_verified` after local validation evidence is recorded | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

The view layer consumes the shared workspace inspection contract and renders deterministic text, JSON-safe, dashboard, client capability, and plugin plan summaries. It does not execute tools, create approvals, call models, write memory, execute plugin code, activate channels, start remote/container execution, or expose secret-like values.

Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain non-executing.

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

| `/workspace-view` safe terminal snapshot command | `implemented_verified` | `raiker/cli/commands.py`, `tests/test_phase_3_workspace_views.py` |

## 2026-06-18 Phase 3 Slice E — approval-preview UX/contracts

Status: `implemented_verified` locally for the Slice E contract surface only; full Phase 3 is not complete.

Slice E adds preview-only approval contracts for future graph/codemap indexing and semantic memory writes. The implementation exposes deterministic preview rendering, redaction of secret-like memory text, CLI preview commands, and workspace inspection summary fields.

Safety status:

- Graph/codemap runtime indexing remains disabled.
- Semantic/vector memory writes remain disabled.
- Previews are not approvals to execute; approving for later does not write memory or run indexing.
- No embeddings, vectors, background indexers, watchers, daemons, plugins, channels, remote execution, or container execution are activated.
- GitHub Actions remain paused due quota exhaustion; local validation evidence is mandatory and full CI must be re-enabled later when quota is available.

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

## Phase 3 Slice H lifecycle retention status

Slice H is `implemented_verified` locally for metadata-only retention policies, cleanup previews, approval-handoff planning, read-only summaries, and SQLite metadata tables. Full Phase 3 is still incomplete. Keep detailed contract and safety requirements in `docs/PHASE_3_SLICE_H_LIFECYCLE_RETENTION_SPEC.md`; this document records only the status summary. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, approval relay, or remote/container/cloud execution.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Phase 3 Slice J — Graph/Codemap Indexing Readiness Metadata

Slice J is `implemented_verified` for metadata-only readiness surfaces: deterministic contract, registry create/list/get/summary, read-only CLI, optional SQLite metadata table, workspace inspection/view fields, docs, and tests.

Slice J did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked. Graph/codemap runtime indexing, graph writes, workers, schedulers, file watchers, daemons, and runtime jobs remain disabled.


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Slice K did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice L — Approval Preview Persistence Readiness — Metadata Only

Slice L is implemented as metadata-only readiness for future durable approval preview persistence. It adds `/approval-readiness [--summary|--json]`, deterministic `appr_` readiness contracts, optional `phase3_approval_preview_persistence_readiness` SQLite metadata storage, and workspace inspection/view fields. Approval execution, approval relay runtime, durable approval queues, approval workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice L did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Phase 3 Slice M — Storage Cleanup Execution Readiness — Metadata Only

Implemented deterministic metadata-only readiness contracts, registry, optional SQLite metadata table, CLI surface, and workspace summaries for storage cleanup execution readiness. Cleanup execution, deletion, purge, tombstone, rollback, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice M did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice O — External Channels/Notifications Readiness — Metadata Only

Implemented metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/channel-readiness` CLI output, and workspace summary fields for future external channels and notifications. No external channels, notifications, push notifications, share links, webhook dispatch, relay runtime, hosted channels/routines, workers, schedulers, watchers, daemons, or runtime execution are enabled. Slice O did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Added metadata-only readiness contracts, registry operations, optional SQLite persistence, read-only `/remote-readiness` CLI output, and workspace summary fields for future remote/container/cloud execution. No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, or runtime execution are enabled.

## Phase 3 Completion Status

All Phase 3 slices A through P are implemented, tested, and documented. Phase 3 is now marked `implemented_verified` per the completion audit in `docs/PHASE_3_COMPLETION_AUDIT.md`. All runtime execution remains disabled. Phase 4 remains blocked.
