# Raiker

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, or governed enterprise environment.

Raiker is not just a chatbot. Raiker is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, channels, checkpoints, execution environments, and rich interactive clients behind a security and privacy boundary.

The goal is simple:

```text
Just Ask
  -> interrupt, steer, or add context at any time
  -> Raiker gathers context
  -> Raiker plans when the task is complex or risky
  -> Raiker acts through approved tools, skills, plugins, hooks, channels, and subagents
  -> Raiker can answer side questions while work continues
  -> Raiker verifies the result
  -> Raiker records every action
  -> Raiker checkpoints and can rewind/fork work
  -> Raiker updates governed long-term memory only when appropriate
```

---

## Implementation Documentation Map

Raiker is intended to be implemented by AI coding agents, including smaller local or cloud models. The README explains the product vision, but builders must use the detailed documents below before writing code.

| Document | Purpose |
|---|---|
| [`docs/FEATURE_COVERAGE_MATRIX.md`](docs/FEATURE_COVERAGE_MATRIX.md) | Full platform feature coverage checklist and non-negotiable invariants. |
| [`docs/REFERENCE_PLATFORM_COMPATIBILITY.md`](docs/REFERENCE_PLATFORM_COMPATIBILITY.md) | Mapping from reference systems and concepts to Raiker specifications. |
| [`docs/LOCAL_LLM_BUILDER_GUIDE.md`](docs/LOCAL_LLM_BUILDER_GUIDE.md) | Operating rules, prompt template, and anti-drift checklist for Qwen/Gemma-class builder agents. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Implementation-ready architecture, component responsibilities, data flow, invariants, and Phase 1 boundaries. |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | Explicit contracts for prompt envelopes, events, plans, tool actions, policy decisions, tool results, responses, and checkpoints. |
| [`docs/RUNTIME_ORCHESTRATION_SPEC.md`](docs/RUNTIME_ORCHESTRATION_SPEC.md) | Deterministic runtime, background task, interrupt, side-question, verification, and orchestration rules. |
| [`docs/TOOLS_AND_PERMISSIONS_SPEC.md`](docs/TOOLS_AND_PERMISSIONS_SPEC.md) | Tool catalogue, broker lifecycle, approval modes, permission scopes, shell policy, and testing rules. |
| [`docs/HOOKS_SPEC.md`](docs/HOOKS_SPEC.md) | Hook lifecycle events, handlers, matchers, async hooks, decision authority, and hook security. |
| [`docs/PLUGIN_SYSTEM_SPEC.md`](docs/PLUGIN_SYSTEM_SPEC.md) | Plugin manifests, components, permissions, trust levels, lifecycle, and supply-chain controls. |
| [`docs/CHANNELS_SPEC.md`](docs/CHANNELS_SPEC.md) | Channel envelopes, pairing, sender trust, approval relay, attachments, and side-question routing. |
| [`docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`](docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) | Slash commands, command expansion, rich TUI, background work, side questions, approvals, and keyboard UX. |
| [`docs/CHECKPOINTING_AND_REWIND_SPEC.md`](docs/CHECKPOINTING_AND_REWIND_SPEC.md) | Checkpoint types, file snapshots, restore, fork, rewind UX, cleanup, and security. |
| [`docs/MEMORY_AND_CONTEXT_STRATEGY.md`](docs/MEMORY_AND_CONTEXT_STRATEGY.md) | Memory types, context bundles, retrieval, governance, correction, compaction, and poisoning controls. |
| [`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md) | Graph entities, relationships, codemap indexing, graph queries, staleness, and graph-context retrieval. |
| [`docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`](docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) | Model router, local inference, hosted providers, tool-call modes, streaming, context budgets, and privacy. |
| [`docs/EXECUTION_ENVIRONMENTS_SPEC.md`](docs/EXECUTION_ENVIRONMENTS_SPEC.md) | Local, worktree, Docker, SSH, cloud/GPU execution profiles, artifacts, and resource controls. |
| [`docs/OWASP_GENAI_SECURITY_MAPPING.md`](docs/OWASP_GENAI_SECURITY_MAPPING.md) | Mapping from GenAI/LLM risks to concrete Raiker controls and security tests. |
| [`docs/PHASE_1_MVP_BUILD_PLAN.md`](docs/PHASE_1_MVP_BUILD_PLAN.md) | Task-by-task Phase 1 build plan with acceptance criteria suitable for local LLM builders. |
| [`docs/ROADMAP_PHASE_2_TO_PHASE_5.md`](docs/ROADMAP_PHASE_2_TO_PHASE_5.md) | Full platform roadmap with phase boundaries from local MVP to governed enterprise/home-lab platform. |
| [`docs/SECURITY_AND_POLICY.md`](docs/SECURITY_AND_POLICY.md) | Phase 1 security model, policy matrix, path safety, shell approval, memory governance, and security tests. |
| [`docs/VERIFICATION_PLAN.md`](docs/VERIFICATION_PLAN.md) | Test strategy, expected event sequences, PR checklist, and local LLM evaluation scenarios. |
| [`docs/ADR_TEMPLATE.md`](docs/ADR_TEMPLATE.md) | Template for documenting design decisions instead of silently inventing behaviour. |

Recommended builder order:

```text
README.md
  -> FEATURE_COVERAGE_MATRIX.md
  -> REFERENCE_PLATFORM_COMPATIBILITY.md
  -> LOCAL_LLM_BUILDER_GUIDE.md
  -> ARCHITECTURE.md
  -> CONTRACTS.md
  -> SECURITY_AND_POLICY.md
  -> RUNTIME_ORCHESTRATION_SPEC.md
  -> TOOLS_AND_PERMISSIONS_SPEC.md
  -> HOOKS_SPEC.md
  -> PLUGIN_SYSTEM_SPEC.md
  -> CHANNELS_SPEC.md
  -> COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> CHECKPOINTING_AND_REWIND_SPEC.md
  -> MEMORY_AND_CONTEXT_STRATEGY.md
  -> GRAPH_MEMORY_AND_CODEMAP_SPEC.md
  -> MODEL_RUNTIME_AND_LOCAL_INFERENCE.md
  -> EXECUTION_ENVIRONMENTS_SPEC.md
  -> OWASP_GENAI_SECURITY_MAPPING.md
  -> PHASE_1_MVP_BUILD_PLAN.md
  -> ROADMAP_PHASE_2_TO_PHASE_5.md
  -> VERIFICATION_PLAN.md
```

---

## Why Raiker Exists

Modern AI coding agents are powerful, but they often have several gaps:

- They may rely heavily on cloud models.
- They may not preserve useful memory across long periods.
- They may lack strong security boundaries around shell, files, plugins, channels, and network access.
- They may not provide OS-like event logs for every action.
- They may treat terminal, chat, desktop, web, IDE, API, and external channels as separate products instead of equal clients.
- They may stop work when the user asks a side question instead of answering without corrupting the active task.
- They may drift when smaller local models are used to implement complex systems.

Raiker is designed to solve those problems with a **local-first, policy-gated, event-sourced, checkpointable agent runtime**.

---

## Core Principles

### 1. Local-first by default
Raiker should be able to run fully locally with local models such as llama.cpp, Ollama, or LM Studio. Remote models and cloud execution are optional and policy-controlled.

### 2. Equal-status clients
Raiker is not tied to one interface. CLI, rich TUI, desktop, web, IDE, voice, hotkeys, REST, webhooks, Slack, Teams, Discord, Signal, email, and future clients all use the same agent gateway.

### 3. Rich interruptible UX
Raiker must support background work, progress visibility, side questions, pause, cancel, steer, approve, deny, rewind, fork, and inspect without losing task state.

### 4. Security and privacy are architectural layers
Tool execution, memory writes, plugin actions, channel messages, remote calls, shell commands, and external execution all pass through policy.

### 5. OS-like event logging
Every prompt, model call, tool proposal, approval, denial, tool result, hook, plugin action, channel message, memory write, checkpoint, subagent event, verification result, and error is recorded.

### 6. Durable but governed memory
Raiker can remember across sessions, months, and years, but memory is governed by provenance, confidence, sensitivity, retention, trust score, approval state, correction, and deletion.

### 7. Documentation-first implementation
Every feature must have contracts, lifecycle, security rules, events, tests, and roadmap phase before implementation.

---

## High-Level User Flow

```text
User prompt or channel message
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

Raiker uses a nested control-boundary architecture:

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
```

The nested design is intentional:

- clients and channels never execute tools directly;
- event logging wraps meaningful activity;
- security and privacy mediate risky operations;
- the runtime reasons, plans, acts, verifies, checkpoints, and delegates;
- execution adapters run commands only through approved profiles;
- persistence stores logs, checkpoints, memory, vectors, graphs, and artifacts.

---

## Phase 1 MVP

Phase 1 builds only the secure local core:

- repository scaffold;
- contracts;
- event log writer;
- static policy engine;
- tool broker skeleton;
- read_file;
- list_directory;
- glob;
- grep;
- shell with approval;
- mock model provider;
- deterministic runtime state machine;
- CLI client;
- checkpoint stub;
- unit tests.

Future features are fully specified in docs but must be added according to the roadmap.

---

## Project Status

Raiker is currently at the architecture and implementation-blueprint stage. The next step is to implement the Phase 1 MVP from the implementation plan while preserving the full platform specifications and phase boundaries.
