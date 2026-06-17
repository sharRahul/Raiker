# Raiker Full Platform Feature Coverage Matrix

This document tracks Raiker feature coverage against modern agent platforms, local-first coding agents, memory systems, graph-context systems, GenAI security guidance, and local inference runtimes.

Raiker must not rely on vague phrases such as "support plugins", "web UI later", "memory later", or "dashboard later". Each capability must be documented with user experience, contracts, lifecycle rules, storage, permissions, event logging, verification requirements, UI surface, and phase placement.

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

---

## Platform Coverage Summary

| Area | Spec status | Build phase | Specification document |
|---|---:|---:|---|
| Global `raiker` command | fully-specified | phase-1-build | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
| Model launch command | fully-specified | phase-1-to-2-build | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
| Agent gateway | fully-specified | phase-1-build | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` |
| Deterministic runtime loop | fully-specified | phase-1-build | `docs/ARCHITECTURE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Context gathering | fully-specified | phase-1-build | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Planning | fully-specified | phase-1-build | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool broker | fully-specified | phase-1-build | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Tool catalogue | fully-specified | phase-1-to-5-build | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Permissions and approvals | fully-specified | phase-1-to-5-build | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/SECURITY_AND_POLICY.md` |
| Hooks | fully-specified | phase-2-build | `docs/HOOKS_SPEC.md` |
| Plugins | fully-specified | phase-3-build | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Channels | fully-specified | phase-3-to-5-build | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
| Commands and slash commands | fully-specified | phase-1-to-2-build | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich interactive TUI | fully-specified | phase-2-build | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| TUI status bar | fully-specified | phase-2-build | `docs/UI_UX_DESIGN_SPEC.md` |
| Async side questions during work | fully-specified | phase-2-to-4-build | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Desktop UI | fully-specified | phase-3-build | `docs/UI_UX_DESIGN_SPEC.md` |
| Web UI | fully-specified | phase-3-build | `docs/UI_UX_DESIGN_SPEC.md` |
| Dashboard | fully-specified | phase-3-build | `docs/UI_UX_DESIGN_SPEC.md` |
| IDE extension | fully-specified | phase-3-build | `docs/UI_UX_DESIGN_SPEC.md` |
| Voice UI | fully-specified | phase-4-build | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Checkpoint and rewind | fully-specified | phase-2-build | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Event log | fully-specified | phase-1-build | `docs/CONTRACTS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Session resume/fork | fully-specified | phase-2-build | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| SQLite storage | fully-specified | phase-1-to-2-build | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| FTS5 search | fully-specified | phase-2-build | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Eidetic observation memory | fully-specified | phase-2-build | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Gist memory | fully-specified | phase-2-build | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Self-improving skills | fully-specified | phase-2-to-3-build | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Semantic/vector memory | fully-specified | phase-3-build | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Graph memory/code map | fully-specified | phase-3-build | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Recursive CTE graph queries | fully-specified | phase-3-build | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Local inference | fully-specified | phase-2-build | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Hosted/cloud inference | fully-specified | phase-3-to-5-build | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Model router | fully-specified | phase-1-to-2-build | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Scheduled automations | fully-specified | phase-3-build | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| OpenClaw-style gateway and channels | fully-specified | phase-3-to-4-build | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/CHANNELS_SPEC.md` |
| Hermes-style learning loop | fully-specified | phase-2-to-4-build | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Subagents | fully-specified | phase-4-build | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Multi-agent teams | fully-specified | phase-4-to-5-build | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Remote execution | fully-specified | phase-4-to-5-build | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Container execution | fully-specified | phase-4-build | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| SSH execution | fully-specified | phase-4-build | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Cloud batch/GPU execution | fully-specified | phase-5-build | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| OWASP LLM Top 10 controls | fully-specified | phase-1-to-5-build | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Agentic AI threat controls | fully-specified | phase-1-to-5-build | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Supply-chain controls | fully-specified | phase-3-to-5-build | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Verification and test plan | fully-specified | phase-1-to-5-build | `docs/VERIFICATION_PLAN.md` |
| Full phase implementation blueprint | fully-specified | phase-1-to-5-build | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Capability Coverage

| Capability class | Raiker requirement |
|---|---|
| Interactive coding agent loop | Runtime must support plan/act/observe/verify with bounded tool calls and resumable checkpoints. |
| File tools | Read, write, edit, list, glob, grep, patch, diff, and delete must be tool-brokered and policy-gated. |
| Command execution | Local commands must require approval unless scoped policy permits them. |
| Search tools | Text search, semantic search, code-symbol search, graph search, and web search must be separate tools with separate policies. |
| Hooks | Lifecycle hooks must be available at session, prompt, tool, permission, task, subagent, file, config, compaction, and stop events. |
| Plugins | Plugins must package commands, hooks, skills, agents, channels, MCP servers, themes, and UI panels with manifests and permissions. |
| Channels | External clients must send `ChannelMessageEnvelope` into a session and receive replies or events through scoped permissions. |
| Commands | Slash commands, quick commands, local command proposals, file mentions, macros, aliases, and command expansion must be specified. |
| TUI | Rich TUI must support background task progress, status bar, approval inbox, checkpoint timeline, and side questions without blocking running work. |
| Desktop/Web/Dashboard | Full layouts, panels, widgets, auth/event-stream rules, and operational dashboard widgets must be specified before implementation. |
| Checkpoints | Checkpoints must support restore, fork, compare, summarise, clean up, and file-edit snapshots. |
| Permissions | Permission rules must support project/user/local/managed scopes, path patterns, tool names, argument patterns, and time-limited approvals. |
| Memory | Memory must support profile, project, episodic, procedural, semantic, graph, scratchpad, eidetic observation, and gist memory with governance. |
| Learning loop | Verified task trajectories may become skills only through proposal, tests, and approval. |
| Storage | SQLite must store state/metadata; JSONL stores append-only events; SQLite FTS5/vector metadata/recursive CTEs support search and graph traversal. |
| Local models | Model runtime must support llama.cpp, Ollama, LM Studio, OpenAI-compatible providers, context limits, streaming, tool call formats, and quantisation profiles. |

---

## Non-Negotiable Platform Invariants

1. All clients are equal-status clients of the gateway.
2. No client executes tools directly.
3. No model output is trusted until validated.
4. All tool actions are policy-reviewed.
5. Hooks may influence decisions but may not silently bypass policy.
6. Plugins are disabled by default unless trusted or explicitly enabled.
7. Channels are untrusted input surfaces.
8. Memory writes are governed and auditable.
9. Checkpoints are not a Git replacement.
10. External execution is denied unless policy explicitly enables it.
11. Rich TUI side questions must not corrupt or reorder the active task state.
12. Background tasks must be cancellable, observable, and event-logged.
13. Every feature must have tests, event types, contracts, storage notes, UI surfaces, and security notes before implementation.
14. Phase scheduling controls build order only; it does not permit vague requirements.

---

## Builder Agent Instruction

If a feature is listed here but no implementation task exists yet, the builder must add or update the relevant docs before coding. It must not invent behaviour in code first.
