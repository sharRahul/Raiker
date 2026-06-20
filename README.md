# Raiker

## Raiker Description

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, mobile device, browser, chat workspace, or governed enterprise environment.

Raiker is not just a chatbot. It is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, channels, checkpoints, execution environments, approval previews, and rich interactive clients behind a security and privacy boundary.

Raiker installs one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` currently launches a simple terminal/CLI shell. Rich TUI panels and other renderers remain specified/deferred unless an implementation is explicitly added and tested. This command is one primary interface, not the canonical or exclusive interface.

Raiker does **not** have one privileged human interface. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Why Raiker

Most AI coding assistants and local agent tools focus on one interface, one model path, or one execution style. Raiker is designed as a governed agent operating layer where every interface talks through the same runtime, contracts, policy checks, event log, storage layer, approval-preview flow, and checkpoint flow.

Raiker exists to provide:

- local-first operation by default;
- equal-status primary interfaces instead of one privileged chat or terminal UI;
- explicit contracts for prompts, UI actions, channel messages, tools, policy decisions, events, responses, approval previews, and checkpoints;
- policy-gated tool execution;
- append-only event logging;
- SQLite-backed state, search, registry, memory, graph, approval, and checkpoint metadata;
- model-provider abstraction for local and hosted providers;
- governed memory and context handling;
- interruptible work with side questions, approvals, pause/cancel/steer, preview-only gates, and checkpoints;
- a phased implementation path that local or cloud builder agents can follow without inventing architecture.

---

## Current Repository Status

**Read this section before implementing anything.** The README is a project entry point, but [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) is the implementation control ledger.

As of the current `main` state:

All Phase 3 slices A through P are implemented, tested, and documented. Phase 3 Slice B approval planning preview is implemented. Runtime execution remains disabled.

The current launchable UI is a simple terminal/CLI shell plus read-only shared view contracts. Desktop/Web/Dashboard/Mobile apps, Rich TUI panels, REST/API, IDE, Voice, Browser Extension, and external channel clients are specified/deferred, not implemented as launchable apps. Runtime execution remains disabled and Phase 4 remains blocked. Disabled runtime flags remain false: plugin_execution_enabled, graph_indexing_enabled, semantic_memory_writes_enabled, vector_writes_enabled, embedding_creation_enabled, approval_execution_enabled, approval_relay_runtime_enabled, cleanup_execution_enabled, rollback_execution_enabled, external_channels_enabled, notifications_enabled, remote_execution_enabled, container_execution_enabled, cloud_execution_enabled, process_execution_enabled, shell_execution_enabled, network_execution_enabled, runtime_execution_enabled.

| Area | Status | Notes |
|---|---|---|
| Phase 1 MVP runtime core | `implemented_verified` | Package scaffold, global `raiker` command, contracts, event log, SQLite bootstrap, static policy, tool broker, safe filesystem/search tools, approval-gated local actions, mock model provider, runtime state machine, terminal shell, and checkpoint stubs are present and covered by tests. |
| Phase 2 rich local workspace | `implemented_verified` | Task management, event viewer, checkpoint timeline, status/task/event/checkpoint/approval commands, side-question and interrupt contracts, approval inbox, governed file/git wrappers, local provider health-check, and memory candidate views are present and covered by tests. |
| Phase 3 Slice A proposal lifecycle | `implemented_verified` | Proposal lifecycle foundation: `/review --propose-fixes --save-proposals`, `/proposals`, `/proposal <proposal_id>`, metadata-only lifecycle records and events. |
| Phase 3 Slice B approval planning preview | `implemented_verified` | Approval planning previews from saved proposals: `/proposal <proposal_id> --approval-preview`, `/approval-previews`, `/approval-preview <preview_id>`. Preview-only, no execution. |
| Phase 3 safe foundation/readiness slices C-P | `implemented_verified` | Implemented verified for safe local rich workspace/extensibility foundations, CLI functional-test surfaces, read-only shared workspace contracts, planning-only plugin validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full Desktop/Web/Dashboard/Mobile apps, REST API, plugin execution, semantic search runtime, graph indexing runtime, MCP/LSP runtime, scheduled automations, and external channels are specified/deferred, not implemented. |
| Phase 4 external channel / multi-agent / governed execution foundations | **Foundation only; Phase 4 is not complete** | Execution profiles, remote/container execution planning, subagent planning, external-channel activation status, and inspection commands are present. External transports, subagent spawning, multi-agent teams, remote execution, and container execution remain disabled. |
| GitHub Actions | Active CI plus manual phase validation | `.github/workflows/ci.yml` runs on `pull_request` and `push` to `main`. `.github/workflows/phase-status.yml` remains manual `workflow_dispatch`. Local validation remains required when Actions quota prevents actual runs; do not claim all workflows are `workflow_dispatch`-only while CI is active. |

> **Review note (2026-06-19):** A full repository review is recorded in
> [`docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md`](docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md).
> Since that review, two of its top gaps were closed: the **llama.cpp server** is now the native
> default backend with a model-driven tool-calling loop (`raiker/models/providers/`,
> `raiker/runtime/orchestrator.py`), and **hooks** are implemented (`raiker/hooks/`, `builtin`+
> `command` handlers). Remaining stubs tracked in
> [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) under "Known Documentation/Code
> Gaps": the **verifier** and **context gatherer** are still placeholders, and the deferred hook
> handler types (`http`/`mcp_tool`/`prompt`/`agent`) are not wired.

Do **not** mark any capability `implemented_verified` unless:

1. the implementation maps to a named phase task;
2. required tests exist;
3. validation evidence is recorded;
4. contracts, events, storage, policy, and equal-interface rules match the docs;
5. unsafe phase-scheduled runtime features remain disabled unless their explicit activation tasks are complete.

---

## What Raiker Currently Provides

### Phase 1 local runtime core

- Global `raiker` terminal command.
- Prompt envelope and shared contract models.
- Agent Gateway and deterministic runtime state machine.
- Append-only JSONL event log plus SQLite runtime state.
- Static policy engine.
- Tool broker skeleton.
- Safe filesystem/search tools: `read_file`, `list_directory`, `glob`, `grep`.
- Approval-gated local action proposal path.
- Deterministic mock model provider.
- Model profile registry and channel connector profile registry.
- Checkpoint stubs.
- Equal-interface metadata proving the terminal is not a privileged/canonical-only interface.

### Phase 2 rich local workspace

- Task record storage and task manager service.
- Task lifecycle events and event indexing.
- Event viewer query service.
- Checkpoint timeline listing.
- `/status`, `/tasks`, `/events`, and `/checkpoints` inspection commands.
- Side-question child-turn contracts and read-only runtime path.
- Interrupt/pause/cancel/steer contracts with safe-boundary handling.
- Approval inbox service and `/approvals`, `/approve <id>`, `/deny <id>` commands.
- `stat_path`, `diff_files`, write/edit/apply-patch proposal paths, and git status/diff/log wrappers under policy.
- Local provider health-check abstraction.
- Memory candidate listing and governed memory status view.

### Phase 3 — implemented and verified

The restored Phase 1 and Phase 2 build-plan documents remain the detailed scope sources for those completed phases; Slice G/H references are later-phase metadata-only additions and do not change Phase 1 or Phase 2 runtime scope.

- Capability gates for Phase 3 features.
- Read-only workspace inspection shared by terminal, desktop, web, and dashboard client types.
- `/workspace`, `/workspace-view`, and `/clients` inspection commands.
- Plugin manifest validation and registration planning without importing or executing plugin code.
- `/plugins` and `/plugin-plan <manifest_path>` inspection/planning commands.
- Graph/codemap governance status and dry-run planning with safe path filtering.
- `/graph-status` and `/graph-plan` commands.
- Semantic memory status and review queue governance.
- `/semantic-memory`, `/memory`, `/memory-review`, and `/memory-review --summary` commands.
- Approval-preview contracts for future graph indexing and semantic memory writes.
- `/approval-previews`, `/graph-approval-preview`, `/memory-approval-preview [--summary]`, and `/approval-preview <preview_id>` preview commands.
- Workspace inspection/view `approval_preview_summary` showing preview availability and disabled runtime state.
- Slice I lifecycle evidence bundles and policy simulations with deterministic `sleb_`/`slps_` IDs, redacted JSON exports, read-only CLI commands, metadata-only SQLite tables, and disabled runtime flags.
- Slice P remote/container/cloud execution readiness contracts, registry, optional SQLite persistence, and read-only `/remote-readiness` CLI with deterministic `rccr_` IDs and all runtime execution flags disabled.

### Phase 4 safe foundations only

- Capability gates for Phase 4 features.
- Listable execution profiles for local/container/SSH/Daytona-style environments.
- Remote/container execution plans that deny execution by default.
- Subagent plans that cannot spawn workers.
- External-channel activation status that keeps transports inactive.
- `/execution-profiles` inspection command.

---

## Disabled Runtime Capabilities

The following capabilities are intentionally **not active** and must stay disabled until their phase-specific policy, storage, event, lifecycle, approval, audit, rollback, and acceptance-test work is complete:

- plugin code execution;
- graph/codemap runtime indexing;
- background graph indexing, watchers, or daemons;
- semantic/vector memory writes;
- embedding creation;
- vector record creation;
- durable semantic memory writes;
- durable approval-preview persistence or approval-preview execution;
- external channel transport activation;
- approval relay over external channels;
- subagent spawning;
- multi-agent team execution;
- remote execution;
- container execution;
- hosted model billing/runtime paths that are not explicitly policy-gated.

Planning, status, manifest validation, dry-run, review-queue, approval-preview, and read-only inspection surfaces are allowed where documented. They must not silently activate runtime execution.

---

## Quick Start

### Install for local development

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
raiker
```

On Windows PowerShell:

```powershell
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
raiker
```

### Submit one prompt and exit

```bash
raiker --prompt "Hello Raiker"
```

### Use a specific workspace root

```bash
raiker --workspace /path/to/workspace
```

---

## CLI Command Surface

The terminal client currently exposes these inspection and controlled-action commands:

```text
/help
/providers
/models
/model current
/model use <profile_id>
/model use --provider <provider> --model <model>
/model health
/model capabilities
/reasoning
/reasoning status
/reasoning set <mode-or-effort>
/reasoning off
/status
/tasks
/events
/checkpoints
/approvals
/approve <id>
/deny <id>
/memory
/semantic-memory
/capabilities
/execution-profiles
/workspace
/workspace-view
/clients
/plugins
/plugin-plan <manifest_path>
/graph-status
/graph-plan
/graph-readiness [--summary|--json]
/memory-readiness [--summary|--json]
/approval-readiness [--summary|--json]
/cleanup-readiness [--summary|--json]
/remote-readiness [--summary|--json]
/plugin-readiness [--summary|--json]
/channel-readiness [--summary|--json]
/memory-review [--summary]
/approval-previews [--json] [--status <status>] [--limit <n>]
/graph-approval-preview
/memory-approval-preview [--summary]
/approval-preview <preview_id> [--json]
/approval-audit [--summary]
/rollback-plan
/graph-rollback-plan
/memory-rollback-plan
/storage-lifecycle [--summary|--graph|--memory]
/storage-lifecycle-retention [--summary]
/storage-lifecycle-cleanup-preview [--summary]
/storage-lifecycle-handoff [--summary]
/storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]
/storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]
/review [--summary] [--staged] [--path <path>] [--json] [--limit <number>] [--severity <info|low|medium|high>] [--propose-fixes] [--proposals-only] [--save-proposals]
/proposals [--json] [--status <proposed|acknowledged|deferred|rejected|superseded>] [--limit <number>]
/proposal <proposal_id> [--json] [--mark <proposed|acknowledged|deferred|rejected|superseded>] [--approval-preview]
/doctor
/channels
/launch --provider mock --model mock-deterministic
/quit
```

The deterministic mock launch command is test-only: normal production CLI policy blocks `/launch --provider mock --model mock-deterministic` and should report `deterministic_test_provider_requires_test_mode` unless explicit test mode/test harness policy is active.

### Phase 2.5 local code-review workflow

`/review` is a Phase 2.5 local CLI code-review workflow MVP: `implemented_verified` for CLI-only, read-only, bounded local diff review using deterministic rule-based findings and metadata-only events. It inspects local Git status/diff through the existing policy-mediated `ToolBroker`/`PolicyEngine` git wrappers and the Phase 1/2-safe context gatherer, then returns deterministic findings (missing tests, secret-like additions, Phase 3/4 scope expansion, risky runtime activation, docs-only/test-only changes, large-diff truncation, and metadata-only untracked-file presence).

Phase 2.5 hardening is complete: `--severity` and `--limit` summaries are rebuilt from filtered findings, and untracked files are detected as metadata-only (contents never read or leaked).

### Phase 2.6 review-to-action proposal workflow

Phase 2.6 review-to-action proposal workflow: `implemented_verified` for local CLI-only proposal generation from deterministic review findings. `/review --propose-fixes` converts review findings into safe, in-memory proposed actions (`ReviewActionProposal`) using a deterministic generator (`raiker/review/proposals.py`). Proposals are included in text/JSON output and a metadata-only `review_proposals_created` event records proposal/risk counts. `--severity`/`--limit` filtering applies before proposal generation so proposals align with visible findings. `--proposals-only` shows proposals with finding references but omits detailed finding text.

Phase 2.6 is proposal-only. No fixes are applied. No files are modified. No tests are run. No shell/process/network execution is used. No GitHub PR automation is implemented. No UI/API/IDE/dashboard/mobile surface is implemented. No model-assisted/semantic review is implemented. No Phase 3/4 runtime capability is enabled.

`/review` is local CLI code review only. It is not a review UI, web/dashboard review surface, IDE review surface, REST/API review server, or GitHub PR review automation, and it does not apply fixes, run tests, mutate files, or touch the Git index. Raw diffs and secrets are never written into findings, proposals, or event payloads.

### Phase 3 Slice A proposal lifecycle foundation

Phase 3 Slice A proposal lifecycle foundation: `implemented_verified` for local metadata-only proposal lifecycle tracking. `/review --propose-fixes --save-proposals` persists generated `ReviewActionProposal` records as metadata-only `ProposalLifecycleRecord` rows in the local SQLite `proposal_lifecycle_records` table. `/proposals` lists saved records (newest first, default limit 20) with `--json`, `--status <proposed|acknowledged|deferred|rejected|superseded>`, and `--limit <number>`. `/proposal <proposal_id>` shows one record with `--json` and `--mark <status>` transitions (metadata only).

Phase 3 Slice A is metadata-only; proposal-only; no proposal execution; no auto-fix; no patch application; no file mutation; no staging/unstaging; no test execution; no GitHub PR automation; no UI/API/IDE/dashboard/mobile; no approval execution; no Phase 4. `approval_execution_enabled` remains false. Disabled runtime flags remain false. No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw tool output, or patch content is stored in records or event payloads. Metadata-only `proposal_lifecycle_created`, `proposal_lifecycle_status_changed`, `proposal_lifecycle_listed`, and `proposal_lifecycle_viewed` events are emitted.

Phase 3 and Phase 4 commands are inspection/planning/governance/preview surfaces unless explicitly documented otherwise. They must not execute plugins, activate channels, write semantic/vector memory, create embeddings, start graph indexing, persist executable approvals, spawn agents, or run remote/container commands.

### Phase 3 Slice Q1 documented default Rich TUI access shell

Phase 3 Slice Q1 documented default Rich TUI access shell: `implemented_verified` for the
documented default layout only. Running `raiker` interactively renders the documented
default layout from `docs/UI_UX_DESIGN_SPEC.md` — a Primary/Main panel, an Activity panel,
an Input panel, and a configurable Status Bar panel — and `raiker --prompt "..."` stays
line-oriented and exits. The shell adapts to standard, narrow, and no-colour/ASCII
terminals, keeps safety labels (state, network, approvals, disabled runtime) visible, and
falls back to a plain terminal loop when rich is unavailable, the terminal is
non-interactive, or `RAIKER_TUI=plain` is set. A grouped command overlay is available via
`/commands` (or `/palette`); a searchable keyboard-driven palette is deferred to a later
slice.

This does not implement the full advanced Rich TUI, extended developer panels, plugin
panels, custom panel registry, desktop/web/mobile apps, REST API, external channels,
runtime execution, proposal execution, approval execution, graph indexing,
semantic/vector writes, remote/container/cloud execution, shell/process execution, or
direct network execution. The shell creates no new runtime authority: prompts route
through the existing `submit_terminal_prompt()` / Agent Gateway path and slash commands
route through the existing `handle_slash_command()` handlers. TUI panel modules call no
tools, models, plugins, channels, shell, subprocess, sockets, or network APIs directly,
mutate no files, and execute no approvals or proposals. Q1 adds no new events (it reuses
existing command/runtime events) and no new storage. `approval_execution_enabled` remains
false and Runtime execution remains disabled. Disabled runtime flags remain false. See
`docs/completed/PHASE_3_SLICE_Q1_RICH_TUI_DEFAULT_ACCESS_SHELL_SPEC.md`.

---

## Current UI/UX Implementation Truth Table

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

## Developer Validation

GitHub Actions CI is configured for `pull_request` and `push` to `main`; the separate phase-status workflow is manual `workflow_dispatch`. Local validation is mandatory before merge or direct main changes, especially when Actions quota or environment limits prevent actual hosted runs.

Run the documented local validation gate:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
raiker --help
raiker --prompt "Hello Raiker"
```

For Phase 3 rollout branches, also smoke-test the inspection and preview commands listed in [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md), including `/capabilities`, `/semantic-memory`, `/execution-profiles`, `/workspace`, `/workspace-view`, `/plugins`, `/plugin-plan`, `/graph-status`, `/graph-plan`, `/memory-review`, `/approval-previews`, `/graph-approval-preview`, `/memory-approval-preview`, and `/doctor` where applicable.

Validation evidence should record:

- branch and commit tested;
- OS and Python version;
- virtual environment details;
- commands run;
- test totals;
- CLI smoke results;
- confirmation that unsafe runtime gates remain disabled;
- files changed;
- remaining risks;
- statement of whether hosted GitHub Actions actually ran; local validation evidence remains required when quota or environment limits apply.

---

## Builder Reading Order

Recommended builder flow:

```text
README.md
  -> docs/IMPLEMENTATION_STATUS.md
  -> docs/LOCAL_VALIDATION_GATE.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/ROADMAP_PHASE_2_TO_PHASE_5.md
  -> docs/BUILD_ORDER.md
  -> docs/ARCHITECTURE.md
  -> docs/CONTRACTS.md
  -> docs/API_AND_CONTRACT_SCHEMAS.md
  -> docs/EVENT_CATALOG.md
  -> docs/RUNTIME_STATE_MACHINE.md
  -> docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/SECURITY_AND_POLICY.md
  -> docs/THREAT_MODEL.md
  -> docs/NON_GOALS_AND_BOUNDARIES.md
  -> docs/completed/PHASE_1_MVP_BUILD_PLAN.md
  -> docs/completed/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md
  -> docs/completed/PHASE_3_BUILD_PLAN.md
  -> docs/PHASE_4_BUILD_PLAN.md
  -> docs/RUNTIME_ORCHESTRATION_SPEC.md
  -> docs/TOOLS_AND_PERMISSIONS_SPEC.md
  -> docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md
  -> docs/MODEL_PROVIDER_CONTRACT.md
  -> docs/CHANNELS_SPEC.md
  -> docs/UI_UX_DESIGN_SPEC.md
  -> docs/MEMORY_AND_CONTEXT_STRATEGY.md
  -> docs/MEMORY_GOVERNANCE_RULES.md
  -> docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md
  -> docs/PLUGIN_SYSTEM_SPEC.md
  -> docs/PLUGIN_MANIFEST_SCHEMA.md
  -> docs/EXECUTION_ENVIRONMENTS_SPEC.md
  -> docs/ACCEPTANCE_TESTS_BY_PHASE.md
  -> docs/REFERENCE_REQUIREMENTS_MATRIX.md
  -> docs/VERIFICATION_PLAN.md
  -> config/model-profiles.json
  -> config/channel-connectors.json
```

---

## Documentation Map

Raiker is intended to be implemented by local or cloud AI coding agents. Implementation is phased, but the specification is not vague. Every phase-scheduled feature must already have contracts, storage, runtime lifecycle, UI surface, security rules, events, tests, and failure handling.

### Core implementation docs

| Document | Purpose |
|---|---|
| [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) | Status ledger for specified, implemented, disabled, blocked, and out-of-scope capabilities. |
| [`docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md`](docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md) | Critical review vs reference platforms: capability coverage, doc/code gap analysis, OWASP status, and engineering backlog. |
 | [`docs/PHASE_3_COMPLETION_AUDIT.md`](docs/PHASE_3_COMPLETION_AUDIT.md) | Phase 3 completion audit confirming all slices A-P are implemented, tested, and documented with runtime execution disabled. |
 | [`docs/PHASE_3_READINESS_PATTERN_CONSOLIDATION_AUDIT.md`](docs/completed/PHASE_3_READINESS_PATTERN_CONSOLIDATION_AUDIT.md) | Audit of repeated Phase 3 readiness patterns across Slices J-O and the recommended shared internal foundation before Slice P. (Completed; archived under `docs/completed/`.) |
| [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md) | Required local validation while GitHub Actions are paused. |
| [`docs/FEATURE_COVERAGE_MATRIX.md`](docs/FEATURE_COVERAGE_MATRIX.md) | Full platform coverage checklist, phase placement, and non-negotiable invariants. |
| [`docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`](docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md) | Phase 1 to Phase 5 implementation blueprint and builder hand-off flow. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Phased architecture, component responsibilities, equal-interface flow, and implementation boundaries. |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | Contracts for prompts, events, plans, actions, policy decisions, tool results, responses, approval previews, and checkpoints. |
| [`docs/API_AND_CONTRACT_SCHEMAS.md`](docs/API_AND_CONTRACT_SCHEMAS.md) | Strict schema reference for IDs, client metadata, prompts, UI/channel actions, tools, approvals, approval previews, responses, and checkpoints. |
| [`docs/EVENT_CATALOG.md`](docs/EVENT_CATALOG.md) | Canonical event names, payload expectations, ordering, actors, approval-preview events, and event indexing rules. |
| [`docs/RUNTIME_STATE_MACHINE.md`](docs/RUNTIME_STATE_MACHINE.md) | Legal runtime transitions, invalid transitions, guards, state events, and state-machine tests. |
| [`docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`](docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md) | SQLite, JSONL, FTS5, vector metadata, graph tables, recursive CTEs, checkpoint and memory storage. |
| [`docs/SECURITY_AND_POLICY.md`](docs/SECURITY_AND_POLICY.md) | Security model, policy matrix, path safety, command approval, memory governance, and security tests. |
| [`docs/RUNTIME_ORCHESTRATION_SPEC.md`](docs/RUNTIME_ORCHESTRATION_SPEC.md) | Runtime orchestration, background tasks, interrupts, side questions, verification, and deterministic event ordering. |
| [`docs/TOOLS_AND_PERMISSIONS_SPEC.md`](docs/TOOLS_AND_PERMISSIONS_SPEC.md) | Tool catalogue, broker lifecycle, approvals, permission scopes, command policy, and testing rules. |
| [`docs/VERIFICATION_PLAN.md`](docs/VERIFICATION_PLAN.md) | Validation commands, event sequences, PR checklist, local/cloud builder evaluation scenarios. |

### Phase plans

| Document | Purpose |
|---|---|
| [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/completed/PHASE_1_MVP_BUILD_PLAN.md) | Phase 1 build scope, task order, and acceptance criteria. (Phase 1 complete; archived under `docs/completed/`.) |
| [`docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md`](docs/completed/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md) | Phase 2 task decomposition and rich local workspace acceptance criteria. (Phase 2 complete; archived under `docs/completed/`.) |
| [`docs/PHASE_3_BUILD_PLAN.md`](docs/completed/PHASE_3_BUILD_PLAN.md) | Phase 3 local rich workspace, extensibility foundation, governance, and approval-preview plan. (Phase 3 complete; archived under `docs/completed/`.) |
| [`docs/PHASE_4_BUILD_PLAN.md`](docs/PHASE_4_BUILD_PLAN.md) | Phase 4 external channels, multi-agent, and governed execution plan. |
| [`docs/ROADMAP_PHASE_2_TO_PHASE_5.md`](docs/ROADMAP_PHASE_2_TO_PHASE_5.md) | Phase-scheduled roadmap from local MVP to governed enterprise/home-lab platform. |

### Builder-proof control docs

| Document | Purpose |
|---|---|
| [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md) | Dependency-safe implementation order and PR completion gate. |
| [`docs/ACCEPTANCE_TESTS_BY_PHASE.md`](docs/ACCEPTANCE_TESTS_BY_PHASE.md) | Phase-by-phase acceptance tests required before a feature can be called complete. |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Assets, trust boundaries, threats, controls, and threat-driven tests. |
| [`docs/NON_GOALS_AND_BOUNDARIES.md`](docs/NON_GOALS_AND_BOUNDARIES.md) | Explicit product, phase, architecture, storage, model, memory, and security boundaries. |
| [`docs/REFERENCE_REQUIREMENTS_MATRIX.md`](docs/REFERENCE_REQUIREMENTS_MATRIX.md) | Mapping from reference agent-platform capabilities to Raiker contracts, events, storage, policy, tests, and phases. |

### Interface, model, channel, and UX docs

| Document | Purpose |
|---|---|
| [`docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`](docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) | Global `raiker` command, equal primary interfaces, TUI actions, slash commands, model launch, side questions, approvals, preview commands, and keyboard UX. |
| [`docs/UI_UX_DESIGN_SPEC.md`](docs/UI_UX_DESIGN_SPEC.md) | Shared UX, Rich TUI, configurable status bar, optional panels, Desktop UI, Web UI, Dashboard, IDE, Voice UI, Apple/Android mobile apps, approval-preview UI, and channel clients. |
| [`docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`](docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) | Model profiles, local providers, hosted policy gates, launch contract, streaming, tool-call modes. |
| [`docs/MODEL_PROVIDER_CONTRACT.md`](docs/MODEL_PROVIDER_CONTRACT.md) | Provider adapter interface, model request/response schema, provider policy, events, and mock-provider acceptance. |
| [`config/model-profiles.json`](config/model-profiles.json) | Built-in model launch profile registry for mock, the llama.cpp server (native default), LM Studio, OpenAI-compatible, vLLM (later), and hosted providers. |
| [`docs/CHANNELS_SPEC.md`](docs/CHANNELS_SPEC.md) | Channel connector profiles, pairing, sender trust, routing, side questions, approval relay, link/unlink lifecycle. |
| [`config/channel-connectors.json`](config/channel-connectors.json) | Built-in connector profile registry used by UI listing/linking flows before implementation wiring. |

### Memory, graph, plugins, execution, and roadmap docs

| Document | Purpose |
|---|---|
| [`docs/MEMORY_AND_CONTEXT_STRATEGY.md`](docs/MEMORY_AND_CONTEXT_STRATEGY.md) | Working, profile, project, episodic, procedural, semantic, graph, eidetic observation, and gist memory. |
| [`docs/MEMORY_GOVERNANCE_RULES.md`](docs/MEMORY_GOVERNANCE_RULES.md) | Memory candidate/record schemas, sensitivity levels, write/use/poisoning controls, preview rules, and memory-governance tests. |
| [`docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`](docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md) | Eidetic-style raw observations, gist memory, retention, exact replay, skill learning, and self-improvement controls. |
| [`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md) | Graph entities, relationships, codemap indexing, graph queries, staleness, graph-context retrieval, and approval previews. |
| [`docs/HOOKS_SPEC.md`](docs/HOOKS_SPEC.md) | Hook lifecycle events, handlers, matchers, async hooks, decision authority, and hook security. |
| [`docs/EXTENSIBILITY_MODEL.md`](docs/EXTENSIBILITY_MODEL.md) | Unified model of the five extension surfaces (tools, hooks, skills, plugins, channels), shared trust/scope/lifecycle rules, and current code state. |
| [`docs/SELF_IMPROVEMENT_MODEL.md`](docs/SELF_IMPROVEMENT_MODEL.md) | First-class self-improvement/skill-learning spec: closed loop, distillation contract, safety boundaries, and tests. |
| [`docs/PLUGIN_SYSTEM_SPEC.md`](docs/PLUGIN_SYSTEM_SPEC.md) | Plugin manifests, components, permissions, trust levels, lifecycle, skills, channels, and supply-chain controls. |
| [`docs/PLUGIN_MANIFEST_SCHEMA.md`](docs/PLUGIN_MANIFEST_SCHEMA.md) | Strict plugin manifest schema, required fields, permission declaration rules, trust rules, events, and tests. |
| [`docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`](docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md) | Subagents, multi-agent teams, bounded delegation, side questions, and parent verification. |
| [`docs/EXECUTION_ENVIRONMENTS_SPEC.md`](docs/EXECUTION_ENVIRONMENTS_SPEC.md) | Local, worktree, container, SSH, VPS, Kubernetes, cloud/GPU execution profiles, artifacts, and resource controls. |
| [`docs/OWASP_GENAI_SECURITY_MAPPING.md`](docs/OWASP_GENAI_SECURITY_MAPPING.md) | GenAI/LLM risk mapping, controls, and security test matrix. |
| [`docs/REFERENCE_PLATFORM_COMPATIBILITY.md`](docs/REFERENCE_PLATFORM_COMPATIBILITY.md) | Mapping to Claude Code, OpenClaw, Hermes, memory, graph, local inference, and security reference concepts. |
| [`docs/LOCAL_LLM_BUILDER_GUIDE.md`](docs/LOCAL_LLM_BUILDER_GUIDE.md) | Operating rules, prompt template, and anti-drift checklist for local/cloud builder agents. |
| [`docs/ADR_TEMPLATE.md`](docs/ADR_TEMPLATE.md) | Template for documenting design decisions instead of silently inventing behaviour. |

---

## Versioning

Raiker starts at package/application version `0.0.0`. Patch updates must progress through `0.0.1` to `0.0.99` before the project is bumped to `0.1.0`.

The current package metadata still reports version `0.0.0`.

---

## Support and Change Rules

For now:

- use the documentation map above and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) as the source of truth;
- open a GitHub issue for bugs, documentation gaps, implementation questions, or scope conflicts;
- include the relevant phase, task ID, file path, expected behaviour, and actual behaviour;
- do not treat undocumented behaviour as approved implementation scope;
- do not claim GitHub CI passed while Actions are paused;
- do not activate disabled runtime capabilities through README, docs, tests, or code shortcuts.

If a builder finds conflicting instructions, it should stop, report the conflict, and update the relevant spec before implementing behaviour that could affect architecture, security, storage, policy, or interface parity.

## Phase 3 Slice H lifecycle retention update

Slice H adds metadata-only lifecycle retention policies, cleanup previews, expiry/supersede counts, and approval-handoff planning. The read-only commands are `/storage-lifecycle-retention`, `/storage-lifecycle-retention --summary`, `/storage-lifecycle-cleanup-preview`, `/storage-lifecycle-cleanup-preview --summary`, `/storage-lifecycle-handoff`, and `/storage-lifecycle-handoff --summary`. Slice H does not execute cleanup, graph/codemap indexing, semantic/vector memory writes, embeddings, rollback, plugins, channels, subagents, or remote/container/cloud execution.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/completed/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Phase 3 next slice definition audit

Slice J adds metadata-only/read-only graph/codemap readiness contracts, optional SQLite metadata persistence, workspace inspection/view summaries, and `/graph-readiness [--summary|--json]`. Slice J does not enable graph/codemap indexing, graph writes, codemap writes, indexing jobs, runtime execution, workers, schedulers, file watchers, daemons, semantic/vector memory writes, embeddings, approval relay runtime, plugin execution, MCP/LSP/plugin server startup, cleanup execution, rollback execution, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, or share links. Slice J did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked from starting as a substitute.


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Slice K did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice L — Approval Preview Persistence Readiness — Metadata Only

Slice L adds deterministic metadata-only approval preview persistence readiness contracts, registry, optional SQLite metadata table, `/approval-readiness [--summary|--json]`, workspace summaries, and reserved metadata-only events. Approval execution, approval relay runtime, durable approval queues, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Reserved Slice L metadata-only events: `phase3.approval_readiness.metadata_created`, `phase3.approval_readiness.summary_viewed`, `phase3.approval_readiness.exported`. Slice L did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Phase 3 Slice M: Storage cleanup execution readiness metadata

Slice M adds metadata-only storage cleanup execution readiness surfaces. Cleanup execution, deletion, purge, tombstone, rollback, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice M did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/server startup readiness metadata

Slice N adds metadata-only plugin/server startup readiness contracts, registry, optional SQLite metadata table, `/plugin-readiness [--summary|--json]`, workspace summaries, and reserved metadata-only events. Plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace installs, hosted routines, external channels, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

### Phase 3 Slice O: External Channels/Notifications Readiness — Metadata Only

Slice O adds deterministic metadata-only readiness surfaces for future external channels and notifications. `/channel-readiness`, workspace inspection, workspace views, and optional SQLite metadata record readiness blockers and disabled runtime flags only. External channels, notifications, push notifications, share links, webhook dispatch, relay runtime, hosted channels/routines, workers, schedulers, watchers, daemons, and runtime execution remain disabled. Slice O did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

### Phase 3 Slice P: Remote/Container/Cloud Execution Readiness — Metadata Only

Slice P adds deterministic metadata-only readiness surfaces for future remote/container/cloud execution. `/remote-readiness`, workspace inspection, workspace views, and optional SQLite metadata record readiness blockers and disabled runtime flags only. Remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, and runtime execution remain disabled. Slice P did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Status labels used by Raiker are `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Raiker now uses the real `httpx` package (`httpx.AsyncClient`) for async OpenAI-compatible provider transport. The repository-local `httpx.py` shim was removed and must not be restored. The OpenAI SDK and Pydantic are not used by this runtime.

Dependency decision: `httpx` is required and used. `fastapi` is deferred because this change does not implement a Raiker API/server surface. `langchain` is deferred because no governed adapter is implemented and it must not bypass Raiker tool, policy, approval, or event contracts. `llama-index` is deferred because no governed retrieval/indexing adapter is implemented and it must not bypass Raiker memory or provenance policy.

llama.cpp, Ollama, LM Studio, vLLM, generic OpenAI-compatible endpoints, and OpenRouter are represented through Raiker-owned async model-provider contracts. llama.cpp is the local-first native profile via the async OpenAI-compatible path. OpenRouter is hosted and policy-gated: it requires explicit hosted policy, egress and budget policy metadata, HTTPS, and a non-empty API key environment variable.

The deterministic provider is `test_only`; production gateways and normal CLI runtime do not fall back to it. If no real provider is configured or usable, runtime fails safely with a `no_real_model_provider_available`/provider-policy style error instead of silently switching to a mock or hosted backend. No silent local-to-hosted fallback is implemented. Provider support is offline-tested with `httpx.MockTransport`; real provider validation requires an operator-provided server or API key and was not performed here.

UI model selection is session-scoped and persisted in the workspace SQLite store. `/model use` writes the selected profile, `/model current` reads it, `/models` marks it, and reasoning controls are capability-gated. Private chain-of-thought is never exposed; any reasoning summary must be labeled as a summary, not raw reasoning. Model events use safe metadata only and must not include prompts, completions, stream chunks, Authorization headers, API keys, file contents, or tool outputs.
