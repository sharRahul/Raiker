# Reference Platform Compatibility Mapping

This document maps Raiker concepts to the reference systems and concepts used to shape the full platform specification.

Raiker is not a clone of any one system. It combines local-first agent runtime, coding-agent UX, hooks, plugins, channels, memory, graph context, local inference, self-improving skills, eidetic-style recall, and GenAI security into a governed architecture.

---

## Claude Code Concept Coverage

| Reference concept | Raiker specification |
|---|---|
| Agentic coding loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tools reference | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Interactive mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Rich terminal UX | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Checkpointing | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Hooks | `docs/HOOKS_SPEC.md` |
| Plugins | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Channels | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` |
| Commands | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| TUI-first command reference | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
| Session events | `docs/HOOKS_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool events | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/HOOKS_SPEC.md` |
| Permission requests | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Subagents/tasks | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Worktrees/execution | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Context compaction | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |

### Claude Code documentation — per-page mapping

Each reference page named in the review brief maps to a Raiker spec and a current code status.
Status: ✅ implemented · 🟡 partial/stub · 🔒 phase_scheduled_disabled · 📘 specified_not_implemented.

| Reference page | Raiker spec | Code status |
|---|---|---|
| `how-claude-code-works` (gather→act→verify loop, harness) | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/RUNTIME_STATE_MACHINE.md` | ✅ loop real; 🟡 verify/context stubs |
| `tools-reference` (built-in tools + permission per tool) | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` | ✅ read tools; write/shell approval-gated |
| `interactive-mode` (REPL, shortcuts, steer/interrupt) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ basic REPL |
| `commands` / slash commands (built-in + custom) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | ✅ 50+ inspection commands |
| `cli-reference` (flags: `--prompt`, `--workspace`, resume/fork) | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `README.md` | 🟡 `--prompt`/`--workspace` only |
| `checkpointing` (snapshot before edit, rewind, restore code/convo) | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` | 🟡 write real; restore plan-only |
| `hooks` (31 events; `command|http|mcp_tool|prompt|agent`; matchers; `if`) | `docs/HOOKS_SPEC.md` | 📘 spec only, no code |
| `plugins-reference` (`plugin.json`; skills/agents/hooks/MCP/LSP/monitors; marketplace) | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/PLUGIN_MANIFEST_SCHEMA.md` | 🔒 manifest validation only |
| `channels-reference` (MCP `claude/channel` capability; `notifications/claude/channel`; sender gating; permission relay) | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json` | 🔒 registry only |

> Alignment notes: the Claude Code hooks reference documents **31 events** (incl.
> `SessionStart`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PreCompact`, `PostCompact`,
> `SubagentStart/Stop`, `TaskCreated/Completed`) and **5 handler types**
> (`command`, `http`, `mcp_tool`, `prompt`, `agent`) with a three-level
> `EventName → matcher → hooks[]` config and an optional `if` condition. The channels reference
> models a channel as a **local MCP server** that declares `claude/channel`, emits
> `notifications/claude/channel`, gates inbound by **sender identity** (not room), and can opt
> into **permission relay** via `claude/channel/permission`. Raiker's specs should converge on
> these shapes; see `docs/HOOKS_SPEC.md` and `docs/CHANNELS_SPEC.md`.

---

## OpenClaw-Style Personal Agent Coverage

| Concept | Raiker specification |
|---|---|
| Local-first gateway/control plane | `docs/ARCHITECTURE.md`, `docs/CHANNELS_SPEC.md` |
| Multi-channel inbox | `docs/CHANNELS_SPEC.md`, `config/channel-connectors.json`, `docs/UI_UX_DESIGN_SPEC.md` |
| Channel pairing and sender allowlists | `docs/CHANNELS_SPEC.md`, `docs/SECURITY_AND_POLICY.md` |
| Channel-to-agent routing | `docs/CHANNELS_SPEC.md`, `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Gateway daemon mode | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Voice wake/talk mode equivalent | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Live canvas/workspace equivalent | `docs/UI_UX_DESIGN_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Companion apps/nodes | `docs/UI_UX_DESIGN_SPEC.md`, `docs/CHANNELS_SPEC.md` |
| Onboarding and connector setup | `docs/CHANNELS_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Skills from bundled/global/workspace scopes | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |
| Channel security diagnostics | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/VERIFICATION_PLAN.md` |

---

## Agent Framework Coverage

| Concept | Raiker specification |
|---|---|
| Tool-using agent loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Model-router/provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
| Global `raiker` TUI entry and in-TUI provider launch | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Structured tool proposal | `docs/CONTRACTS.md`, `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Verification/reflection | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Local-first inference support | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Full TUI with streaming output | `docs/UI_UX_DESIGN_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Interrupt and redirect | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Cross-channel conversation continuity | `docs/CHANNELS_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Closed learning loop | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill creation and skill improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| FTS5 session search with summaries | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| User modelling from confirmed facts | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Scheduled automations | `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Parallel subagents | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Multiple execution backends | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |

---

## Eidetic Memory Coverage

| Concept | Raiker specification |
|---|---|
| Raw observation capture | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Observation checksum and artifact reference | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Gist memory compression | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Exact replay with provenance | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Retention classes | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Memory deletion/forgetting | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Skill learning from trajectories | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Ruflo-Style Multi-Agent Coverage

| Concept | Raiker specification |
|---|---|
| Multi-agent teams | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Subagent roles | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Background task progress | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Team UI | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/UI_UX_DESIGN_SPEC.md` |
| Agent recursion limits | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` |
| Enterprise security/governance | `docs/OWASP_GENAI_SECURITY_MAPPING.md`, `docs/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md` |

---

## Graphify-Style Graph Context Coverage

| Concept | Raiker specification |
|---|---|
| Project graph extraction | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Symbols/entities/relations | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph queries | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Graph-backed context retrieval | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Staleness detection | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` |
| Recursive CTE traversal | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

---

## Skills Coverage

| Concept | Raiker specification |
|---|---|
| Procedural workflows | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill packaging | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill activation | `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill safety/verification | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Skill self-improvement | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

---

## Memory Coverage

| Concept | Raiker specification |
|---|---|
| User/profile memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Project memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Episodic memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Procedural memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Semantic/vector memory | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |
| Memory scoring/provenance | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Memory correction/forgetting | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Memory poisoning controls | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Eidetic observation and gist memory | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

---

## llama.cpp / Local Inference Coverage

| Concept | Raiker specification |
|---|---|
| Local inference profiles | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
| Provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| TUI model launch | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Context windows | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Quantisation/hardware notes | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Streaming | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |
| Tool-call modes for local models | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` |

---

## LangChain/LangGraph-Style Runtime Coverage

| Concept | Raiker specification |
|---|---|
| Agent framework vs runtime distinction | `docs/ARCHITECTURE.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Durable execution | `docs/CHECKPOINTING_AND_REWIND_SPEC.md` |
| Human-in-the-loop | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Streaming | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
| Persistence | `docs/CHECKPOINTING_AND_REWIND_SPEC.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Low-level orchestration | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |

---

## OWASP GenAI/LLM Security Coverage

| Concept | Raiker specification |
|---|---|
| Prompt injection | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Sensitive data disclosure | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Supply chain | `docs/PLUGIN_SYSTEM_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Memory/data poisoning | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Improper output handling | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Excessive agency | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| System prompt leakage | `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Vector/embedding weaknesses | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Misinformation | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/VERIFICATION_PLAN.md` |
| Unbounded consumption | `docs/RUNTIME_ORCHESTRATION_SPEC.md`, `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |

---

## Superpowers-Style Skills / Self-Improvement Coverage

Reference: `obra/Superpowers` — an agent accrues composable, reusable skills and invokes them on
demand. Mapped to Raiker's skills + self-improvement surfaces.

| Concept | Raiker specification |
|---|---|
| Reusable named skill unit | `docs/EXTENSIBILITY_MODEL.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill distilled from a successful trajectory | `docs/SELF_IMPROVEMENT_MODEL.md` |
| On-demand skill load (cheap until used) | `docs/EXTENSIBILITY_MODEL.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Skill activation gated by review | `docs/SELF_IMPROVEMENT_MODEL.md`, `docs/PLUGIN_SYSTEM_SPEC.md` |
| Skill safety/verification before reuse | `docs/SELF_IMPROVEMENT_MODEL.md`, `docs/VERIFICATION_PLAN.md` |
| Confidence/decay/forgetting of skills | `docs/SELF_IMPROVEMENT_MODEL.md` |

---

## mem0-Style Memory Coverage

Reference: `mem0ai/mem0` — a universal memory layer with `add`/`search`/`retrieve` over user,
session, and agent scopes, using hybrid retrieval (semantic embeddings + keyword/BM25 + entity
linking) and provenance.

| mem0 concept | Raiker specification |
|---|---|
| `add` memory from interactions (candidate-first) | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| `search` (semantic + keyword hybrid) | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS5 + vector metadata) |
| `retrieve` filtered by scope/metadata | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| User / session / agent memory scopes | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Provenance + confidence scoring | `docs/MEMORY_GOVERNANCE_RULES.md` |
| Update / correct / forget | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |
| Self-hosted/local-first deployment | `docs/ARCHITECTURE.md` (local-first, SQLite-backed) |

Raiker difference: memory writes are **candidate-first and governance-gated**, and durable
semantic/vector writes are currently disabled (`raiker/memory/readiness.py`).

---

## memsearch-Style Semantic Search Coverage

Reference: `zilliztech/memsearch` — embedding-backed semantic memory/search over an agent's
history with a vector index.

| Concept | Raiker specification |
|---|---|
| Embedding-backed memory index | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (vector metadata tables) |
| Semantic retrieval over session history | `docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |
| Hybrid lexical + vector ranking | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` (FTS5 + vector) |
| Sensitivity/provenance filters on retrieval | `docs/MEMORY_GOVERNANCE_RULES.md`, `docs/OWASP_GENAI_SECURITY_MAPPING.md` |
| Vector store backend abstraction | `docs/STORAGE_DATABASE_AND_SEARCH_SPEC.md` |

Raiker difference: vector writes, embedding creation, and background indexing are
phase-scheduled and **disabled** until governance, approval-preview, and retention controls land.

---

## Rule For New References

When Raiker adopts a concept from another platform, the docs must add concept name, Raiker behaviour, contract/schema, lifecycle, storage, security rules, events, tests, UI surface, and build phase.

If these are not present, the concept is not considered fully specified.
