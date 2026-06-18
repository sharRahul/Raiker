# Raiker

## Raiker Description

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, mobile device, browser, chat workspace, or governed enterprise environment.

Raiker is not just a chatbot. It is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, channels, checkpoints, execution environments, approval previews, and rich interactive clients behind a security and privacy boundary.

Raiker installs one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` launches the configured local terminal client, which may be a Rich TUI, plain terminal client, or another configured terminal renderer. This command is one primary interface, not the canonical or exclusive interface.

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

| Area | Status | Notes |
|---|---|---|
| Phase 1 MVP runtime core | `implemented_verified` | Package scaffold, global `raiker` command, contracts, event log, SQLite bootstrap, static policy, tool broker, safe filesystem/search tools, approval-gated local actions, mock model provider, runtime state machine, terminal shell, and checkpoint stubs are present and covered by tests. |
| Phase 2 rich local workspace | `implemented_verified` | Task management, event viewer, checkpoint timeline, status/task/event/checkpoint/approval commands, side-question and interrupt contracts, approval inbox, governed file/git wrappers, local provider health-check, and memory candidate views are present and covered by tests. |
| Phase 3 local rich workspace/extensibility foundations | **Foundation only; Phase 3 is not complete** | Read-only workspace inspection/view surfaces, equal client contract parity, plugin manifest/registration planning, capability gates, graph/codemap dry-run planning, semantic memory review governance, approval-preview UX/contracts, Slice G metadata-only storage lifecycle preparation, Slice H metadata-only retention/cleanup-preview/approval-handoff planning, Slice I metadata-only lifecycle evidence/export/policy-simulation surfaces, and Slice J metadata-only graph/codemap readiness surfaces are present. Runtime plugin execution, graph/codemap indexing, indexing jobs, semantic/vector memory writes, embeddings, cleanup execution, approval relay, and durable approval-preview persistence remain disabled. |
| Phase 4 external channel / multi-agent / governed execution foundations | **Foundation only; Phase 4 is not complete** | Execution profiles, remote/container execution planning, subagent planning, external-channel activation status, and inspection commands are present. External transports, subagent spawning, multi-agent teams, remote execution, and container execution remain disabled. |
| GitHub Actions | Temporarily paused | Workflows are currently `workflow_dispatch` only because GitHub Actions quota is exhausted. Use [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md) until CI triggers are restored. |

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

### Phase 3 safe foundations only

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
/status
/tasks
/events
/checkpoints
/approvals
/approve <approval_id>
/deny <approval_id>
/memory
/semantic-memory
/memory-review
/memory-review --summary
/capabilities
/execution-profiles
/workspace
/workspace-view
/clients
/plugins
/plugin-plan <manifest_path>
/graph-status
/graph-plan
/approval-previews
/graph-approval-preview
/memory-approval-preview
/memory-approval-preview --summary
/approval-preview <preview_id>
/doctor
/channels
/models
/launch --provider mock --model mock-deterministic
/quit
```

Phase 3 and Phase 4 commands are inspection/planning/governance/preview surfaces unless explicitly documented otherwise. They must not execute plugins, activate channels, write semantic/vector memory, create embeddings, start graph indexing, persist executable approvals, spawn agents, or run remote/container commands.

---

## Developer Validation

GitHub Actions are temporarily paused because the Actions run limit/quota is exhausted. Until pull-request and push triggers are restored, local validation is mandatory before merge or direct main changes.

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
- statement that GitHub Actions are paused and must be re-enabled later.

---

## Builder Reading Order

Recommended builder flow:

```text
README.md
  -> docs/IMPLEMENTATION_STATUS.md
  -> docs/LOCAL_VALIDATION_GATE.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/04_ROADMAP.md
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
  -> docs/PHASE_1_MVP_BUILD_PLAN.md
  -> docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md
  -> docs/PHASE_3_BUILD_PLAN.md
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
| [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md) | Phase 1 build scope, task order, and acceptance criteria. |
| [`docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md`](docs/PHASE_2_RICH_LOCAL_WORKSPACE_BUILD_PLAN.md) | Phase 2 task decomposition and rich local workspace acceptance criteria. |
| [`docs/PHASE_3_BUILD_PLAN.md`](docs/PHASE_3_BUILD_PLAN.md) | Phase 3 local rich workspace, extensibility foundation, governance, and approval-preview plan. |
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
| [`config/model-profiles.json`](config/model-profiles.json) | Built-in model launch profile registry for mock, Ollama, llama.cpp, LM Studio, OpenAI-compatible, and hosted providers. |
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

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Phase 3 next slice definition audit

Slice J adds metadata-only/read-only graph/codemap readiness contracts, optional SQLite metadata persistence, workspace inspection/view summaries, and `/graph-readiness [--summary|--json]`. Slice J does not enable graph/codemap indexing, graph writes, codemap writes, indexing jobs, runtime execution, workers, schedulers, file watchers, daemons, semantic/vector memory writes, embeddings, approval relay runtime, plugin execution, MCP/LSP/plugin server startup, cleanup execution, rollback execution, remote/container/cloud execution, hosted routines, marketplace installs, push notifications, or share links. Phase 3 remains incomplete, and Phase 4 remains blocked from starting as a substitute.
