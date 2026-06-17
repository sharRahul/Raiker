# Raiker Architecture Blueprint

Raiker is a local-first AI agent platform. It is designed as an operating layer for prompts, models, tools, policy, memory, plugins, hooks, subagents, and execution environments.

This document turns the high-level README into implementation-ready architecture.

---

## System Goals

Raiker must provide:

1. one gateway for all clients;
2. deterministic runtime state transitions;
3. policy-gated tool execution;
4. append-only event logging;
5. governed memory writes;
6. model-provider abstraction;
7. safe local-first execution;
8. resumable checkpoints;
9. testable contracts;
10. small-model-friendly implementation boundaries.

---

## Non-Goals For Phase 1

Phase 1 must not implement:

- full desktop app;
- web dashboard;
- plugin marketplace;
- autonomous background agents;
- long-term vector memory;
- graph memory;
- cloud deployment;
- Docker execution beyond interface stubs;
- remote SSH execution beyond interface stubs;
- voice, Slack, Teams, Discord, Signal, or email clients;
- real LLM provider integrations except a mock provider and optional local-model interface stub.

---

## Layered Architecture

```text
Clients
  -> Agent Gateway
    -> Session Manager
      -> Agent Runtime
        -> Context Gatherer
        -> Planner
        -> Policy Engine
        -> Tool Broker
        -> Model Router
        -> Verifier
        -> Checkpoint Service
        -> Memory Governance
      -> Event Log
```

Every client talks to the gateway. No client can call tools directly.

---

## Component Responsibilities

### Agent Gateway

Responsible for:

- accepting `PromptEnvelope` input;
- validating request shape;
- assigning request IDs if missing;
- forwarding the request to the session manager;
- returning an `AgentEvent` stream or final `AgentResponse`.

Must not:

- execute tools;
- call models directly;
- write memory directly;
- bypass event logging.

### Session Manager

Responsible for:

- creating sessions;
- loading session state;
- preserving turn order;
- attaching checkpoints to sessions;
- closing completed turns.

### Agent Runtime

Responsible for the deterministic task loop:

```text
RECEIVED
  -> NORMALISED
  -> CLASSIFIED
  -> CONTEXT_READY
  -> PLAN_READY or PLAN_SKIPPED
  -> POLICY_REVIEWED
  -> ACTIONS_EXECUTED or ACTIONS_DENIED
  -> VERIFIED
  -> MEMORY_REVIEWED
  -> RESPONDED
  -> CHECKPOINTED
  -> CLOSED
```

The runtime must expose state transitions in logs and tests.

### Context Gatherer

Responsible for gathering only approved context sources:

- current prompt;
- session history;
- explicitly attached files;
- project memory stubs;
- tool-read results approved by policy.

### Planner

Responsible for deciding whether a plan is needed.

A plan is required when:

- task has more than one tool action;
- task writes files;
- task uses shell;
- task changes code;
- task involves external network access;
- task could affect user data, cost, security, or privacy.

Plan may be skipped for simple chat, summarisation, or direct answer tasks. The reason must be logged.

### Policy Engine

Responsible for evaluating proposed actions before execution.

It returns:

- `allow`;
- `deny`;
- `needs_approval`.

Phase 1 policy can be static YAML or JSON. It must be deterministic and covered by tests.

### Tool Broker

Responsible for all tool execution.

Phase 1 tools:

- `read_file`;
- `list_directory`;
- `glob`;
- `grep`;
- `shell` with approval requirement.

No module outside the broker may execute shell commands or read/write files as an agent action.

### Model Router

Responsible for abstracting model providers.

Phase 1 providers:

- `mock` provider for deterministic tests;
- optional interface-only local provider stub.

### Event Log

Responsible for append-only JSONL events.

Every event must include:

- event ID;
- timestamp;
- session ID;
- turn ID;
- event type;
- actor;
- payload;
- schema version.

### Checkpoint Service

Responsible for storing resumable state after a turn.

Phase 1 may use simple JSON files.

### Memory Governance

Phase 1 must not implement durable long-term memory. It must only identify memory candidates and log whether they were accepted, rejected, or deferred.

---

## Data Flow For A Phase 1 Prompt

```text
1. CLI receives prompt.
2. CLI builds PromptEnvelope.
3. AgentGateway validates envelope.
4. SessionManager opens or creates session.
5. AgentRuntime logs prompt_received.
6. Runtime classifies intent and risk.
7. Runtime gathers context.
8. Runtime creates or skips plan.
9. Runtime proposes actions.
10. PolicyEngine reviews actions.
11. ToolBroker executes approved actions.
12. Runtime verifies result.
13. Runtime produces final response.
14. CheckpointService writes checkpoint.
15. EventLogWriter records all events.
```

---

## Recommended Phase 1 Technology Choices

These choices are intended to minimise drift and complexity.

- Language: Python 3.11 or 3.12.
- Package manager: uv or pip with a lockfile.
- CLI: argparse or Typer. Prefer argparse if dependency minimisation is more important.
- Data validation: Pydantic or dataclasses. Use one consistently.
- Tests: pytest.
- Event log: JSONL files.
- Policy config: JSON or YAML. Prefer JSON if avoiding dependencies.
- Storage: local filesystem only.

---

## Required Directory Shape For Phase 1

```text
raiker/
  __init__.py
  contracts/
    __init__.py
    envelopes.py
    events.py
    actions.py
    policy.py
  gateway/
    __init__.py
    agent_gateway.py
  sessions/
    __init__.py
    session_manager.py
  runtime/
    __init__.py
    state_machine.py
    agent_runtime.py
    classifier.py
    planner.py
    verifier.py
  policy/
    __init__.py
    static_policy_engine.py
  tools/
    __init__.py
    broker.py
    file_tools.py
    search_tools.py
    shell_tool.py
  models/
    __init__.py
    router.py
    mock_provider.py
  events/
    __init__.py
    event_log_writer.py
  checkpoints/
    __init__.py
    checkpoint_service.py
  memory/
    __init__.py
    governance.py
apps/
  cli/
    __init__.py
    main.py
tests/
  test_contracts.py
  test_event_log.py
  test_policy_engine.py
  test_tool_broker.py
  test_runtime_state_machine.py
  test_cli_smoke.py
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
7. The CLI path uses the same gateway as future clients.
8. The model router can use a deterministic mock provider.

---

## Future Phase Boundaries

Future phases may add:

- real Ollama and llama.cpp providers;
- web UI;
- desktop UI;
- TUI;
- plugin manifests;
- MCP servers;
- vector memory;
- graph memory;
- remote execution;
- voice;
- multi-agent orchestration.

Until a future phase starts, these must remain as docs, interfaces, or stubs only.
