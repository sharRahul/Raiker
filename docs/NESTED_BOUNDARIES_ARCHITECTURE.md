# Nested Boundaries Architecture Diagram

This diagram makes Raiker's architecture boundaries explicit so a local or cloud builder model can see which components are allowed to talk to each other and which boundaries must never be bypassed.

The diagram is implementation-oriented, not future-vague. Phase scheduling controls build order only. The boundaries below apply from Phase 1 and remain stable as later phase-scheduled features are wired.

## Source-of-truth boundary rules

1. `raiker` is the only human-facing global command. It launches the Rich TUI.
2. All clients, channels, UIs, and provider shortcuts must enter through the Agent Gateway.
3. No client, model, plugin, hook, channel, runtime helper, or subagent may execute tools directly.
4. Every tool action must pass through ToolAction proposal, Policy Engine review, optional action-bound approval, Tool Broker dispatch, and Event Log recording.
5. Model output, file content, channel messages, plugin content, subagent output, memory records, and graph results are context inputs or proposals, not trusted instructions.
6. SQLite, JSONL event logs, checkpoints, snapshots, artifacts, indexes, and config under `.raiker/` form the local persistence boundary.
7. Graph/codemap, semantic search, eidetic observations, gist memory, skills, subagents, channels, plugins, and remote/cloud execution extend the same contracts instead of creating parallel paths.

## Nested boundary diagram

```mermaid
flowchart TB
  user((User)) --> global_cmd[`global command: raiker`]
  provider_shortcut[`provider shortcut, e.g. ollama launch raiker --model <model>`] -. delegates to TUI action .-> global_cmd

  subgraph HOST["Host boundary: workstation / home lab / governed enterprise environment"]
    direction TB

    subgraph PRIVACY["Security + privacy trust boundary"]
      direction TB

      subgraph CLIENTS["Interface and channel boundary"]
        direction LR
        global_cmd --> tui["Rich TUI\nprimary Phase 1 client"]
        cli["CLI adapter\ncompatibility surface"]
        desktop["Desktop UI\nphase-scheduled"]
        web["Web UI / Dashboard\nphase-scheduled"]
        ide["IDE / browser / voice\nphase-scheduled"]
        external_channels["Slack / Teams / Discord / Signal / Email\nphase-scheduled channels"]
      end

      subgraph RAIKER["Raiker runtime process boundary"]
        direction TB

        subgraph INGRESS["Only ingress boundary"]
          gateway["Agent Gateway\nvalidates PromptEnvelope, UIActionEnvelope, ChannelMessageEnvelope"]
        end

        subgraph SESSION["Session and deterministic runtime boundary"]
          direction TB
          session_mgr["Session Manager\nresume, fork, turn order, task state"]
          runtime["Runtime Orchestrator\nstate machine + background tasks + interrupts"]
          context["Context Gatherer\napproved context bundle only"]
          planner["Planner\nrequired for multi-action/risky work"]
          verifier["Verifier\ncontract, tests, diff, security, result checks"]
          checkpoint["Checkpoint Service\nturn checkpoints + risky-action snapshots"]
        end

        subgraph POLICY_AUDIT["Policy, approval, and audit boundary"]
          direction TB
          policy["Policy Engine\nallow / deny / needs_approval"]
          approvals["Action-bound Approval Service\nno approval reuse for changed action"]
          events["Event Log Writer\nappend-only JSONL + SQLite index"]
        end

        subgraph ACTIONS["Action execution boundary"]
          direction TB
          broker["Tool Broker\nonly execution path"]
          fs_tools["Filesystem/search tools\nread_file, list_directory, glob, grep"]
          command_tools["Local command proposals\nshell requires approval"]
          exec_adapters["Execution Adapter Registry\nlocal now; container/SSH/VPS/K8s/cloud later"]
        end

        subgraph MODEL["Model runtime boundary"]
          direction TB
          model_router["Model Router\nprovider abstraction, roles, streaming, structured output"]
          local_models["Local providers\nmock, Ollama, llama.cpp, LM Studio, local OpenAI-compatible"]
          hosted_models["Hosted providers\nOpenRouter / Anthropic / cloud GPU\npolicy + egress + budget gated"]
        end

        subgraph MEMORY_GRAPH["Context, memory, graph, and learning boundary"]
          direction TB
          memory["Memory Governance\ncandidates, approved records, correction, forgetting"]
          eidetic["Eidetic observations + gist memory\nraw snapshot retention + compressed recall"]
          graph["Graph / Codemap Service\nentities, edges, impact queries, stale detection"]
          search["FTS5 / semantic / vector retrieval\nsensitivity-filtered context"]
          skills["Self-improving skills\napproved, tested, provenance-linked"]
        end

        subgraph EXTENSIONS["Extension and delegation boundary"]
          direction TB
          hooks["Hook Engine\nlifecycle hooks; no silent bypass"]
          plugins["Plugin Manager\nmanifest, trust, permission diff"]
          channel_mgr["Channel Manager\nprofile registry, sender trust, approval relay controls"]
          subagents["Subagent Orchestrator\nbounded delegation, parent verification"]
        end

        subgraph STORAGE["Local persistence boundary: .raiker/"]
          direction TB
          sqlite[("SQLite raiker.db\nsessions, turns, tasks, approvals, graph, memory, registries")]
          jsonl[("events/*.jsonl\nappend-only audit/event stream")]
          ckpts[("checkpoints/\nmanifests, snapshots, rewind/fork inputs")]
          artifacts[("artifacts/ + indexes/ + config/\nlarge outputs, vector/graph cache, policy/model/plugin config")]
        end
      end
    end
  end

  tui --> gateway
  cli --> gateway
  desktop --> gateway
  web --> gateway
  ide --> gateway
  external_channels --> channel_mgr
  channel_mgr --> gateway

  gateway --> session_mgr
  session_mgr --> runtime
  runtime --> context
  runtime --> planner
  runtime --> policy
  policy --> approvals
  approvals --> broker
  policy --> broker
  broker --> fs_tools
  broker --> command_tools
  broker --> exec_adapters
  runtime --> verifier
  runtime --> checkpoint
  runtime --> model_router
  model_router --> local_models
  model_router -. explicit egress/cost approval .-> hosted_models

  context --> memory
  context --> eidetic
  context --> graph
  context --> search
  memory --> skills
  graph --> search

  runtime --> hooks
  hooks --> policy
  plugins --> broker
  plugins --> hooks
  subagents --> gateway
  subagents --> verifier

  gateway --> events
  runtime --> events
  policy --> events
  approvals --> events
  broker --> events
  model_router --> events
  memory --> events
  graph --> events
  checkpoint --> events
  channel_mgr --> events
  plugins --> events
  subagents --> events

  session_mgr --> sqlite
  events --> jsonl
  events --> sqlite
  checkpoint --> ckpts
  broker --> artifacts
  memory --> sqlite
  eidetic --> artifacts
  eidetic --> sqlite
  graph --> sqlite
  graph --> artifacts
  search --> sqlite
  search --> artifacts
  model_router --> sqlite
  channel_mgr --> sqlite
  plugins --> sqlite
```

## Boundary interpretation for builders

### 1. Outer host boundary

Raiker runs local-first on a workstation, home lab, or governed enterprise environment. Remote providers and cloud execution are optional and policy-controlled. The default assumption is that local execution, local storage, and local model profiles are preferred.

### 2. Security and privacy trust boundary

Every inner component operates under the security and privacy boundary. Untrusted inputs include user prompts, workspace files, model outputs, channel messages, plugin content, memory records, graph results, tool output text, and subagent output. These inputs may be used as context but must not become privileged instructions.

### 3. Interface and channel boundary

The Rich TUI launched by `raiker` is the Phase 1 primary client. Desktop, Web, Dashboard, IDE, voice, browser, mobile, and external messaging clients are phase-scheduled clients, but they do not get separate control paths. They all use the same gateway and event stream.

### 4. Gateway boundary

The Agent Gateway is the only ingress point for client and channel envelopes. It validates request shape, assigns missing IDs, forwards to the Session Manager, and returns event streams or final responses. It must not execute tools, call models directly, write memory directly, or bypass the event log.

### 5. Runtime/session boundary

The Session Manager owns session state, turn order, resume/fork, checkpoint association, and task reconstruction. The Runtime Orchestrator owns deterministic turn and background-task state machines, context gathering, planning, action proposal, approval waiting, verification, memory review, response creation, checkpointing, and closure.

### 6. Policy, approval, and audit boundary

Every proposed action must be policy-reviewed before execution. Risky actions pause for action-bound approval. Every security-relevant event is written to append-only event logs and indexed in SQLite.

### 7. Tool/action boundary

The Tool Broker is the only path to tools. Filesystem reads, search, shell commands, command wrappers, execution profiles, memory tools, graph queries, web tools, plugin tools, channel tools, and subagent tools must all route through the broker when implemented.

### 8. Model boundary

The Model Router treats model output as untrusted. It parses, schema-validates, risk-classifies, policy-reviews, and logs structured output. Local providers are preferred. Hosted providers require explicit privacy, egress, endpoint, budget, and policy controls. There is no silent remote fallback.

### 9. Memory/graph/learning boundary

Memory is governed, scoped, auditable, and correctable. Eidetic observations are short-retention raw snapshots with provenance and sensitivity labels. Gist memory is preferred for durable recall. Graph/codemap data supports impact analysis and retrieval, but graph results cannot override policy.

### 10. Storage boundary

`.raiker/` is the local persistence boundary. SQLite is the primary state database. JSONL stores append-only event logs. Checkpoints and snapshots support rewind/fork. Artifacts and indexes store large tool outputs, vector metadata, graph caches, reports, and exports.

## Non-bypass rules

| Caller | Forbidden direct target | Required route |
|---|---|---|
| TUI / CLI / Desktop / Web / Channel | Tool Broker, Model Router, Storage | Agent Gateway |
| Model output | Tool execution | Runtime parses proposal -> Policy Engine -> Tool Broker |
| Plugin | Tool execution or approval | Plugin Manager -> permission diff -> Tool Broker / Policy Engine |
| Hook | Tool execution or hidden allow | Hook Engine -> declared authority -> Policy Engine / Event Log |
| Subagent | Filesystem, command, memory write | Parent runtime/gateway -> policy/broker -> verifier |
| Memory/graph retrieval | System authority | Context Gatherer with trust labels and provenance |
| Execution adapter | Command execution | Tool Broker action with policy decision and approval if required |
| Channel approval | Action execution | Approval relay binding to exact action ID and trusted channel session |

## Builder checklist

Before implementing any component touched by this diagram, a builder must identify:

1. which boundary owns the component;
2. which contracts enter and leave the boundary;
3. which event types are emitted;
4. which SQLite tables or artifact paths are affected;
5. which policy decisions can block or pause the operation;
6. which UI surface exposes the operation;
7. which tests prove the boundary cannot be bypassed;
8. which phase task implements the behaviour without changing the boundary.
