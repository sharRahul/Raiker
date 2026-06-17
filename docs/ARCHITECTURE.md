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
11. rich interruptible UX across CLI, TUI, Desktop, Web, IDE, Voice, and Channels;
12. small-model-friendly implementation boundaries.

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

Phase boundaries exist to control implementation order, not to hide missing design.

| Phase | Build focus | Required architectural state |
|---|---|---|
| Phase 1 | Secure Local CLI Core | Contracts, gateway, sessions, runtime, policy, broker, event log, SQLite bootstrap, CLI, mock model, checkpoint stub. |
| Phase 2 | Rich Local Workspace | Rich TUI, background tasks, side questions, full checkpoints/rewind, local model providers, hooks, approved project/profile memory. |
| Phase 3 | Desktop/Web/Plugin/Graph Platform | Desktop UI, Web UI, Dashboard, plugin manager, semantic search, graph/codemap, REST API, worktree isolation. |
| Phase 4 | Channels/Multi-Agent/Remote Execution | Channel connectors, subagents, agent teams, container/remote profiles, voice/hotkeys/browser extension. |
| Phase 5 | Governed Enterprise/Home-Lab Platform | Managed policies, multi-user governance, signed plugins, event integrity, audit export, cloud/GPU budgets, deployment operations. |

### Phase 1 Exclusions Are Implementation Exclusions Only

Phase 1 does not wire these features into user-facing behaviour: Desktop UI, Web UI, Dashboard, plugin marketplace, autonomous multi-agent teams, durable vector/graph memory writes, cloud deployment, container/remote execution, external messaging channels, voice channels, or production hosted-model billing controls.

However, Phase 1 must still preserve the contracts, registries, storage hooks, policy boundaries, and extension points that make those phase-scheduled features implementable without redesign.

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

Every client talks to the gateway. No client can call tools directly.

---

## Component Responsibilities

### Agent Gateway

Responsible for accepting `PromptEnvelope` and `ChannelMessageEnvelope` input, validating request shape, assigning request IDs if missing, forwarding requests to the session manager, and returning an `AgentEvent` stream or final `AgentResponse`.

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

The runtime must expose state transitions in logs, SQLite state, TUI status, and tests.

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

Responsible for abstracting model providers. Phase 1 uses the deterministic `mock` provider. Phase 2 wires Ollama, llama.cpp server, LM Studio, and OpenAI-compatible local endpoints. Hosted providers are policy-controlled and documented in `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`.

### Event Log

Responsible for append-only JSONL events and SQLite event indexes. Every event must include event ID, timestamp, session ID, event type, actor, payload, and schema version.

### State Store

Responsible for SQLite-backed state, indexes, memory metadata, graph metadata, approvals, tool actions, checkpoints, connector profiles, plugin registry, model profiles, and dashboard metrics. The concrete schema is defined in `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`.

### Checkpoint Service

Responsible for storing resumable state after turns and snapshots before risky file actions. Phase 1 writes basic checkpoint manifests. Phase 2 expands restore, rewind, fork, compare, and file snapshots according to `docs/CHECKPOINTING_AND_REWIND_SPEC.md`.

### Memory Governance

Responsible for memory candidates, durable memory records, provenance, sensitivity, confidence, correction, forgetting, semantic search, and graph-linked memory. Phase 1 creates candidates and SQLite memory tables. Phase 2 writes approved profile/project/episodic/procedural memory. Phase 3 adds semantic/vector and graph-backed retrieval.

---

## Data Flow For A Phase 1 Prompt

```text
1. User runs global `raiker ask "..."` command.
2. CLI builds PromptEnvelope.
3. AgentGateway validates envelope.
4. SessionManager opens or creates session.
5. Runtime logs prompt_received.
6. Runtime classifies intent and risk.
7. Runtime gathers context.
8. Runtime creates or skips plan.
9. Runtime proposes actions.
10. PolicyEngine reviews actions.
11. ToolBroker executes approved actions or pauses for approval.
12. Runtime verifies result.
13. Runtime produces final response.
14. CheckpointService writes checkpoint.
15. EventLogWriter records all events.
16. SQLite state store indexes session, turn, events, task, action, and checkpoint metadata.
```

---

## Global Command And Launch Architecture

Raiker must install a global command named `raiker`.

Minimum command family:

```bash
raiker ask "List files in this project"
raiker chat
raiker tui
raiker launch --provider ollama --model qwen3.5-coder:9b
raiker launch --provider llama.cpp --model /models/qwen.gguf --ctx 32768
raiker launch --provider lm-studio --model local-model
raiker launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
raiker gateway start
raiker gateway status
raiker models list
raiker channels list
raiker doctor
```

Canonical launch path:

```bash
raiker launch --provider <provider> --model <model>
```

Provider-specific convenience launchers, including a platform adapter that accepts a command shaped like `ollama launch raiker --model <model>`, may delegate into the canonical `raiker launch` path when that platform supports such extension behaviour. Documentation and tests must always keep the canonical global `raiker` path.

---

## Recommended Phase 1 Technology Choices

These choices minimise drift and complexity while preserving the full architecture.

- Language: Python 3.11 or 3.12.
- Package manager: uv or pip with a lockfile.
- CLI: argparse or Typer. Prefer argparse if dependency minimisation is more important.
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
  test_cli_smoke.py
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
7. The CLI path uses the same gateway as every scheduled client and channel.
8. The model router can use a deterministic mock provider.
9. The global `raiker` command can create a PromptEnvelope and reach the gateway.
10. Connector profiles can be listed even before connector implementations are enabled.
11. SQLite state indexes events written to JSONL.

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
  -> task-specific spec
  -> docs/VERIFICATION_PLAN.md
```

The builder must not interpret phase scheduling as permission to skip the detailed spec. If a spec is incomplete, the builder must update the spec first, then implement.
