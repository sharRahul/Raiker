# Raiker Architecture Blueprint

Raiker is a local-first AI agent platform. It is designed as an operating layer for prompts, models, tools, policy, memory, plugins, hooks, subagents, channels, user interfaces, storage, search, graph context, checkpoints, and execution environments.

This document turns the high-level README into implementation-ready architecture. Implementation is phased, but the architecture is fully specified now.

---

## System Goals

Raiker must provide:

1. one gateway for all clients and channels;
2. deterministic runtime state transitions;
3. policy-gated tool execution;
4. append-only event logging;
5. governed memory writes and memory retrieval;
6. model-provider abstraction for local and hosted providers;
7. safe local-first execution;
8. resumable checkpoints and rewind/fork flows;
9. testable contracts;
10. SQLite-backed state, memory, graph, and search metadata;
11. rich interruptible UX across CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and Channels;
12. equal primary-interface status for every implemented and enabled client;
13. small-model-friendly implementation boundaries.

No user interface is architecturally primary over another. Interface implementation can be phased, but phase order must not create privileged runtime paths.

---

## Phased Boundaries And Implementation Plan

Raiker uses phased delivery. A later build phase does **not** mean vague design. Every phase-listed feature must already have:

1. user experience;
2. contract/schema;
3. storage;
4. runtime lifecycle;
5. security policy;
6. events;
7. tests;
8. UI surface;
9. failure handling;
10. migration or upgrade impact.

Phase boundaries exist to control implementation order, not to hide missing design or define interface priority.

| Phase | Build focus | Required architectural state |
|---|---|---|
| Phase 1 | Secure Local Interface Core | Contracts, gateway, sessions, runtime, policy, broker, event log, SQLite bootstrap, first local terminal client, mock model, checkpoint stub, equal-interface contracts. |
| Phase 2 | Rich Local Workspace | Full terminal/TUI panels, background tasks, side questions, full checkpoints/rewind, local model providers, hooks, approved project/profile memory. |
| Phase 3 | Desktop/Web/Mobile/Plugin/Graph Platform | Desktop UI, Web UI, Dashboard, Apple mobile app, Android mobile app, plugin manager, semantic search, graph/codemap, REST API, worktree isolation. |
| Phase 4 | Channels/Multi-Agent/Remote Execution | Channel connectors, subagents, agent teams, container/remote profiles, voice/hotkeys/browser extension, chat/email clients. |
| Phase 5 | Governed Enterprise/Home-Lab Platform | Managed policies, multi-user governance, signed plugins, event integrity, audit export, cloud/GPU budgets, deployment operations. |

### Phase 1 Exclusions Are Implementation Exclusions Only

Phase 1 does not wire these features into active behaviour: Desktop UI, Web UI, Dashboard, Apple mobile app, Android mobile app, plugin marketplace, autonomous multi-agent teams, durable vector/graph memory writes, cloud deployment, container/remote execution, external messaging channels, voice channels, or production hosted-model billing controls.

However, Phase 1 must still preserve the contracts, registries, storage hooks, policy boundaries, and extension points that make those phase-scheduled features implementable without redesign. Those phase-scheduled interfaces are equal primary interfaces once implemented and enabled.

---

## Layered Architecture

```text
Interface and Channel Layer
  -> Agent Gateway
    -> Session Manager
      -> Runtime Orchestrator
        -> Context Gatherer
        -> Planner
        -> Policy Engine
        -> Tool Broker
        -> Hook Engine
        -> Plugin Manager
        -> Channel Manager
        -> Model Router
        -> Memory Service
        -> Graph/Codemap Service
        -> Verifier
        -> Checkpoint Service
        -> Execution Adapter Registry
      -> Event Log
      -> SQLite State Store
```

Every client talks to the gateway. No client can call tools directly. No client gets a private bypass path because it was implemented earlier or has a richer UI.

---

## Component Responsibilities

### Agent Gateway

Responsible for accepting `PromptEnvelope`, `UIActionEnvelope`, and `ChannelMessageEnvelope` input from any enabled primary interface, validating request shape, assigning request IDs if missing, forwarding requests to the session manager, and returning an `AgentEvent` stream or final `AgentResponse` to the originating interface.

Must not execute tools, call models directly, write memory directly, bypass event logging, or accept channel approval without approval binding.

### Session Manager

Responsible for creating sessions, loading session state from SQLite and event logs, preserving turn order, attaching checkpoints to sessions, supporting resume/fork, closing completed turns, and reconstructing active task state after restart.

### Runtime Orchestrator

Responsible for the deterministic task loop:

```text
RECEIVED
  -> NORMALISED
  -> CLASSIFIED
  -> CONTEXT_READY
  -> PLAN_READY or PLAN_SKIPPED
  -> POLICY_REVIEWED
  -> EXECUTING or WAITING_FOR_APPROVAL or DENIED
  -> OBSERVING
  -> VERIFYING
  -> MEMORY_REVIEWING
  -> RESPONDING
  -> CHECKPOINTING
  -> CLOSED
```

The runtime must expose state transitions in logs, SQLite state, interface status surfaces, and tests.

### Context Gatherer

Responsible for gathering only approved context sources: current prompt, session history, explicitly attached files, permitted memory records, memory candidates, graph/codemap query results, semantic search results permitted by sensitivity policy, tool-read results approved by policy, and channel messages with provenance and trust labels.

### Planner

Responsible for deciding whether a plan is needed. A plan is required when a task has more than one action, writes files, uses a local command, changes code, uses network, creates a background task, uses a linked channel, spawns a subagent, or could affect data, cost, security, or privacy.

### Policy Engine

Responsible for evaluating proposed actions before execution. Phase 1 implements `allow`, `deny`, and `needs_approval`; phase-scheduled policy decisions are defined in `docs/TOOLS_AND_PERMISSIONS_SPEC.md`.

### Tool Broker

Responsible for all tool execution. Phase 1 tools are `read_file`, `list_directory`, `glob`, `grep`, and `shell` with approval requirement. Phase-scheduled tools are fully catalogued in `docs/TOOLS_AND_PERMISSIONS_SPEC.md` and must route through the same broker when implemented.

### Hook Engine

Responsible for lifecycle hooks. Phase 1 keeps the interface boundary; Phase 2 wires hook execution. Hook contracts, matchers, scopes, event names, decision authority, async hooks, and tests are specified in `docs/HOOKS_SPEC.md`.

### Plugin Manager

Responsible for plugin registry, manifests, trust levels, permission diff, component registration, and enable/disable lifecycle. Phase 1 keeps the directory/config boundary; Phase 3 wires plugin execution according to `docs/PLUGIN_SYSTEM_SPEC.md`.

### Channel Manager

Responsible for connector profile registry, channel linking, pairing, sender trust, message normalisation, side-question routing, approval relay, and channel events. Phase 1 ships connector profiles as configuration; phase-scheduled connectors are linked and wired according to `docs/CHANNELS_SPEC.md` and `config/channel-connectors.json`.

### Model Router

Responsible for abstracting model providers. The deterministic `mock` provider is the offline/test fallback; the **llama.cpp server is the native default local backend** (`raiker/models/providers/llama_cpp_server.py`), selected automatically when its `/health` endpoint is reachable. LM Studio and OpenAI-compatible local endpoints have profiles but are not yet wired; vLLM is a later high-throughput GPU option. Hosted providers are policy-controlled and documented in `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`.

### Event Log

Responsible for append-only JSONL events and SQLite event indexes. Every event must include event ID, timestamp, session ID, event type, actor, payload, and schema version.

### State Store

Responsible for SQLite-backed state, indexes, memory metadata, graph metadata, approvals, tool actions, checkpoints, connector profiles, plugin registry, model profiles, and dashboard metrics. The concrete schema is defined in `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`.

### Checkpoint Service

Responsible for storing resumable state after turns and snapshots before risky file actions. Phase 1 writes basic checkpoint manifests. Phase 2 expands restore, rewind, fork, compare, and file snapshots according to `docs/CHECKPOINTING_AND_REWIND_SPEC.md`.

### Memory Governance

Responsible for memory candidates, durable memory records, provenance, sensitivity, confidence, correction, forgetting, semantic search, and graph-linked memory. Phase 1 creates candidates and SQLite memory tables. Phase 2 writes approved profile/project/episodic/procedural memory. Phase 3 adds semantic/vector and graph-backed retrieval.

---

## Data Flow For Any Interface Prompt

```text
1. User acts through any enabled primary interface.
2. Interface captures prompt, command/action, side question, approval choice, model action, channel action, memory action, graph query, checkpoint action, diagnostics action, or task control.
3. Interface builds a PromptEnvelope, UIActionEnvelope, or ChannelMessageEnvelope with client metadata.
4. AgentGateway validates envelope.
5. SessionManager opens or creates session.
6. Runtime logs prompt_received, ui_action_received, or channel_message_received.
7. Runtime classifies intent and risk.
8. Runtime gathers context.
9. Runtime creates or skips plan.
10. Runtime proposes actions.
11. PolicyEngine reviews actions.
12. ToolBroker executes approved actions or pauses for approval.
13. Runtime verifies result.
14. Runtime updates event stream and interface state.
15. CheckpointService writes checkpoint.
16. EventLogWriter records all events.
17. SQLite state store indexes session, turn, events, task, action, approval, and checkpoint metadata.
18. Response, side answer, task update, approval request, or diagnostic result is returned to the originating interface and any subscribed linked interfaces allowed by policy.
```

---

## Global Command And Local Terminal Launch Architecture

Raiker must install one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` launches the configured local terminal client. The default terminal client may be a Rich TUI, but it is not the canonical or exclusive human interface.

Required terminal actions:

```text
normal prompt: "List files in this project"
side question: ? What is it doing now?
model launch: /launch --provider llama.cpp --model local-gguf
model launch: /launch --provider lm-studio --model local-model
model launch: /launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
models: /models
channels: /channels
sessions: /sessions
checkpoints: /checkpoints
doctor: /doctor
```

Every terminal action above must have an equivalent action contract available to Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, chat channels, Email, Browser Extension, Apple mobile app, Android mobile app, and Mobile Companion when those interfaces are implemented and enabled.

Provider-specific convenience launchers may delegate into a Raiker model-launch request when that platform supports such extension behaviour. Documentation and tests must keep the equal-interface invariant intact.

---

## Recommended Phase 1 Technology Choices

These choices minimise drift and complexity while preserving the full architecture.

- Language: Python 3.11 or 3.12.
- Package manager: uv or pip with a lockfile.
- Terminal client: Textual, Rich, or a minimal dependency-free terminal renderer. Prefer the smallest implementation that supports panels and input safely.
- Data validation: Pydantic or dataclasses. Use one consistently.
- Tests: pytest.
- Event log: JSONL files plus SQLite indexes.
- Policy config: JSON or YAML. Prefer JSON if avoiding dependencies.
- Storage: SQLite database plus JSONL/checkpoint/artifact files under `.raiker/`.

---

## Required Directory Shape For Phase 1

```text
raiker/
  cli/
    main.py
    commands.py
  contracts/
  gateway/
  sessions/
  runtime/
  policy/
  tools/
  models/
  events/
  storage/
  checkpoints/
  memory/
  channels/
  tui/
apps/
  cli/
    main.py
docs/
config/
  channel-connectors.json
  model-profiles.json
tests/
  test_contracts.py
  test_event_log.py
  test_policy_engine.py
  test_tool_broker.py
  test_runtime_state_machine.py
  test_terminal_client_smoke.py
  test_storage_sqlite.py
  test_channel_connector_registry.py
```

---

## Architectural Invariants

These must be tested:

1. A prompt always produces at least `prompt_received` and `turn_closed` events.
2. A shell action cannot run without policy review.
3. A denied action is logged and not executed.
4. A risky action requiring approval pauses instead of executing.
5. Runtime state transitions happen in valid order.
6. A checkpoint is written after a completed turn.
7. Every enabled primary interface uses the same gateway, contracts, policy, event log, and session state.
8. The model router can use a deterministic mock provider.
9. The global `raiker` command launches the configured local terminal client and can create a PromptEnvelope that reaches the gateway.
10. Connector profiles can be listed even before connector implementations are enabled.
11. SQLite state indexes events written to JSONL.
12. No interface is allowed to bypass or outrank another interface because of phase order, implementation order, or UI richness.

---

## Phased Implementation Hand-Off

When a builder starts work, it must choose exactly one task from the phase blueprint, then read the docs linked by that task.

Recommended reading sequence for any implementation task:

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

The builder must not interpret phase scheduling as permission to skip the detailed spec. If a spec is incomplete, the builder must update the spec first, then implement.
