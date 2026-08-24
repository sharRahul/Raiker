# Reference Requirements Matrix

This document maps reference agent-platform concepts into Raiker requirements. It exists to prevent shallow imitation: if Raiker borrows an idea from coding agents, local-first tools, model runtimes, memory systems, plugin systems, channel gateways, graph/codemap tools, or OWASP GenAI controls, the requirement must be mapped to a Raiker contract, event, storage location, policy rule, test, and build phase.

Reference systems are inspiration only. Raiker's source of truth is this repository's documentation.

---

## Mapping Rules

Each reference capability must map to:

1. Raiker capability name;
2. build phase;
3. canonical spec file;
4. contracts affected;
5. storage affected;
6. events emitted;
7. policy/security controls;
8. acceptance tests;
9. out-of-scope notes.

If any field is missing, the requirement is not builder-proof.

---

## Core Agent Runtime Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Agentic loop: gather context, act, observe, verify | Deterministic runtime state machine with context, planning, policy, execution, observation, verification, response, checkpoint | Phase 1 | `docs/architecture/RUNTIME_STATE_MACHINE.md`, `docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md` | State transition and event sequence tests |
| Tool-mediated local work | Tool Broker is the only path to filesystem/search/command actions | Phase 1 | `docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md` | Broker tests prove no tool runs without policy |
| Permissioned actions | Static policy returns `allow`, `deny`, or `needs_approval` | Phase 1 | `docs/architecture/SECURITY_AND_POLICY.md` | Policy tests for allow/deny/approval |
| Approval-gated risky actions | Approval request bound to exact action ID | Phase 1 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Approval mismatch tests |
| Append-only audit | JSONL events plus SQLite index | Phase 1 | `docs/architecture/EVENT_CATALOG.md`, `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Event append/index tests |
| Checkpoint/resume | Checkpoint manifest after completed turn; later restore/fork | Phase 1-2 | `docs/architecture/CHECKPOINTING_AND_REWIND_SPEC.md` | Checkpoint write/read and restore approval tests |
| Interruptible work | Pause/cancel/steer and side questions at safe boundaries | Phase 2 | `docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md` | Side question and safe-boundary tests |

---

## Interface And Client Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Terminal coding agent | `raiker` launches first local terminal client | Phase 1 | `README.md`, `docs/architecture/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | Global command smoke test |
| Rich local workspace | TUI panels for task, approval, checkpoint, event, memory, model, permission, diagnostics | Phase 2 | `docs/architecture/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md` | TUI event-driven panel tests |
| Desktop/web dashboard | Local app surfaces for sessions, tasks, approvals, events, memory, graph, plugins, channels | Phase 3 | `docs/architecture/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md` | Gateway parity and event stream tests |
| Mobile app control | Apple/Android apps are equal primary interfaces, not notification-only companions | Phase 3 | `docs/architecture/WEB_UI_CONTROL_DECK_PLAN.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md`, `docs/architecture/CHANNELS_SPEC.md` | Stale mobile approval rejection tests |
| Chat/channel access | External messages normalise into ChannelMessageEnvelope and gateway path | Phase 4 | `docs/architecture/CHANNELS_SPEC.md` | Pairing, sender trust, rate-limit tests |
| Interface parity | Every enabled interface uses same action contracts and policy path | Phase 1-5 | `docs/architecture/FEATURE_COVERAGE_MATRIX.md` | Equal-interface invariant tests |

---

## Model Runtime Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Deterministic test model | `mock` model provider for offline tests | Phase 1 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Mock provider deterministic tests |
| Local model providers | Ollama (`gemma4:31b-cloud` native default), llama.cpp server, LM Studio, OpenAI-compatible local endpoints | Phase 2 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `raiker/config/model-profiles.json` | Provider profile and chat/tool-call tests |
| Hosted provider controls | Hosted providers disabled until privacy/egress/budget policy allows | Phase 3-5 | `docs/architecture/SECURITY_AND_POLICY.md`, `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Hosted fallback denied tests |
| Tool-call parsing | Model output parsed as untrusted structured proposal | Phase 1-2 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Invalid model tool call tests |
| Context limits | Context budget and source priority before model calls | Phase 2 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Truncation priority tests |

---

## Memory, Graph, And Learning Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Working memory | Current-turn scratchpad and task context | Phase 1 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Context gatherer tests |
| Durable memory | Profile/project/episodic/procedural memory with governance | Phase 2 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Memory approval and provenance tests |
| Eidetic observation | Raw observation metadata with retention and gist memory | Phase 2 | `docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` | Retention and gist creation tests |
| Semantic search | Local vector metadata with sensitivity/provenance filters | Phase 3 | `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Sensitivity-filtered retrieval tests |
| Graph/codemap | SQLite graph nodes/edges plus recursive CTEs | Phase 3 | `docs/architecture/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Impact-analysis CTE tests |
| Skill learning | Verified task trajectory may become proposed skill only after tests and approval | Phase 2-3 | `docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Skill proposal/approval tests |

---

## Plugin, Hook, And Extension Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Lifecycle hooks | Hook events with bounded decision authority | Phase 2 | `docs/architecture/HOOKS_SPEC.md` | Hook cannot bypass managed deny |
| Plugin manifest | Explicit manifest, permissions, trust, supply-chain metadata | Phase 3 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Manifest validation tests |
| Permission diff | Show expanded permissions before enable/update | Phase 3 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Permission diff tests |
| Plugin tools | Plugin tools register through broker only | Phase 3 | `docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md` | Plugin tool broker-route tests |
| Plugin channels | Channel plugins require pairing/sender policy | Phase 3-4 | `docs/architecture/CHANNELS_SPEC.md` | Unknown sender rejection tests |

---

## Execution And Multi-Agent Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Subagents | Bounded specialist agents with parent verification | Phase 4 | `docs/architecture/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Parent verification and cancellation tests |
| Multi-agent teams | Planner/executor/critic patterns with limits | Phase 4-5 | `docs/architecture/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Budget/depth/runtime tests |
| Worktree/container execution | Explicit execution profiles with snapshots/artifacts | Phase 4 | `docs/architecture/EXECUTION_ENVIRONMENTS_SPEC.md` | Profile and cleanup tests |
| SSH/VPS/Kubernetes/cloud execution | Policy-gated remote execution with resource/cost controls | Phase 4-5 | `docs/architecture/EXECUTION_ENVIRONMENTS_SPEC.md` | Egress/resource/budget tests |

---

## OWASP GenAI Security Requirements

| Risk area | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Prompt injection | Treat prompts/files/tool outputs/channel messages as untrusted | Phase 1-5 | `docs/architecture/THREAT_MODEL.md`, `docs/architecture/OWASP_GENAI_SECURITY_MAPPING.md` | Injection fixture tests |
| Sensitive information disclosure | Redact secrets and block unsafe egress | Phase 1-5 | `docs/architecture/SECURITY_AND_POLICY.md` | Secret redaction and hosted-deny tests |
| Supply chain | Dependencies/plugins/providers need provenance and trust controls | Phase 3-5 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Signature/checksum and permission-diff tests |
| Excessive agency | Bounded tools, approvals, subagent limits, budgets | Phase 1-5 | `docs/architecture/THREAT_MODEL.md` | Approval, depth, budget, cancellation tests |
| Insecure output handling | Model output is parsed, validated, and policy-reviewed | Phase 1-5 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Invalid structured output tests |
| Data poisoning | Memory and graph writes require provenance and trust labels | Phase 2-5 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Poisoned memory candidate tests |

---

## Builder Use

When implementing a feature, use this matrix to answer:

- Which reference concept am I implementing?
- Which Raiker requirement owns it?
- Which build phase allows active wiring?
- Which contract/event/storage/policy docs apply?
- Which tests prove it is complete?
- Which phase-scheduled boundaries must remain disabled?

If the answer is unclear, update the docs before coding.
