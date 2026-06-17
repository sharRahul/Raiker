# Raiker

## Raiker Description

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, mobile device, browser, chat workspace, or governed enterprise environment.

Raiker is not just a chatbot. It is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, channels, checkpoints, execution environments, and rich interactive clients behind a security and privacy boundary.

Raiker installs one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` launches the configured local terminal client, which may be a Rich TUI, plain terminal client, or another configured terminal renderer. This command is one primary interface, not the canonical or exclusive interface.

Raiker does **not** have one privileged human interface. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Why Raiker

Most AI coding assistants and local agent tools focus on one interface, one model path, or one execution style. Raiker is designed as a governed agent operating layer where every interface talks through the same runtime, contracts, policy checks, event log, storage layer, and checkpoint flow.

Raiker exists to provide:

- local-first operation by default;
- equal-status primary interfaces instead of one privileged chat or terminal UI;
- explicit contracts for prompts, UI actions, channel messages, tools, policy decisions, events, responses, and checkpoints;
- policy-gated tool execution;
- append-only event logging;
- SQLite-backed state, search, registry, memory, graph, approval, and checkpoint metadata;
- model-provider abstraction for local and hosted providers;
- governed memory and context handling;
- interruptible work with side questions, approvals, pause/cancel/steer, and checkpoints;
- a phased implementation path that local or cloud builder agents can follow without inventing architecture.

---

## What Raiker Does

Raiker provides the architecture and implementation plan for a local-first agent platform that can:

- receive prompts from any enabled primary interface;
- normalise requests into shared envelopes;
- route work through an Agent Gateway;
- create and resume sessions;
- run a deterministic runtime state machine;
- gather context from approved sources;
- create or skip plans based on task risk;
- review every proposed action through policy;
- execute safe tools through a Tool Broker;
- pause for approval before risky or local-machine-affecting actions;
- call deterministic mock models in Phase 1 and local model providers in later phases;
- write append-only JSONL events;
- index events and state in SQLite;
- create checkpoint stubs after completed turns;
- list model and connector registries before full provider/channel wiring;
- preserve equal-interface contracts for terminal, desktop, web, mobile, IDE, voice, chat, REST, webhook, browser-extension, and channel clients.

### Versioning

Raiker starts at package/application version `0.0.0`. Patch updates must progress through `0.0.1` to `0.0.99` before the project is bumped to `0.1.0`.

### Phase 1 MVP

Phase 1 builds the secure local core and the first local terminal client while preserving equal-interface contracts:

- global `raiker` terminal entry command;
- repository scaffold;
- contracts;
- event log writer;
- static policy engine;
- SQLite bootstrap;
- connector profile registry;
- model profile registry;
- tool broker skeleton;
- `read_file`;
- `list_directory`;
- `glob`;
- `grep`;
- local command/action proposal with approval;
- mock model provider;
- deterministic runtime state machine;
- first local terminal client shell with prompt input and status panels;
- checkpoint stub;
- unit and integration tests.

Raiker now contains a Phase 1 runtime-core implementation on `main`. Continue to use [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md) as the single source of truth for Phase 1 scope and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) as the status ledger.

---

## Quick Start

### Current repository status

Raiker contains the initial Phase 1 MVP runtime core. Check [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) before continuing work, and do not mark any capability `implemented_verified` unless its tests exist and the relevant validation has passed.

Start by reading the Phase 1 plan:

```bash
cat docs/PHASE_1_MVP_BUILD_PLAN.md
```

Recommended builder flow:

```text
README.md
  -> docs/IMPLEMENTATION_STATUS.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
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
  -> docs/RUNTIME_ORCHESTRATION_SPEC.md
  -> docs/TOOLS_AND_PERMISSIONS_SPEC.md
  -> docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md
  -> docs/MODEL_PROVIDER_CONTRACT.md
  -> docs/CHANNELS_SPEC.md
  -> docs/UI_UX_DESIGN_SPEC.md
  -> docs/MEMORY_AND_CONTEXT_STRATEGY.md
  -> docs/MEMORY_GOVERNANCE_RULES.md
  -> docs/PLUGIN_SYSTEM_SPEC.md
  -> docs/PLUGIN_MANIFEST_SCHEMA.md
  -> docs/ACCEPTANCE_TESTS_BY_PHASE.md
  -> docs/REFERENCE_REQUIREMENTS_MATRIX.md
  -> docs/VERIFICATION_PLAN.md
  -> config/model-profiles.json
  -> config/channel-connectors.json
```

After Phase 1 is implemented, the expected local entry point is:

```bash
raiker
```

Expected Phase 1 validation commands:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Expected Phase 1 manual terminal actions:

```text
normal prompt: Hello Raiker
normal prompt: List files in this project
/launch --provider mock --model mock-deterministic
/channels
/models
```

If the global `raiker` command is not configured during early bootstrapping, module-based commands may be used temporarily, but the final Phase 1 deliverable must expose `raiker`.

---

## CLI Install

### macOS/Linux/WSL/Git Bash

From a local checkout:

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
raiker
```

During early bootstrapping, if the console script is not installed yet, use the module entry point documented by the active implementation task and report that as temporary.

### Developer validation

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
```

---

## What You Get

When Phase 1 is complete, Raiker should provide:

- a global `raiker` command;
- a first local terminal client shell;
- shared contracts for prompts, UI actions, channel messages, events, tools, policy decisions, results, responses, and checkpoints;
- deterministic runtime transitions;
- safe filesystem/search tools;
- approval-gated local action proposals;
- a static policy engine;
- append-only JSONL event logs;
- SQLite runtime state and indexes;
- checkpoint stubs;
- deterministic mock model provider;
- model and connector registries;
- disabled/listable phase-scheduled connector profiles;
- tests that prove the local core works and that the equal-interface invariant is preserved.

Later phases add rich workspace UX, local model providers, hooks, memory expansion, desktop/web/mobile/dashboard clients, plugins, graph/codemap, channel connectors, multi-agent teams, remote/container execution, and governed enterprise/home-lab controls.

---

## Documentation

Raiker is intended to be implemented by local or cloud AI coding agents. Implementation is phased, but the specification is not vague. Every phase-scheduled feature must already have contracts, storage, runtime lifecycle, UI surface, security rules, events, tests, and failure handling.

### Core implementation docs

| Document | Purpose |
|---|---|
| [`docs/FEATURE_COVERAGE_MATRIX.md`](docs/FEATURE_COVERAGE_MATRIX.md) | Full platform coverage checklist, phase placement, and non-negotiable invariants. |
| [`docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`](docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md) | Phase 1 to Phase 5 implementation blueprint and builder hand-off flow. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Phased architecture, component responsibilities, equal-interface flow, and implementation boundaries. |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | Contracts for prompts, events, plans, actions, policy decisions, tool results, responses, and checkpoints. |
| [`docs/API_AND_CONTRACT_SCHEMAS.md`](docs/API_AND_CONTRACT_SCHEMAS.md) | Strict schema reference for IDs, client metadata, prompts, UI/channel actions, tools, approvals, responses, and checkpoints. |
| [`docs/EVENT_CATALOG.md`](docs/EVENT_CATALOG.md) | Canonical event names, payload expectations, ordering, actors, and event indexing rules. |
| [`docs/RUNTIME_STATE_MACHINE.md`](docs/RUNTIME_STATE_MACHINE.md) | Legal Phase 1 runtime transitions, invalid transitions, guards, state events, and state-machine tests. |
| [`docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`](docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md) | SQLite, JSONL, FTS5, vector metadata, graph tables, recursive CTEs, checkpoint and memory storage. |
| [`docs/SECURITY_AND_POLICY.md`](docs/SECURITY_AND_POLICY.md) | Phase 1 security model, policy matrix, path safety, command approval, memory governance, security tests. |
| [`docs/RUNTIME_ORCHESTRATION_SPEC.md`](docs/RUNTIME_ORCHESTRATION_SPEC.md) | Runtime orchestration, background tasks, interrupts, side questions, verification, and deterministic event ordering. |
| [`docs/TOOLS_AND_PERMISSIONS_SPEC.md`](docs/TOOLS_AND_PERMISSIONS_SPEC.md) | Tool catalogue, broker lifecycle, approvals, permission scopes, command policy, and testing rules. |
| [`docs/VERIFICATION_PLAN.md`](docs/VERIFICATION_PLAN.md) | Validation commands, event sequences, PR checklist, local/cloud builder evaluation scenarios. |
| [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md) | Single source of truth for Phase 1 build scope, task order, and acceptance criteria. |

### Builder-proof control docs

| Document | Purpose |
|---|---|
| [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) | Status ledger for specified, implemented, disabled, blocked, and out-of-scope capabilities. |
| [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md) | Dependency-safe implementation order and PR completion gate. |
| [`docs/ACCEPTANCE_TESTS_BY_PHASE.md`](docs/ACCEPTANCE_TESTS_BY_PHASE.md) | Phase-by-phase acceptance tests required before a feature can be called complete. |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Assets, trust boundaries, threats, controls, and threat-driven tests. |
| [`docs/NON_GOALS_AND_BOUNDARIES.md`](docs/NON_GOALS_AND_BOUNDARIES.md) | Explicit product, phase, architecture, storage, model, memory, and security boundaries. |
| [`docs/REFERENCE_REQUIREMENTS_MATRIX.md`](docs/REFERENCE_REQUIREMENTS_MATRIX.md) | Mapping from reference agent-platform capabilities to Raiker contracts, events, storage, policy, tests, and phases. |

### Interface, model, channel, and UX docs

| Document | Purpose |
|---|---|
| [`docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`](docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) | Global `raiker` command, equal primary interfaces, TUI actions, slash commands, model launch, side questions, approvals, keyboard UX. |
| [`docs/UI_UX_DESIGN_SPEC.md`](docs/UI_UX_DESIGN_SPEC.md) | Shared UX, Rich TUI, configurable status bar, optional panels, Desktop UI, Web UI, Dashboard, IDE, Voice UI, Apple/Android mobile apps, and channel clients. |
| [`docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`](docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) | Model profiles, local providers, hosted policy gates, launch contract, streaming, tool-call modes. |
| [`docs/MODEL_PROVIDER_CONTRACT.md`](docs/MODEL_PROVIDER_CONTRACT.md) | Provider adapter interface, model request/response schema, provider policy, events, and Phase 1 mock-provider acceptance. |
| [`config/model-profiles.json`](config/model-profiles.json) | Built-in model launch profile registry for mock, Ollama, llama.cpp, LM Studio, OpenAI-compatible, and hosted providers. |
| [`docs/CHANNELS_SPEC.md`](docs/CHANNELS_SPEC.md) | Channel connector profiles, pairing, sender trust, routing, side questions, approval relay, link/unlink lifecycle. |
| [`config/channel-connectors.json`](config/channel-connectors.json) | Built-in connector profile registry used by UI listing/linking flows before implementation wiring. |

### Memory, graph, plugins, execution, and roadmap docs

| Document | Purpose |
|---|---|
| [`docs/MEMORY_AND_CONTEXT_STRATEGY.md`](docs/MEMORY_AND_CONTEXT_STRATEGY.md) | Working, profile, project, episodic, procedural, semantic, graph, eidetic observation, and gist memory. |
| [`docs/MEMORY_GOVERNANCE_RULES.md`](docs/MEMORY_GOVERNANCE_RULES.md) | Memory candidate/record schemas, sensitivity levels, write/use/poisoning controls, and memory-governance tests. |
| [`docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`](docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md) | Eidetic-style raw observations, gist memory, retention, exact replay, skill learning, and self-improvement controls. |
| [`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md) | Graph entities, relationships, codemap indexing, graph queries, staleness, and graph-context retrieval. |
| [`docs/HOOKS_SPEC.md`](docs/HOOKS_SPEC.md) | Hook lifecycle events, handlers, matchers, async hooks, decision authority, and hook security. |
| [`docs/PLUGIN_SYSTEM_SPEC.md`](docs/PLUGIN_SYSTEM_SPEC.md) | Plugin manifests, components, permissions, trust levels, lifecycle, skills, channels, and supply-chain controls. |
| [`docs/PLUGIN_MANIFEST_SCHEMA.md`](docs/PLUGIN_MANIFEST_SCHEMA.md) | Strict plugin manifest schema, required fields, permission declaration rules, trust rules, events, and tests. |
| [`docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`](docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md) | Subagents, multi-agent teams, bounded delegation, side questions, and parent verification. |
| [`docs/EXECUTION_ENVIRONMENTS_SPEC.md`](docs/EXECUTION_ENVIRONMENTS_SPEC.md) | Local, worktree, container, SSH, VPS, Kubernetes, cloud/GPU execution profiles, artifacts, and resource controls. |
| [`docs/OWASP_GENAI_SECURITY_MAPPING.md`](docs/OWASP_GENAI_SECURITY_MAPPING.md) | GenAI/LLM risk mapping, controls, and security test matrix. |
| [`docs/REFERENCE_PLATFORM_COMPATIBILITY.md`](docs/REFERENCE_PLATFORM_COMPATIBILITY.md) | Mapping to Claude Code, OpenClaw, Hermes, memory, graph, local inference, and security reference concepts. |
| [`docs/ROADMAP_PHASE_2_TO_PHASE_5.md`](docs/ROADMAP_PHASE_2_TO_PHASE_5.md) | Phase-scheduled roadmap from local MVP to governed enterprise/home-lab platform. |
| [`docs/LOCAL_LLM_BUILDER_GUIDE.md`](docs/LOCAL_LLM_BUILDER_GUIDE.md) | Operating rules, prompt template, and anti-drift checklist for local/cloud builder agents. |
| [`docs/ADR_TEMPLATE.md`](docs/ADR_TEMPLATE.md) | Template for documenting design decisions instead of silently inventing behaviour. |

---

## Support

Raiker is currently in Phase 1 MVP runtime-core implementation and validation.

For now:

- use the documentation map above as the source of truth;
- open a GitHub issue for bugs, documentation gaps, implementation questions, or scope conflicts;
- include the relevant phase, task ID, file path, expected behaviour, and actual behaviour;
- for Phase 1 work, reference [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md);
- do not treat undocumented behaviour as approved implementation scope.

If a builder finds conflicting instructions, it should stop, report the conflict, and update the relevant spec before implementing behaviour that could affect architecture, security, storage, policy, or interface parity.
