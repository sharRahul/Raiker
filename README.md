# Raiker

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, or governed enterprise environment.

Raiker is not just a chatbot. Raiker is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, channels, checkpoints, execution environments, and rich interactive clients behind a security and privacy boundary.

Raiker installs one human-facing global command named `raiker`.

```bash
raiker
```

Running `raiker` launches the Rich TUI. From the TUI, the user can submit normal prompts, ask side questions, approve or deny actions, launch or switch models, link channels, inspect memory, query graph context, open diagnostics, manage sessions, review checkpoints, and control tasks.

Provider-specific adapters may still map commands such as `ollama launch raiker --model <model>` into a Raiker model-launch request when the provider supports that style of extension, but the user-facing Raiker entry point remains `raiker`.

---

## Implementation Documentation Map

Raiker is intended to be implemented by local or cloud AI coding agents. Implementation is phased, but the specification is not vague. Every phase-scheduled feature must already have contracts, storage, runtime lifecycle, UI surface, security rules, events, tests, and failure handling.

| Document | Purpose |
|---|---|
| [`docs/FEATURE_COVERAGE_MATRIX.md`](docs/FEATURE_COVERAGE_MATRIX.md) | Full platform coverage checklist, phase placement, and non-negotiable invariants. |
| [`docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`](docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md) | Phase 1 to Phase 5 implementation blueprint and builder hand-off flow. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Phased architecture, component responsibilities, global command flow, and implementation boundaries. |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | Contracts for prompts, events, plans, actions, policy decisions, tool results, responses, and checkpoints. |
| [`docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`](docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md) | SQLite, JSONL, FTS5, vector metadata, graph tables, recursive CTEs, checkpoint and memory storage. |
| [`docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`](docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) | Global `raiker` command, TUI actions, slash commands, model launch, side questions, approvals, keyboard UX. |
| [`docs/UI_UX_DESIGN_SPEC.md`](docs/UI_UX_DESIGN_SPEC.md) | Rich TUI, status bar, Desktop UI, Web UI, Dashboard, IDE, Voice UI, and shared UX design. |
| [`docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`](docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) | Model profiles, local providers, hosted policy gates, launch contract, streaming, tool-call modes. |
| [`config/model-profiles.json`](config/model-profiles.json) | Built-in model launch profile registry for mock, Ollama, llama.cpp, LM Studio, OpenAI-compatible, hosted providers. |
| [`docs/CHANNELS_SPEC.md`](docs/CHANNELS_SPEC.md) | Channel connector profiles, pairing, sender trust, routing, side questions, approval relay, link/unlink lifecycle. |
| [`config/channel-connectors.json`](config/channel-connectors.json) | Built-in connector profile registry used by UI listing/linking flows before implementation wiring. |
| [`docs/MEMORY_AND_CONTEXT_STRATEGY.md`](docs/MEMORY_AND_CONTEXT_STRATEGY.md) | Working, profile, project, episodic, procedural, semantic, graph, eidetic observation, and gist memory. |
| [`docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`](docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md) | Eidetic-style raw observations, gist memory, retention, exact replay, skill learning, and self-improvement controls. |
| [`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md) | Graph entities, relationships, codemap indexing, graph queries, staleness, and graph-context retrieval. |
| [`docs/RUNTIME_ORCHESTRATION_SPEC.md`](docs/RUNTIME_ORCHESTRATION_SPEC.md) | Runtime state machine, background tasks, interrupts, side questions, verification, and deterministic event ordering. |
| [`docs/TOOLS_AND_PERMISSIONS_SPEC.md`](docs/TOOLS_AND_PERMISSIONS_SPEC.md) | Tool catalogue, broker lifecycle, approvals, permission scopes, command policy, and testing rules. |
| [`docs/HOOKS_SPEC.md`](docs/HOOKS_SPEC.md) | Hook lifecycle events, handlers, matchers, async hooks, decision authority, and hook security. |
| [`docs/PLUGIN_SYSTEM_SPEC.md`](docs/PLUGIN_SYSTEM_SPEC.md) | Plugin manifests, components, permissions, trust levels, lifecycle, skills, channels, and supply-chain controls. |
| [`docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`](docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md) | Subagents, multi-agent teams, bounded delegation, side questions, and parent verification. |
| [`docs/EXECUTION_ENVIRONMENTS_SPEC.md`](docs/EXECUTION_ENVIRONMENTS_SPEC.md) | Local, worktree, container, SSH, VPS, Kubernetes, cloud/GPU execution profiles, artifacts, and resource controls. |
| [`docs/OWASP_GENAI_SECURITY_MAPPING.md`](docs/OWASP_GENAI_SECURITY_MAPPING.md) | GenAI/LLM risk mapping, controls, and security test matrix. |
| [`docs/REFERENCE_PLATFORM_COMPATIBILITY.md`](docs/REFERENCE_PLATFORM_COMPATIBILITY.md) | Mapping to Claude Code, OpenClaw, Hermes, memory, graph, local inference, and security reference concepts. |
| [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md) | Task-by-task Phase 1 build plan with acceptance criteria. |
| [`docs/PHASE_1_ALIGNMENT_ADDENDUM.md`](docs/PHASE_1_ALIGNMENT_ADDENDUM.md) | Phase 1 addendum for global command, registries, and phase-scheduled feature compatibility. |
| [`docs/ROADMAP_PHASE_2_TO_PHASE_5.md`](docs/ROADMAP_PHASE_2_TO_PHASE_5.md) | Phase-scheduled roadmap from local MVP to governed enterprise/home-lab platform. |
| [`docs/SECURITY_AND_POLICY.md`](docs/SECURITY_AND_POLICY.md) | Phase 1 security model, policy matrix, path safety, command approval, memory governance, security tests. |
| [`docs/VERIFICATION_PLAN.md`](docs/VERIFICATION_PLAN.md) | Validation commands, event sequences, PR checklist, local/cloud builder evaluation scenarios. |
| [`docs/LOCAL_LLM_BUILDER_GUIDE.md`](docs/LOCAL_LLM_BUILDER_GUIDE.md) | Operating rules, prompt template, and anti-drift checklist for local/cloud builder agents. |
| [`docs/ADR_TEMPLATE.md`](docs/ADR_TEMPLATE.md) | Template for documenting design decisions instead of silently inventing behaviour. |

---

## Builder Reading Flow

A builder model must use this flow before coding:

```text
README.md
  -> docs/FEATURE_COVERAGE_MATRIX.md
  -> docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/ARCHITECTURE.md
  -> docs/CONTRACTS.md
  -> docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/SECURITY_AND_POLICY.md
  -> task-specific spec
  -> docs/VERIFICATION_PLAN.md
```

For every task, the builder must identify the phase, task ID, files to change, contracts affected, storage affected, events emitted, policy gates, UI surface, tests, and documentation updates.

---

## Core Principles

### 1. Local-first by default
Raiker should run fully locally with local models such as llama.cpp, Ollama, or LM Studio. Remote models and cloud execution are optional and policy-controlled.

### 2. Equal-status clients
CLI, Rich TUI, Desktop, Web, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Mobile Companion, and other phase-scheduled clients all use the same agent gateway.

### 3. Rich interruptible UX
Raiker must support background work, progress visibility, side questions, pause, cancel, steer, approve, deny, rewind, fork, and inspect without losing task state.

### 4. Concrete storage design
Raiker uses local storage with SQLite for state/search/index metadata, JSONL for append-only event logs, checkpoint manifests and file snapshots for recovery, local vector metadata, graph tables, and recursive CTEs.

### 5. Governed memory and learning
Raiker memory includes candidates, working context, profile/project memory, episodic/procedural memory, eidetic observations, gist memory, semantic memory, graph memory, and self-improving skills, all governed by provenance, confidence, sensitivity, retention, approval, correction, and deletion.

### 6. Security and privacy are architectural layers
Tool execution, memory writes, plugin actions, channel messages, remote calls, local commands, and external execution all pass through policy.

### 7. OS-like event logging
Every prompt, model call, tool proposal, approval, denial, tool result, hook, plugin action, channel message, memory write, checkpoint, subagent event, verification result, and error is recorded.

---

## High-Level User Flow

```text
User runs `raiker`
  -> Rich TUI opens
  -> user submits prompt, slash command, side question, approval, or model/channel action
  -> client/channel envelope
  -> agent gateway
  -> session manager
  -> runtime orchestration
  -> context gathering
  -> planning
  -> policy review
  -> hooks
  -> tool/model/memory/subagent/channel action
  -> verification
  -> response or side answer
  -> checkpoint
  -> event log
  -> governed memory review
```

---

## Main Architecture

```text
Interface and Channel Layer
  Event Logging Layer
    Security and Privacy Layer
      Agent Core
        Agent Gateway
        Session Manager
        Runtime Orchestrator
        Tool Broker
        Hook Engine
        Plugin Manager
        Channel Manager
        Memory Service
        Graph/Codemap Service
        Model Router
        Checkpoint Service
        Subagent Orchestrator
        Execution Adapters
        SQLite State Store
```

---

## Phase 1 MVP

Phase 1 builds the secure local core:

- global `raiker` TUI launch command;
- repository scaffold;
- contracts;
- event log writer;
- static policy engine;
- SQLite bootstrap;
- connector profile registry;
- model profile registry;
- tool broker skeleton;
- read_file;
- list_directory;
- glob;
- grep;
- local command proposal with approval;
- mock model provider;
- deterministic runtime state machine;
- Rich TUI shell with prompt input and status panels;
- checkpoint stub;
- unit tests.

Phase-scheduled features are fully specified in the docs listed above and must be implemented according to the phase blueprint.

---

## Project Status

Raiker is currently at the architecture and implementation-blueprint stage. The next step is to implement the Phase 1 MVP from the implementation plan while preserving the full platform specifications and phase boundaries.
