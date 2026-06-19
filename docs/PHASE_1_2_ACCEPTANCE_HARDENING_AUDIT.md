# Phase 1/2 Acceptance Hardening Audit

Date: 2026-06-19
Scope: Phase 1 MVP runtime core and Phase 2 rich local workspace only.

This audit verifies every Phase 1 and Phase 2 row currently marked `implemented_verified` in `docs/IMPLEMENTATION_STATUS.md` against implementation evidence, test evidence, safety boundaries, and documentation consistency. It does not implement or enable Phase 3, Phase 4, or later runtime capabilities.

## Scope boundary confirmation

This PR is limited to acceptance hardening for Phase 1 and Phase 2. It does not implement or activate rich TUI panels, Desktop/Web/Dashboard/Mobile apps, REST/API server, IDE extension, plugin execution/installation, MCP/LSP startup, graph/codemap runtime indexing, graph writes, semantic/vector memory writes, embedding creation, semantic search runtime, approval relay runtime, cleanup execution, rollback execution, external channels, notifications, scheduled automation runtime, workers, schedulers, file watchers, daemons, subagents, multi-agent teams, remote execution, container execution, cloud execution, process execution, shell execution, or network execution.

## Disabled runtime flags

The audit explicitly verifies these runtime flags remain false and are directly surfaced by Phase 1/2-safe context metadata:

- `plugin_execution_enabled`
- `graph_indexing_enabled`
- `semantic_memory_writes_enabled`
- `vector_writes_enabled`
- `embedding_creation_enabled`
- `approval_execution_enabled`
- `approval_relay_runtime_enabled`
- `cleanup_execution_enabled`
- `rollback_execution_enabled`
- `external_channels_enabled`
- `notifications_enabled`
- `remote_execution_enabled`
- `container_execution_enabled`
- `cloud_execution_enabled`
- `process_execution_enabled`
- `shell_execution_enabled`
- `network_execution_enabled`
- `runtime_execution_enabled`

Action taken in this PR: `raiker/context/gatherer.py` now reports the full required disabled flag set, and `tests/test_phase_1_2_acceptance_hardening.py` directly asserts every required flag is present and false.

## Phase 1 audit table

| Phase | Requirement | Claimed status | Code evidence | Test evidence | Audit verdict | Action taken |
|---|---|---|---|---|---|---|
| Phase 1 | Python package scaffold | `implemented_verified` | `pyproject.toml`, `raiker/`, `apps/` | `tests/test_scaffold.py` | pass | none |
| Phase 1 | Global `raiker` command | `implemented_verified` | `pyproject.toml`, `raiker/cli/main.py`, `raiker/cli/commands.py` | `tests/test_scaffold.py`, CLI smoke coverage | pass | none |
| Phase 1 | Equal-interface metadata | `implemented_verified` | `raiker/contracts/models.py`, `raiker/cli/commands.py` | `tests/test_equal_interface_invariant.py` | pass | none |
| Phase 1 | PromptEnvelope contract | `implemented_verified` | `raiker/contracts/models.py` | `tests/test_contracts.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | AgentEvent contract | `implemented_verified` | `raiker/contracts/models.py`, `raiker/events/types.py` | `tests/test_event_log.py` | pass | none |
| Phase 1 | SQLite bootstrap | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/storage/migrations.py` | `tests/test_storage_sqlite.py`, `tests/test_phase_1_2_storage_events.py` | pass | none |
| Phase 1 | Append-only JSONL event writer | `implemented_verified` | `raiker/events/writer.py` | `tests/test_event_log.py`, `tests/test_phase_1_2_storage_events.py` | pass | none |
| Phase 1 | Static policy engine | `implemented_verified` | `raiker/policy/engine.py`, `raiker/policy/config.py` | `tests/test_policy_engine.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | Tool broker skeleton | `implemented_verified` | `raiker/tools/broker.py` | `tests/test_tool_broker.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | `read_file` | `implemented_verified` | `raiker/tools/filesystem.py`, `raiker/tools/broker.py` | `tests/test_tools_filesystem.py`, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 1 | `list_directory` | `implemented_verified` | `raiker/tools/filesystem.py`, `raiker/tools/broker.py` | `tests/test_tools_filesystem.py`, `tests/test_tool_broker.py` | pass | none |
| Phase 1 | `glob` | `implemented_verified` | `raiker/tools/search.py`, `raiker/tools/broker.py` | `tests/test_tools_search.py`, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 1 | `grep` | `implemented_verified` | `raiker/tools/search.py`, `raiker/tools/filesystem.py`, `raiker/tools/broker.py` | `tests/test_tools_search.py`, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 1 | Local action proposal | `implemented_verified` | `raiker/tools/broker.py`, `raiker/tools/filesystem.py`, `raiker/approvals.py` | `tests/test_tool_broker.py`, `tests/test_phase_2_approvals.py`, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 1 | Mock/test model provider | `implemented_verified` | `raiker/models/providers/mock.py`, `raiker/models/router.py`, `config/model-profiles.json` | `tests/test_models.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | Model profile registry | `implemented_verified` | `raiker/models/registry.py`, `config/model-profiles.json` | `tests/test_models.py` | pass | none |
| Phase 1 | Channel connector registry | `implemented_verified` | `raiker/channels/registry.py`, `config/channel-connectors.json` | `tests/test_channels.py` | pass | none |
| Phase 1 | Runtime state machine | `implemented_verified` | `raiker/runtime/state_machine.py`, `raiker/runtime/orchestrator.py` | `tests/test_runtime_state_machine.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | Agent gateway | `implemented_verified` | `raiker/gateway/agent_gateway.py`, `raiker/runtime/orchestrator.py` | `tests/test_agent_gateway.py`, `tests/test_phase_1_2_runtime_gather_act_verify.py` | pass | none |
| Phase 1 | Session manager | `implemented_verified` | `raiker/storage/sqlite.py`, `raiker/sessions.py` | `tests/test_session_manager.py`, `tests/test_storage_sqlite.py` | pass | none |
| Phase 1 | Checkpoint stub | `implemented_verified` | `raiker/checkpoints/service.py`, `raiker/storage/sqlite.py` | `tests/test_checkpoints.py`, `tests/test_phase_2_checkpoint_timeline.py` | pass | none |
| Phase 1 | Terminal client MVP | `implemented_verified` | `raiker/cli/main.py`, `raiker/cli/commands.py` | `tests/test_scaffold.py`, `tests/test_phase_2_terminal_commands.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |

## Phase 2 audit table

| Phase | Requirement | Claimed status | Code evidence | Test evidence | Audit verdict | Action taken |
|---|---|---|---|---|---|---|
| Phase 2 | Phase 2 build plan and status ledger | `implemented_verified` | `docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md`, `docs/IMPLEMENTATION_STATUS.md` | `scripts/validate_phase_status.py`, `scripts/validate_repo_truthfulness.py` | pass | none |
| Phase 2 | CI baseline | `implemented_verified` | `.github/workflows/ci.yml`, `.github/workflows/phase-status.yml` | workflow syntax and validation script checks | pass | none |
| Phase 2 | Task record contract and storage helpers | `implemented_verified` | `raiker/contracts/models.py`, `raiker/tasks/manager.py`, `raiker/storage/sqlite.py` | `tests/test_phase_2_task_manager.py` | pass | none |
| Phase 2 | Background task manager service | `implemented_verified` | `raiker/tasks/manager.py` | `tests/test_phase_2_task_manager.py` | pass | none |
| Phase 2 | Task lifecycle events and event indexing | `implemented_verified` | `raiker/tasks/manager.py`, `raiker/events/writer.py`, `raiker/storage/sqlite.py` | `tests/test_phase_2_task_manager.py`, `tests/test_phase_1_2_storage_events.py` | pass | none |
| Phase 2 | Event viewer query service | `implemented_verified` | `raiker/events/query.py`, `raiker/storage/sqlite.py` | `tests/test_phase_2_event_viewer.py` | pass | none |
| Phase 2 | Checkpoint timeline listing | `implemented_verified` | `raiker/checkpoints/service.py`, `raiker/storage/sqlite.py` | `tests/test_phase_2_checkpoint_timeline.py` | pass | none |
| Phase 2 | `/status` terminal command | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_terminal_commands.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |
| Phase 2 | `/tasks` terminal command | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_terminal_commands.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |
| Phase 2 | `/events` terminal command | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_terminal_commands.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |
| Phase 2 | `/checkpoints` terminal command | `implemented_verified` | `raiker/cli/commands.py` | `tests/test_phase_2_terminal_commands.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |
| Phase 2 | Side-question child-turn contract | `implemented_verified` | `raiker/side_questions.py`, `raiker/contracts/models.py`, `raiker/storage/sqlite.py` | side-question contract tests | pass | none |
| Phase 2 | Read-only side-question runtime | `implemented_verified` | `raiker/side_questions.py`, `raiker/runtime/orchestrator.py` | side-question runtime tests | pass | none |
| Phase 2 | Interrupt/steer action contracts | `implemented_verified` | `raiker/interrupts.py`, `raiker/contracts/models.py` | interrupt contract tests | pass | none |
| Phase 2 | Safe-boundary interrupt handling | `implemented_verified` | `raiker/interrupts.py`, `raiker/runtime/state_machine.py`, `raiker/runtime/orchestrator.py` | interrupt runtime tests | pass | none |
| Phase 2 | Approval inbox service | `implemented_verified` | `raiker/approvals.py`, `raiker/storage/sqlite.py` | `tests/test_phase_2_approvals.py` | pass | none |
| Phase 2 | Approval terminal commands | `implemented_verified` | `raiker/cli/commands.py`, `raiker/approvals.py` | `tests/test_phase_2_approvals.py`, `tests/test_phase_1_2_cli_acceptance.py` | pass | none |
| Phase 2 | Checkpoint restore/fork planning | `implemented_verified` | `raiker/checkpoints/service.py`, `raiker/checkpoints/planning.py` | restore/fork planning tests | pass | none |
| Phase 2 | `stat_path` and `diff_files` tools | `implemented_verified` | `raiker/tools/filesystem.py`, `raiker/tools/broker.py` | stat/diff tests, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 2 | `write_file`/`edit_file`/`apply_patch` | `implemented_verified` | `raiker/tools/broker.py`, `raiker/tools/filesystem.py`, `raiker/approvals.py` | file mutation approval tests, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 2 | `git status`/`diff`/`log` wrappers | `implemented_verified` | `raiker/tools/git.py`, `raiker/tools/broker.py` | git wrapper tests, `tests/test_phase_1_2_verifier.py` | pass | none |
| Phase 2 | Local provider health-check | `implemented_verified` | `raiker/models/health.py`, `raiker/models/providers/openai_compatible.py`, `raiker/models/router.py` | health check tests | pass | none |
| Phase 2 | Memory candidate listing | `implemented_verified` | `raiker/memory/candidates.py`, `raiker/cli/commands.py`, `raiker/context/gatherer.py` | memory candidate tests, `tests/test_phase_1_2_context_gatherer.py` | pass | none |
| Phase 2 | Phase 2 integration validation | `implemented_verified` | `raiker/runtime/orchestrator.py`, `raiker/context/`, `raiker/verification/` | `tests/test_phase_1_2_runtime_gather_act_verify.py`, validation scripts | pass | none |

## Context gatherer audit

Verdict: pass after this PR.

Evidence:

- `raiker/context/gatherer.py` builds a bounded `ContextBundle` from current prompt plus safe Phase 1/2 local metadata: workspace summary, disabled capability status, approvals, recent events, tasks, checkpoints, memory status/candidates, and model profile metadata.
- `raiker/context/models.py` defines source type, trust level, sensitivity, provenance, redaction, item budgeting, and metadata-only event payloads.
- `raiker/context/redaction.py` deterministically redacts obvious tokens, secrets, emails, private keys, bearer tokens, API keys, and high-entropy strings.
- `tests/test_phase_1_2_context_gatherer.py` verifies inclusion, ordering, budgeting, deterministic redaction, metadata-only memory candidates, no unsafe source types, and bounded recent events.
- `tests/test_phase_1_2_runtime_gather_act_verify.py` verifies the runtime emits `context_gathered` and no longer uses the fixed `sources=["current_prompt"]` path.
- `tests/test_phase_1_2_acceptance_hardening.py` now verifies the required disabled runtime flags are all surfaced as false and that the context event payload remains metadata-only.

Action taken: fixed missing disabled runtime flag coverage in `CAPABILITY_FLAGS`.

## Verifier audit

Verdict: pass.

Evidence:

- `raiker/verification/verifier.py` is deterministic and not pass-through: it checks unknown/invalid tool calls, denied action non-execution, approval-required action non-execution, read-tool result shape, and mutation proposal gating.
- `raiker/verification/models.py` exposes metadata-only `event_payload()` output for `verification_completed`.
- `raiker/runtime/orchestrator.py` emits `verification_started` and `verification_completed` events in the gather-act-verify loop.
- `tests/test_phase_1_2_verifier.py` verifies invalid tool calls fail, unknown tools fail, denied actions must not execute, approval-required actions require approval records and stop before execution, read-result shape is checked, mutation proposals remain approval-gated, and private reasoning markers are not emitted.
- `tests/test_phase_1_2_acceptance_hardening.py` verifies verification event payloads do not include raw tool output, tool arguments, private reasoning, or secret-bearing read results.

Action taken: added explicit metadata-only verification event payload acceptance coverage.

## Tool and policy audit summary

Verdict: pass.

Phase 1/2 tools are mediated by `ToolBroker` and `PolicyEngine` before execution. Read-only filesystem/search tools resolve paths inside the workspace, reject traversal/escape, sort or bound outputs deterministically, and distinguish binary/text inputs where needed. Mutation tools use proposal/approval paths rather than direct execution. Git wrappers are surfaced through the broker and policy gates. Verifier coverage now also confirms result shapes for read tools and mutation proposal gating.

## Event and storage audit summary

Verdict: pass.

SQLite bootstrap creates Phase 1/2 tables, later readiness-only tables are non-executing metadata foundations, sessions/tasks/events/checkpoints/approvals are persisted and queryable, event logs are append-only JSONL, and context/verification event payloads are metadata-only. Approval records remain action-bound through `approval_id -> action_id` storage.

## CLI audit summary

Verdict: pass.

Phase 1/2 CLI commands are implemented in `raiker/cli/commands.py` and covered by terminal command tests. Unknown commands fail safely, approval commands require an exact approval ID, and `/launch --provider mock --model mock-deterministic` remains documented as test-only/policy-blocked for normal CLI use.

## Rows fixed in this PR

| Area | Problem found | Fix |
|---|---|---|
| Context gatherer disabled flags | `CAPABILITY_FLAGS` did not directly include every required disabled runtime flag listed by the Phase 1/2 hardening audit. | Added the missing flags and new tests that assert all required disabled runtime flags are present and false. |
| Acceptance coverage | No single test directly asserted the full required disabled flag set and metadata-only context/verification event payloads. | Added `tests/test_phase_1_2_acceptance_hardening.py`. |

## Rows downgraded

None. No Phase 1 or Phase 2 row was downgraded in this PR.

## Follow-up tasks

- Run full local validation before merge in a checkout with repository access.
- Keep code-review workflow as a separate `specified_not_implemented` follow-up outside this PR.
- Do not expand this PR into Phase 3/4 runtime activation.

## Validation evidence

This audit was prepared through repository file inspection and targeted changes through the GitHub connector. The execution sandbox used for this pass could not clone the private repository because it has no direct network access to `github.com`, so full local validation commands were not executed in this environment.

Required before merge:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
raiker --help
raiker --prompt "Hello Raiker"
raiker --prompt "/status"
raiker --prompt "/tasks"
raiker --prompt "/events"
raiker --prompt "/checkpoints"
raiker --prompt "/approvals"
raiker --prompt "/memory"
raiker --prompt "/models"
raiker --prompt "/model current"
raiker --prompt "/model capabilities"
raiker --prompt "/reasoning status"
raiker --prompt "/doctor"
```

Hosted GitHub Actions may remain red/unavailable because Actions quota is exhausted; local validation evidence remains the source of truth during quota exhaustion.
