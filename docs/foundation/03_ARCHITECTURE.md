> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (Phase 8 is the planned UI/client phase), the launchable local UIs are the plain local terminal client and the local web dashboard (Rich/native TUI, desktop, mobile, IDE, voice, browser-extension, and hosted/multi-user REST clients deferred to Phase 8), integrated real executors default enabled and governed per action, and no-executor capabilities remain disabled/fail-closed.

# 03 Architecture Document

## 1. Nested Boundary Architecture

The system should be described and implemented using nested trust and responsibility boundaries.

```text
Interface Boundary
  Event Logging Boundary
    Security and Privacy Boundary
      Agent Core Boundary
        Agent Loop
        Tool Broker
        Hooks
        Memory
        Model Router
        Execution Adapters
```

The visual diagram `nested_layered_architecture.png` follows this structure.

## 2. Boundary Responsibilities

### 2.1 Interface Boundary
Contains all equal-status clients:
- CLI.
- Chat: Signal, Slack, Teams, Discord, email.
- Rich TUI.
- Desktop.
- Web.
- IDE.
- Voice.
- Hotkeys.
- REST.
- Webhooks.

Responsibilities:
- Capture input.
- Display output.
- Show permission prompts.
- Stream events.
- Never execute tools directly.

### 2.2 Event Logging Boundary
Wraps everything below it. Every internal action emits AgentEvent.

Responsibilities:
- Append-only event log.
- Timeline replay.
- Audit export.
- Error and security event capture.
- Parent-child event correlation for tools and subagents.

### 2.3 Security and Privacy Boundary
Mediates all sensitive operations.

Responsibilities:
- Policy decisions.
- Secrets scanning.
- Prompt injection detection.
- Plugin trust verification.
- Egress control.
- Memory governance.
- Sandbox policy.
- Budget enforcement.

### 2.4 Agent Core Boundary
Contains the reasoning and orchestration services.

Components:
- Agent runtime loop.
- Context manager.
- Planner.
- Verifier.
- Subagent coordinator.
- Tool broker.
- Hook engine.
- Plugin manager.
- Memory service.
- Model router.
- Execution adapter registry.

## 3. Component-Level Architecture

### Agent Runtime
The agent runtime is a deterministic state machine. It cannot directly call shell, files, network, plugins, or memory writes. It must call Tool Broker, Memory Service, or Model Router through typed contracts.

### Tool Broker
The tool broker is the only path to tools. It validates arguments, requests policy decisions, executes tools, sanitises output, and records events.

### Hook Engine
The hook engine runs lifecycle automations. Hooks are not trusted by default. Hook outputs are labelled and logged.

### Memory Service
The memory service maintains profile, project, episodic, procedural, semantic, and graph memory. Memory writes require governance. Retrieval returns cited, bounded context.

### Model Router
The model router abstracts local and remote LLMs. It enforces privacy rules before sending content to remote providers.

### Execution Adapter Registry
Execution adapters are local, Docker, SSH, Daytona, Modal, and external hosting. Adapters never run without Policy Engine approval.

## 4. Layer-to-Code Mapping

```text
/apps/*                         -> Interface Boundary
/core/agent_gateway             -> Interface Boundary normalisation
/core/event_log                 -> Event Logging Boundary
/core/policy_engine             -> Security Boundary
/core/security/*                -> Security Boundary helpers
/core/agent_runtime             -> Agent Core
/core/tool_broker               -> Agent Core capability gateway
/core/memory_service            -> Agent Core memory
/core/model_router              -> Agent Core model routing
/core/deployment_adapters/*     -> Execution targets
/plugins, /skills, /agents      -> Extension surface
```

## 5. Data Flow

```text
Prompt -> Gateway -> Session -> Runtime -> Context Gathering -> Plan -> Policy -> Tool/Model/Memory/Subagent -> Verify -> Final -> Checkpoint -> Event Log -> Memory Governance
```

## 6. Do-Not-Build-Yet List

To prevent local models from hallucinating future-phase features, Phase 1 must not implement:
- full desktop UI,
- full web UI,
- real Slack/Signal integrations,
- real Daytona/Modal execution,
- plugin marketplace,
- autonomous browser control,
- full vector database,
- full graph database.

Instead Phase 1 may create interfaces and stubs for these capabilities.

## Non-Deviation Contract for Small/Local Models

The build agent must treat these documents as the source of truth. If implementation context conflicts with these documents, the build agent must stop and report the conflict instead of inventing a new architecture. The build agent must not introduce unplanned services, unplanned data stores, unplanned network calls, unplanned plugin permissions, or unplanned model providers without creating an ADR and asking for approval.

Mandatory behaviour for all implementation tasks:

1. Restate the exact requirement being implemented.
2. Identify the source document and section that authorises the work.
3. List files expected to change before editing.
4. Make the smallest reversible change.
5. Add or update tests.
6. Run verification.
7. Record residual risks and TODOs.
8. If unsure, ask a question or create a clearly labelled assumption. Do not hallucinate.

The intended implementation should work with constrained models such as a local 9B class model on a 16GB GPU. Therefore tasks must be small, explicit, schema-driven, and testable. Long, vague implementation leaps are forbidden.
