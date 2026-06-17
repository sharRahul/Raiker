
# Raiker

**Raiker** is a local-first AI agent platform designed to run as a secure, observable, extensible agent operating layer on a personal workstation, home lab, or governed enterprise environment.

Raiker is not just a chatbot. Raiker is an **agent runtime** that connects user interfaces, language models, tools, memory, plugins, hooks, subagents, and execution environments behind a security and privacy boundary.

The goal is simple:

```text
Just Ask
  -> interrupt, steer, or add context at any time
  -> Raiker gathers context
  -> Raiker plans when the task is complex or risky
  -> Raiker acts through approved tools, skills, plugins, hooks, and subagents
  -> Raiker verifies the result
  -> Raiker records every action
  -> Raiker updates governed long-term memory only when appropriate
```

---

## Why Raiker Exists

Modern AI coding agents are powerful, but they often have several gaps:

- They may rely heavily on cloud models.
- They may not preserve useful memory across long periods.
- They may lack strong security boundaries around shell, files, plugins, and network access.
- They may not provide OS-like event logs for every action.
- They may treat terminal, chat, desktop, and API experiences as separate products instead of equal clients.
- They may drift when smaller local models are used to implement complex systems.

Raiker is designed to solve those problems with a **local-first, policy-gated, event-sourced agent architecture**.

---

## Core Principles

### 1. Local-first by default
Raiker should be able to run fully locally with local models such as llama.cpp, Ollama, or LM Studio. Remote models and cloud execution are optional and policy-controlled.

### 2. Equal-status clients
Raiker is not tied to one interface. CLI, chat, rich TUI, desktop, web, IDE, voice, hotkeys, REST, and webhooks are all clients of the same agent gateway.

### 3. Security and privacy are architectural layers
Raiker treats security as a boundary around the agent core. Tool execution, memory writes, plugin actions, remote calls, shell commands, and external execution all pass through policy.

### 4. OS-like event logging
Every prompt, model call, tool proposal, approval, denial, tool result, hook, plugin action, memory write, checkpoint, subagent event, verification result, and error is recorded.

### 5. Durable but governed memory
Raiker can remember across sessions, months, and years, but memory is not uncontrolled. Memory records include provenance, confidence, sensitivity, retention, trust score, and approval state.

### 6. Small-model friendly implementation
Raiker’s build plan is intentionally decomposed into small, explicit tasks so a local model running on consumer hardware can implement the platform without hallucinating or drifting.

---

## High-Level User Flow

```text
User prompt
  -> Client interface
  -> Agent gateway
  -> Session manager
  -> Agent runtime
  -> Context gathering
  -> Planning
  -> Policy review
  -> Tool/model/memory/subagent action
  -> Verification
  -> Final response
  -> Checkpoint
  -> Event log
  -> Memory governance
```

---

## Main Architecture

Raiker uses a nested control-boundary architecture:

```text
Interface Layer
  Event Logging Layer
    Security and Privacy Layer
      Agent Core
        Agent Runtime
        Tool Broker
        Hook Engine
        Memory Service
        Model Router
        Plugin and Skill System
        Subagent Orchestrator
        Execution Adapters
```

The nested design is intentional:

- The **interface layer** is outside the core and never executes tools directly.
- The **event logging layer** wraps all meaningful activity.
- The **security and privacy layer** mediates all risky operations.
- The **agent core** reasons, plans, acts, verifies, and delegates.
- The **execution layer** runs commands only through approved adapters.
- The **persistence layer** stores logs, checkpoints, memory, vectors, graphs, and artifacts.

---

## Equal-Status Clients

Raiker supports these clients as first-class citizens:

```text
CLI
Chat: Signal, Slack, Teams, Discord, email
Rich TUI
Desktop
Web
IDE extension
Voice
Hotkeys
REST API
Webhooks
```

Each client sends the same `PromptEnvelope` contract and receives the same `AgentEvent` stream.

---

## Agent Core Capabilities

### Agent Runtime
The runtime controls the deterministic loop:

```text
prompt received
  -> prompt normalised
  -> intent classified
  -> risk classified
  -> context gathered
  -> context validated
  -> plan created or skipped with reason
  -> policy reviewed
  -> action dispatched
  -> tool results ingested
  -> verification completed
  -> memory candidates reviewed
  -> final response created
  -> checkpoint created
  -> turn closed
```

### Tool Broker
The tool broker is the only path to tools. It controls:

- file read/write/edit/list/delete
- grep/glob/search
- shell and PowerShell
- Git and worktrees
- LSP/code intelligence
- memory search/write/forget/export
- graph query
- web fetch/search
- subagent spawning
- user clarification
- Docker, SSH, Daytona, Modal, external hosting

### Memory Service
Raiker memory includes:

- **Profile memory** — stable user preferences and facts
- **Project memory** — project decisions and architecture
- **Episodic memory** — timestamped session summaries
- **Procedural memory** — repeated workflows distilled into skills
- **Semantic memory** — vector-searchable knowledge
- **Graph memory** — entities, relationships, code maps, decisions

### Model Router
The model router can connect to:

- local models
- llama.cpp
- Ollama
- LM Studio
- OpenRouter or OpenAI-compatible providers
- Anthropic/OpenAI-style hosted providers
- Modal-hosted inference
- custom provider plugins

### Plugins, Skills, and Hooks
Raiker supports extension through:

- skills
- commands
- plugin manifests
- subagents
- hooks
- channels
- MCP-compatible servers
- monitors
- UI panels

Plugins must declare permissions and are policy-gated.

---

## Execution Targets

Raiker can run work in multiple execution environments:

```text
Local native runner
Docker
SSH remote host
Daytona sandbox
Modal serverless/GPU/batch
External hosting: VPS, Kubernetes, private cloud, managed app
```

External execution is always governed by policy, egress controls, budgets, and event logging.

---

## Security Model

Raiker’s security layer is designed around common GenAI and agentic risks:

- prompt injection
- sensitive information disclosure
- plugin and dependency supply-chain risk
- data, model, and memory poisoning
- improper output handling
- excessive agency
- system prompt leakage
- vector and embedding weaknesses
- misinformation
- unbounded consumption

High-risk actions require explicit approval unless a policy grants them.

---

## Non-Deviation Rules for Builder Agents

Raiker is intended to be implemented by AI coding agents, including smaller local models. To prevent drift:

1. The build agent must follow the roadmap task-by-task.
2. The build agent must not invent unplanned services or databases.
3. The build agent must not add dependencies without explanation.
4. The build agent must not implement future-phase features early.
5. The build agent must not bypass policy, tool broker, or memory governance.
6. The build agent must ask for clarification or create an ADR when uncertain.

---

## Phase 1 MVP

The first implementation phase should build only:

- repository scaffold
- contracts
- event log writer
- static policy engine
- tool broker skeleton
- read_file
- list_directory
- glob
- grep
- shell with approval
- mock model provider
- deterministic runtime state machine
- CLI client
- checkpoint stub
- unit tests

Future features should be added only as stubs or interfaces until their phase.

---

## Suggested Repository Structure

```text
/core
  /contracts
  /agent_gateway
  /session_manager
  /agent_runtime
  /model_router
  /tool_broker
  /policy_engine
  /memory_service
  /event_log
  /checkpoint_service
  /plugin_manager
  /hook_engine
  /channel_manager
  /security
  /deployment_adapters
/apps
  /cli
  /tui
  /desktop
  /web
  /ide
/clients
  /slack
  /signal
  /teams
  /discord
  /email
  /voice
  /hotkeys
  /rest
  /webhooks
/plugins
/skills
/agents
/docs
/tests
/security_tests
/examples
```

---

## Project Status

Raiker is currently at the architecture and implementation-blueprint stage. The next step is to implement the Phase 1 MVP from the implementation plan.
