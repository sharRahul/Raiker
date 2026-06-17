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
| CLI reference | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
| Session events | `docs/HOOKS_SPEC.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Tool events | `docs/TOOLS_AND_PERMISSIONS_SPEC.md`, `docs/HOOKS_SPEC.md` |
| Permission requests | `docs/TOOLS_AND_PERMISSIONS_SPEC.md` |
| Subagents/tasks | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`, `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Worktrees/execution | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` |
| Context compaction | `docs/MEMORY_AND_CONTEXT_STRATEGY.md` |

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

## Hermes-Agent / Agent Framework Coverage

| Concept | Raiker specification |
|---|---|
| Tool-using agent loop | `docs/RUNTIME_ORCHESTRATION_SPEC.md` |
| Model-router/provider abstraction | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `config/model-profiles.json` |
| Global CLI command and provider launch | `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, `docs/ARCHITECTURE.md` |
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
| Global launch | `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` |
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

## Rule For New References

When Raiker adopts a concept from another platform, the docs must add concept name, Raiker behaviour, contract/schema, lifecycle, storage, security rules, events, tests, UI surface, and build phase.

If these are not present, the concept is not considered fully specified.
