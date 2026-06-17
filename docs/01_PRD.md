# 01 Product Requirements Document

## 1. Vision

Build a standalone local-first AI agent platform that combines the useful behaviour of terminal coding agents, long-term memory systems, plugin frameworks, local LLM runtimes, graph-based project understanding, secure execution sandboxes, and OS-like audit logging.

The platform must be usable at home on consumer hardware and also adaptable to enterprise governance. It must be safe enough to run on a personal machine that contains source code, documents, credentials, SSH keys, browser data, and private memory.

## 2. Product Promise

The user can ask for work from any interface. The agent gathers context, proposes a plan when needed, asks for permission before risky actions, acts through approved tools, verifies the result, records every action, and remembers durable facts only through governed memory.

## 3. Primary User Experience

```text
User prompt
  -> normalise input
  -> classify intent and risk
  -> gather context
  -> plan when required
  -> policy review
  -> tool/subagent/action execution
  -> result verification
  -> final response
  -> checkpoint
  -> event log
  -> governed memory update
```

## 4. Personas

### 4.1 Home Power User
- Runs local model on limited hardware.
- Wants privacy-first automation.
- Wants long-term memory over years.
- Wants local files, scripts, NAS, home lab, and development tasks supported.

### 4.2 Developer
- Wants repository analysis, code edits, tests, refactors, code review, and PR assistance.
- Needs deterministic behaviour and minimal hallucination.
- Wants to see exact files changed and verification run.

### 4.3 Security Professional
- Needs prompt-injection defence, egress controls, plugin trust, secrets scanning, and audit logs.
- Wants security-review agents and SARIF output.

### 4.4 Enterprise Administrator
- Needs policy bundles, SSO/OIDC, central plugin registry, audit export, tenant separation, and managed defaults.

### 4.5 Plugin/Skill Author
- Wants a documented extension layout for skills, agents, hooks, commands, MCP servers, and channels.

## 5. Product Requirements

### PR-001 Equal-Status Interfaces
The system must expose CLI, Chat, Rich TUI, Desktop, Web, IDE, Voice, Hotkeys, REST, and Webhooks as equal-status clients.

Acceptance criteria:
- Every interface submits the same PromptEnvelope contract.
- Every interface receives the same AgentEvent stream.
- Permission prompts can be routed back to the originating interface or an approved control interface.
- Chat and webhook inputs are untrusted unless sender-gated.

### PR-002 Agent Core Loop
The agent core must implement a bounded, interruptible, steerable loop.

Required phases:
1. Intake.
2. Intent classification.
3. Risk classification.
4. Context gathering.
5. Context validation.
6. Planning.
7. Policy review.
8. Tool or subagent action.
9. Verification.
10. Final response.
11. Checkpoint.
12. Event logging.
13. Memory governance.

### PR-003 Model Router
The system must support:
- Local llama.cpp.
- Ollama.
- LM Studio.
- OpenRouter or other OpenAI-compatible endpoints.
- Anthropic/OpenAI-style hosted APIs.
- Modal-hosted inference.
- Custom model provider plugins.

The router must track context length, tool-calling support, JSON/structured output support, embedding support, vision support, privacy classification, latency, and estimated cost.

### PR-004 Tool Broker
The tool broker must own all tool execution. No tool may execute directly from model output.

Tool families:
- File read/write/edit/list/delete.
- Grep/glob/search.
- Shell/PowerShell.
- Git/worktree.
- LSP/code intelligence.
- Notebook tools.
- Memory tools.
- Graph query tools.
- Web fetch/search.
- Subagent spawning.
- Ask-user clarification.
- Docker, SSH, Daytona, Modal, external hosting execution.

### PR-005 Hooks
The hook engine must support lifecycle automation for session start/end, user prompt submit, pre/post tool use, permission request/denial, subagent start/stop, memory write, checkpoint, file changed, config changed, and stop/failure.

### PR-006 Plugins and Skills
Plugins must be manifest-driven and permission-scoped. Skills must be reusable prompt workflows with optional reference docs, examples, scripts, and tests.

### PR-007 Memory
Memory must be durable, searchable, editable, exportable, and forgettable.

Memory layers:
- Profile memory.
- Project memory.
- Episodic memory.
- Procedural memory.
- Semantic memory.
- Graph memory.

Every memory must include source, timestamp, confidence, sensitivity, retention, trust score, and approval state.

### PR-008 Event Logging
The system must log actions like an operating system activity journal.

Required events:
- Prompt submitted.
- Context gathered.
- Model call.
- Plan proposed.
- Tool proposed.
- Permission requested.
- Permission approved/denied.
- Tool started/result/failure.
- Hook started/result/failure.
- Subagent started/stopped.
- Checkpoint created/restored.
- Memory candidate/write/rejection.
- Verification result.
- Error.
- Security event.

### PR-009 Security and Privacy
The system must map controls to OWASP GenAI and LLM risks, including prompt injection, sensitive disclosure, supply chain, poisoning, output handling, excessive agency, system prompt leakage, vector weaknesses, misinformation, and unbounded consumption.

### PR-010 External Execution
External execution must be explicit and governed.

Targets:
- Local native runner.
- Docker.
- SSH.
- Daytona sandbox.
- Modal serverless/GPU/batch.
- External hosted deployment.

The agent must never send code, memory, secrets, logs, or prompts to remote systems without policy approval.

## 6. Out of Scope for Early MVP

- Autonomous payments or purchases.
- Unrestricted browser or desktop control.
- Autonomous production infrastructure changes.
- Multi-user enterprise tenancy without access controls.
- Plugin marketplace with public submissions.

## 7. Success Metrics

- 100% high-risk actions produce permission and audit events.
- 100% remote egress is logged and policy-checked.
- Memory survives restart and supports deletion.
- Prompt injection test suite passes.
- Secrets are blocked or redacted before remote calls.
- A constrained local model can execute Phase 1 tasks using only the implementation plan.

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
