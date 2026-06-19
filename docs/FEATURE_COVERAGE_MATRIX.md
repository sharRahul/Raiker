# Raiker Full Platform Feature Coverage Matrix

This document tracks Raiker feature coverage against modern agent platforms, local-first coding agents, memory systems, graph-context systems, GenAI security guidance, and local inference runtimes.

Raiker must not rely on vague phrases such as "support plugins", "web UI later", "memory later", "dashboard later", or "mobile later". Each capability must be documented with user experience, contracts, lifecycle rules, storage, permissions, event logging, verification requirements, UI surface, and phase placement.

No interface is privileged over another. CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled.

---

## Coverage Status Legend

| Status | Meaning |
|---|---|
| `fully-specified` | Behaviour is specified enough for a builder agent to implement without guessing. |
| `phase-scheduled` | Implementation is scheduled by phase, but the full behaviour is already specified in docs. |
| `phase-1-build` | Implement in Phase 1. |
| `phase-2-build` | Implement in Phase 2 according to the existing full specification. |
| `phase-3-build` | Implement in Phase 3 according to the existing full specification. |
| `phase-4-build` | Implement in Phase 4 according to the existing full specification. |
| `phase-5-build` | Implement in Phase 5 according to the existing full specification. |

A feature must never be marked as merely "future" without a full specification.

Specification status and implementation status are separate: `fully-specified` means the contract is complete enough to build, not that runtime/app behavior is currently shipped. Rows marked `phase-3-build` may still be contract-only, readiness-only, metadata-only, or deferred in the current implementation status column.

---

## Platform Coverage Summary

| Area | Spec status | Build phase | Current implementation status | Specification document |
|---|---:|---:|---|---|
| Implementation status ledger | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/IMPLEMENTATION_STATUS.md` |
| Builder dependency order | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/BUILD_ORDER.md` |
| Reference requirement mapping | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/REFERENCE_REQUIREMENTS_MATRIX.md` |
| Non-goals and boundaries | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/NON_GOALS_AND_BOUNDARIES.md` |
| Threat model | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/THREAT_MODEL.md`, `docs/SECURITY_AND_POLICY.md` |
| Acceptance tests by phase | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/ACCEPTANCE_TESTS_BY_PHASE.md`, `docs/VERIFICATION_PLAN.md` |
| API and contract schemas | fully-specified | phase-1-build | see status ledger for current implementation | `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/CONTRACTS.md` |
| Event catalog | fully-specified | phase-1-build | see status ledger for current implementation | `docs/EVENT_CATALOG.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Runtime state transition table | fully-specified | phase-1-build | see status ledger for current implementation | `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Equal primary interface invariant | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `README.md`, `docs/ARCHITECTURE.md`, `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Global `raiker` terminal command | fully-specified | phase-1-build | see status ledger for current implementation | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
| Interface action parity | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Model launch action | fully-specified | phase-1-to-2-build | see status ledger for current implementation | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/MODEL_PROVIDER_CONTRACT.md`, `config/model-profiles.json` |
| Agent gateway | fully-specified | phase-1-build | see status ledger for current implementation | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` |
| Deterministic runtime loop | fully-specified | phase-1-build | see status ledger for current implementation | `docs/ARCHITECTURE.md`, `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Context gathering | fully-specified | phase-1-build | see status ledger for current implementation | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Planning | fully-specified | phase-1-build | see status ledger for current implementation | `docs/RUNTIME_STATE_MACHINE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool broker | fully-specified | phase-1-build | see status ledger for current implementation | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Tool catalogue | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Permissions and approvals | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/SECURITY_AND_POLICY.md`, `docs/API_AND_CONTRACT_SCHEMAS.md` |
| Hooks | fully-specified | phase-2-build | see status ledger for current implementation | `docs/HOOKS_SPEC.md` |
| Plugins | fully-specified | phase-3-build | see status ledger for current implementation | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` |
| Channels | fully-specified | phase-3-to-5-build | see status ledger for current implementation | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
| Commands and slash commands | fully-specified | phase-1-to-2-build | see status ledger for current implementation | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich interactive TUI | fully-specified | phase-1-to-2-build | see status ledger for current implementation | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| TUI status bar | fully-specified | phase-2-build | see status ledger for current implementation | `docs/UI_UX_DESIGN_SPEC.md` |
| Async side questions during work | fully-specified | phase-2-to-4-build | see status ledger for current implementation | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Desktop UI | fully-specified | phase-3-build | contract-only/readiness-only; no launchable app | `docs/UI_UX_DESIGN_SPEC.md` |
| Web UI | fully-specified | phase-3-build | contract-only/readiness-only; no launchable app or event-stream UI | `docs/UI_UX_DESIGN_SPEC.md` |
| Dashboard | fully-specified | phase-3-build | contract-only/metadata-only; no launchable dashboard | `docs/UI_UX_DESIGN_SPEC.md` |
| IDE extension | fully-specified | phase-3-build | deferred; no extension runtime | `docs/UI_UX_DESIGN_SPEC.md` |
| Apple mobile app | fully-specified | phase-3-build | deferred; connector metadata only; no app runtime | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
| Android mobile app | fully-specified | phase-3-build | deferred; connector metadata only; no app runtime | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
| Voice UI | fully-specified | phase-4-build | see status ledger for current implementation | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Browser Extension | fully-specified | phase-4-build | see status ledger for current implementation | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Checkpoint and rewind | fully-specified | phase-2-build | see status ledger for current implementation | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Event log | fully-specified | phase-1-build | see status ledger for current implementation | `docs/EVENT_CATALOG.md`, `docs/CONTRACTS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Session resume/fork | fully-specified | phase-2-build | see status ledger for current implementation | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| SQLite storage | fully-specified | phase-1-to-2-build | see status ledger for current implementation | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| FTS5 search | fully-specified | phase-2-build | see status ledger for current implementation | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Memory governance | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Eidetic observation memory | fully-specified | phase-2-build | see status ledger for current implementation | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Gist memory | fully-specified | phase-2-build | see status ledger for current implementation | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Self-improving skills | fully-specified | phase-2-to-3-build | see status ledger for current implementation | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Semantic/vector memory | fully-specified | phase-3-build | readiness-only/preview-only; runtime writes/search deferred | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Graph memory/code map | fully-specified | phase-3-build | readiness-only/dry-run planning only; runtime indexing/query deferred | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Recursive CTE graph queries | fully-specified | phase-3-build | specified only; runtime query execution deferred | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Local inference | fully-specified | phase-2-build | see status ledger for current implementation | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/MODEL_PROVIDER_CONTRACT.md` |
| Hosted/cloud inference | fully-specified | phase-3-to-5-build | policy-gated/deferred; no hosted runtime enabled | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/MODEL_PROVIDER_CONTRACT.md` |
| Model router | fully-specified | phase-1-to-2-build | see status ledger for current implementation | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/MODEL_PROVIDER_CONTRACT.md` |
| Scheduled automations | fully-specified | phase-3-build | specified/deferred; no scheduler runtime | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| OpenClaw-style gateway and channels | fully-specified | phase-3-to-4-build | metadata/readiness-only; channel transports deferred | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/CHANNELS_SPEC.md` |
| Hermes-style learning loop | fully-specified | phase-2-to-4-build | see status ledger for current implementation | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Subagents | fully-specified | phase-4-build | see status ledger for current implementation | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Multi-agent teams | fully-specified | phase-4-to-5-build | see status ledger for current implementation | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Remote execution | fully-specified | phase-4-to-5-build | see status ledger for current implementation | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Container execution | fully-specified | phase-4-build | see status ledger for current implementation | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| SSH execution | fully-specified | phase-4-build | see status ledger for current implementation | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Cloud batch/GPU execution | fully-specified | phase-5-build | see status ledger for current implementation | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| OWASP LLM Top 10 controls | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/THREAT_MODEL.md` |
| Agentic AI threat controls | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/THREAT_MODEL.md` |
| Supply-chain controls | fully-specified | phase-3-to-5-build | see status ledger for current implementation | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` |
| Verification and test plan | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/VERIFICATION_PLAN.md`, `docs/ACCEPTANCE_TESTS_BY_PHASE.md` |
| Full phase implementation blueprint | fully-specified | phase-1-to-5-build | see status ledger for current implementation | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Capability Coverage

| Capability class | Raiker requirement |
|---|---|
| Equal primary interfaces | Every enabled human or programmatic interface can be the primary interface and must use the same gateway, contracts, policy, event log, and runtime. |
| Action parity | Prompts, side questions, approvals, task controls, model launch, channel linking, memory, graph/codemap, diagnostics, checkpoints, and settings must have equivalent action paths across enabled interfaces. |
| Interactive coding agent loop | Runtime must support plan/act/observe/verify with bounded tool calls and resumable checkpoints. |
| File tools | Read, write, edit, list, glob, grep, patch, diff, and delete must be tool-brokered and policy-gated. |
| Command execution | Local commands must require approval unless scoped policy permits them. |
| Search tools | Text search, semantic search, code-symbol search, graph search, and web search must be separate tools with separate policies. |
| Hooks | Lifecycle hooks must be available at session, prompt, tool, permission, task, subagent, file, config, compaction, and stop events. |
| Plugins | Plugins must package commands, hooks, skills, agents, channels, MCP servers, themes, and UI panels with manifests and permissions. |
| Channels | External clients must send `ChannelMessageEnvelope` into a session and receive replies or events through scoped permissions. |
| Commands | Slash commands, quick commands, local command proposals, file mentions, macros, aliases, and command expansion must be specified as interface-neutral actions. |
| TUI | Rich TUI must support background task progress, status bar, approval inbox, checkpoint timeline, and side questions without blocking running work. |
| Desktop/Web/Dashboard/Mobile | Full layouts, panels, widgets, auth/event-stream rules, mobile approval rules, and operational dashboard widgets must be specified before implementation. |
| Checkpoints | Checkpoints must support restore, fork, compare, summarise, clean up, and file-edit snapshots. |
| Permissions | Permission rules must support project/user/local/managed scopes, path patterns, tool names, argument patterns, interface/client identity, and time-limited approvals. |
| Memory | Memory must support profile, project, episodic, procedural, semantic, graph, scratchpad, eidetic observation, and gist memory with governance. |
| Learning loop | Verified task trajectories may become skills only through proposal, tests, and approval. |
| Storage | SQLite must store state/metadata; JSONL stores append-only events; SQLite FTS5/vector metadata/recursive CTEs support search and graph traversal. |
| Local models | Model runtime must support the llama.cpp server (native default), LM Studio, OpenAI-compatible providers, context limits, streaming, tool call formats, and quantisation profiles. vLLM is a later high-throughput GPU option. |

---

## Non-Negotiable Platform Invariants

1. All clients are equal-status primary clients of the gateway when implemented and enabled.
2. No interface is canonical over another interface.
3. All actions available in one primary interface must have equivalent action contracts in every other primary interface that supports the relevant capability.
4. No client executes tools directly.
5. No model output is trusted until validated.
6. All tool actions are policy-reviewed.
7. Hooks may influence decisions but may not silently bypass policy.
8. Plugins are disabled by default unless trusted or explicitly enabled.
9. Channels are untrusted input surfaces.
10. Memory writes are governed and auditable.
11. Checkpoints are not a Git replacement.
12. External execution is denied unless policy explicitly enables it.
13. Side questions must not corrupt or reorder the active task state regardless of originating interface.
14. Background tasks must be cancellable, observable, and event-logged.
15. Every feature must have tests, event types, contracts, storage notes, UI surfaces, and security notes before implementation.
16. Phase scheduling controls build order only; it does not permit vague requirements or interface hierarchy.

---

## Builder Agent Instruction

If a feature is listed here but no implementation task exists yet, the builder must add or update the relevant docs before coding. It must not invent behaviour in code first.

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Minimal terminal shell/status rendering only; rich panels are specified, not implemented as a full app. | Partial/minimal | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |

