> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (Phase 8 is the planned UI/client phase), the launchable UI is a local terminal client (plain local terminal client only; Rich/native TUI deferred to Phase 8), and all runtime execution remains disabled.

# 02 Technical Specification

## 1. System Overview

Local Sovereign Agent is built as a daemon plus equal-status clients. The daemon owns all authoritative state. Clients are thin control surfaces.

```text
Client -> Gateway -> Session Manager -> Agent Runtime -> Tool Broker -> Policy Engine -> Execution Target
                                      -> Model Router
                                      -> Memory Service
                                      -> Plugin Manager
                                      -> Hook Engine
                                      -> Checkpoint Service
                                      -> Event Log
```

## 2. Required Runtime Modules

### 2.1 Contracts Module
Defines typed data models shared across clients and core services.

Required contracts:
- PromptEnvelope.
- AgentEvent.
- ToolDescriptor.
- ToolCallRequest.
- ToolCallResult.
- PolicyDecision.
- PermissionRequest.
- ModelRequest.
- ModelResponseChunk.
- MemoryRecord.
- CheckpointRecord.
- PluginManifest.
- HookEvent.
- SubagentSpec.

### 2.2 Agent Gateway
Responsibilities:
- Accept client requests over local IPC, REST, WebSocket/SSE, CLI process call, or embedded in-process call.
- Authenticate or identify the caller.
- Attach client type and trust level.
- Convert all requests to PromptEnvelope.
- Stream AgentEvent messages back to clients.
- Relay permission prompts.

### 2.3 Session Manager
Responsibilities:
- Create session ID and turn ID.
- Store active working directory.
- Store active model profile.
- Track active tasks and subagents.
- Support resume, continue, fork, and close.
- Persist session state after every major transition.

### 2.4 Agent Runtime
Responsibilities:
- Implement state machine.
- Request context.
- Invoke planning prompt when required.
- Call Tool Broker only through typed ToolCallRequest.
- Coordinate subagents.
- Call Verification Coordinator.
- Submit memory candidates.
- Produce final response.

### 2.5 Model Router
Responsibilities:
- Maintain provider registry.
- Choose model based on policy and task.
- Enforce local-first rules.
- Block sensitive remote calls unless approved.
- Support fallback from tool-calling model to JSON-only or text-only model using adapter prompts.

### 2.6 Tool Broker
Responsibilities:
- Register tools.
- Validate arguments.
- Classify risk.
- Ask Policy Engine.
- Execute through target adapter.
- Sanitize outputs.
- Emit events.

### 2.7 Policy Engine
Responsibilities:
- Evaluate allow/ask/deny.
- Enforce budgets.
- Enforce filesystem, network, model, plugin, shell, memory, and egress rules.
- Produce explainable decision.

### 2.8 Memory Service
Responsibilities:
- Canonical Markdown storage.
- SQLite metadata.
- Vector index.
- Graph index.
- Retrieval pipeline.
- Write governance pipeline.
- Forget/export/redact.

### 2.9 Plugin Manager
Responsibilities:
- Validate plugin manifests.
- Check signatures or trust state.
- Register skills, tools, hooks, channels, subagents, commands, MCP servers.
- Enforce plugin permission scopes.

### 2.10 Event Log
Responsibilities:
- Append-only JSONL segments.
- SQLite search index.
- Encrypted blob references for sensitive payloads.
- Replay support.
- Export JSONL/SARIF/OpenTelemetry-style traces.

## 3. Data Contracts

### PromptEnvelope

```json
{
  "prompt_id": "uuid",
  "session_id": "uuid|null",
  "turn_id": "uuid|null",
  "client": {
    "type": "cli|chat|tui|desktop|web|ide|voice|hotkeys|rest|webhooks",
    "identity": "string",
    "channel_id": "string|null",
    "trust_level": "trusted|authenticated|untrusted"
  },
  "user_text": "string",
  "attachments": [
    {"type": "file|folder|url|image|clipboard|log|terminal|memory_ref|graph_ref", "uri": "string", "trust": "trusted|untrusted"}
  ],
  "mode": "ask|plan|act|review|security_review|memory|debug",
  "budget": {"max_turns": 20, "max_tokens": 200000, "max_cost": 5.0, "max_seconds": 1800, "max_subagents": 5},
  "permission_overrides": {"shell": "ask", "filesystem_write": "ask", "network": "ask", "external_execution": "ask"}
}
```

### PolicyDecision

```json
{
  "decision": "allow|ask|deny",
  "risk": "low|medium|high|critical",
  "reason": "string",
  "required_approval": "none|user|admin|break_glass",
  "redactions_required": ["string"],
  "constraints": {"timeout_seconds": 60, "network": "deny", "filesystem_scope": "workspace"}
}
```

### ToolCallResult

```json
{
  "tool_call_id": "uuid",
  "status": "success|failure|denied|cancelled|timeout",
  "exit_code": 0,
  "stdout_ref": "blob|null",
  "stderr_ref": "blob|null",
  "summary": "string",
  "artifacts": [],
  "security_findings": [],
  "output_truncated": false
}
```

## 4. Deterministic State Machine

The runtime must not skip states. If a state is not needed, it must emit a state-skipped event with reason.

```text
IDLE
PROMPT_RECEIVED
PROMPT_NORMALISED
INTENT_CLASSIFIED
RISK_CLASSIFIED
CONTEXT_PLAN_CREATED
CONTEXT_GATHERED
CONTEXT_VALIDATED
PLAN_CREATED_OR_SKIPPED
POLICY_REVIEWED
ACTION_DISPATCHED
TOOL_RESULTS_INGESTED
VERIFICATION_COMPLETED
MEMORY_CANDIDATES_REVIEWED
FINAL_RESPONSE_CREATED
CHECKPOINT_CREATED
TURN_CLOSED
```

## 5. MVP Tool List

Phase 1 must implement only:
- read_file.
- list_directory.
- glob.
- grep.
- shell with approval.
- create_checkpoint stub.
- ask_user.

All other tools must exist only as descriptors or planned interfaces until their phase.

## 6. Storage Layout

```text
~/.local-sovereign-agent/
  config/config.toml
  config/providers.toml
  config/policy.toml
  sessions/<session_id>/session.json
  sessions/<session_id>/events.jsonl
  checkpoints/<checkpoint_id>/checkpoint.json
  logs/events-yyyy-mm-dd.jsonl
  memory/profile.md
  memory/projects/<project_id>/PROJECT.md
  memory/episodes/yyyy/mm/<episode_id>.md
  memory/procedures/<skill_candidate>.md
  indexes/vector/
  indexes/graph/
  plugins/<plugin_id>/
  secrets/
```

## 7. Small-Model Implementation Rule

Every implementation task must be less than one coherent unit:
- one contract,
- one module skeleton,
- one tool,
- one test file,
- one adapter stub,
- or one prompt asset.

If a task requires more than five files changed, the build agent must split the task.

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
