# Raiker Full Platform Feature Coverage Matrix

This document tracks Raiker feature coverage against modern agent platforms, local-first coding agents, memory systems, graph-context systems, GenAI security guidance, and local inference runtimes.

Raiker must not rely on vague phrases such as "support plugins" or "support memory". Each capability must be documented with contracts, lifecycle rules, permissions, event logging, verification requirements, and phase boundaries.

---

## Coverage Status Legend

| Status | Meaning |
|---|---|
| `specified` | Behaviour is fully specified enough for a builder agent to implement without guessing. |
| `phase-boundary` | The feature is intentionally postponed, but the contract/boundary is documented. |
| `stub-required` | The codebase must include interfaces/stubs now, but full implementation is later. |
| `not-allowed-in-phase-1` | Builder agents must not implement this in Phase 1. |

---

## Platform Coverage Summary

| Area | Required Raiker status | Specification document |
|---|---:|---|
| Agent gateway | specified | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` |
| Deterministic runtime loop | specified | `docs/ARCHITECTURE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Context gathering | specified | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Planning | specified | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool broker | specified | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Tool catalogue | specified | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Permissions and approvals | specified | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/SECURITY_AND_POLICY.md` |
| Hooks | specified | `docs/HOOKS_SPEC.md` |
| Plugins | specified | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Channels | specified | `docs/CHANNELS_SPEC.md` |
| Commands and slash commands | specified | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich interactive TUI | specified | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Async side questions during work | specified | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Checkpoint and rewind | specified | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Event log | specified | `docs/CONTRACTS.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Session resume/fork | specified | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Local inference | specified | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Hosted/cloud inference | specified with policy gates | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Model router | specified | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Memory governance | specified | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Semantic/vector memory | phase-boundary | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Graph memory/code map | phase-boundary | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Skills/procedural workflows | specified | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Subagents | specified | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Multi-agent teams | phase-boundary | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Remote execution | phase-boundary | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Docker execution | phase-boundary | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| SSH execution | phase-boundary | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Cloud batch/GPU execution | phase-boundary | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| OWASP LLM Top 10 controls | specified | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Agentic AI threat controls | specified | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Supply-chain controls | specified | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Verification and test plan | specified | `docs/VERIFICATION_PLAN.md` |
| Roadmap | specified | `docs/ROADMAP_PHASE_2_TO_PHASE_5.md` |

---

## Claude-Code-Level Capability Coverage

Raiker must cover these equivalent capability classes:

| Capability class | Raiker requirement |
|---|---|
| Interactive coding agent loop | Runtime must support plan/act/observe/verify with bounded tool calls and resumable checkpoints. |
| File tools | Read, write, edit, list, glob, grep, patch, diff, and delete must be tool-brokered and policy-gated. |
| Shell tools | Shell and PowerShell must require explicit approval unless policy grants scoped allowlist. |
| Search tools | Text search, semantic search, code-symbol search, graph search, and web search must be separate tools with separate policies. |
| Hooks | Lifecycle hooks must be available at session, prompt, tool, permission, task, subagent, file, config, compaction, and stop events. |
| Plugins | Plugins must package commands, hooks, skills, agents, channels, MCP servers, themes, and UI panels with manifests and permissions. |
| Channels | External clients must send `ChannelMessageEnvelope` into a session and receive replies or events through scoped permissions. |
| Commands | Slash commands, quick commands, shell passthrough, file mentions, macros, aliases, and command expansion must be specified. |
| TUI | Rich TUI must support background task progress and allow user side questions without blocking running work. |
| Checkpoints | Checkpoints must support restore, fork, compare, summarise, clean up, and file-edit snapshots. |
| Permissions | Permission rules must support project/user/local/managed scopes, path patterns, tool names, argument patterns, and time-limited approvals. |
| Memory | Memory must support profile, project, episodic, procedural, semantic, graph, and scratchpad memory with governance. |
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
13. Every feature must have tests, event types, contracts, and security notes before implementation.

---

## Builder Agent Instruction

If a feature is listed here but no implementation task exists yet, the builder must add or update the relevant docs before coding. It must not invent behaviour in code first.
