# Raiker Architecture Blueprint

> Current truth (2026-06-21): current launchable UI is the plain local terminal client only. Rich/native TUI is Phase 8 deferred work. Desktop/Web/Dashboard/Mobile/IDE/Voice/Browser Extension/REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Runtime execution remains disabled for plugin execution, graph indexing, semantic/vector writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, remote/container/cloud/process/shell/network execution.


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
| Phase 3 | Desktop/Web/Mobile/Plugin/Graph target platform architecture | Target platform architecture covers Desktop UI, Web UI, Dashboard, Apple mobile app, Android mobile app, plugin manager, semantic search, graph/codemap, REST API, and worktree isolation. Currently completed Phase 3 A-P scope is the safe foundation/readiness layer only: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval previews, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Phase 8 deferred runtime/app work includes launchable Rich/native TUI, desktop/web/mobile/dashboard/IDE/API apps; deferred runtime semantic/vector search, graph indexing/query execution, plugin execution, scheduled automation, and hosted/cloud runtime work. |
| Phase 4 | Channels/Multi-Agent/Remote Execution | Channel connectors, subagents, agent teams, container/remote profiles, voice/hotkeys/browser extension, chat/email clients. |
| Phase 5 | Governed Enterprise/Home-Lab Platform | Managed policies, multi-user governance, signed plugins, event integrity, audit export, cloud/GPU budgets, deployment operations. |
| Phase 6 | Channels/Subagents/Remote Foundations | External channel connectors and approval relay, subagent contracts, multi-agent team ledgers, remote/container execution profiles, execution budgets. Records/metadata implemented; runtime transports and execution remain disabled. |
| Phase 7 | Runtime Feature Foundations | Desktop/Web/IDE session models, plugin runtime, graph/codemap indexing, and semantic/vector memory writes as record-level foundations. Dashboard and mobile apps remain `specified_not_implemented`; all execution stays policy-gated and disabled. |
| Phase 9 | Advanced Memory & Graph | Vector index, AST symbol/dependency graph indexer, project graph extraction, and procedural-memory-to-skill-candidate conversion as in-memory modules with SQLite persistence. All execution remains policy-gated and disabled. (There is Phase 8 is the planned UI/client phase; numbering intentionally skips from 7 to 9.) |

> Phase 6–9 status detail lives in the canonical ledger `docs/IMPLEMENTATION_STATUS.md`.

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

Running `raiker` launches the configured local terminal client. The default terminal client is currently the plain local terminal client only; Rich/native TUI is Phase 8 deferred.

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
- Terminal client: a minimal dependency-free terminal renderer; Textual/Rich are Phase 8 deferred. Prefer the smallest implementation that supports panels and input safely.
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

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Plain terminal shell/status rendering only; Rich/native TUI panels are Phase 8 deferred. | Plain-only | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |

