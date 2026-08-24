# Architecture and implementation reference

This directory contains Raiker's technical source documents: the architecture,
runtime contracts, security boundaries, implementation status, verification
requirements, and historical design records. User workflows belong in the
[user guide](../guide/README.md).

## Canonical documents

Prefer these when another technical document disagrees:

| Question | Canonical document |
|---|---|
| What are the components and governed action flow? | [Architecture](ARCHITECTURE.md) |
| What is implemented right now? | [Implementation status](IMPLEMENTATION_STATUS.md) |
| What are the trust boundaries and fail-closed controls? | [Security architecture](SECURITY_ARCHITECTURE.md) |
| What is the security philosophy? | [Security and policy](SECURITY_AND_POLICY.md) |
| What can the current build not do? | [Known limits](KNOWN_LIMITS.md) |
| What does the web API expose? | [API and contract schemas](API_AND_CONTRACT_SCHEMAS.md) |
| How does Raiker compare with reference platforms? | [Reference platform compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md) |
| What tools and capabilities exist? | [Tool and plugin catalog](RAIKER_TOOL_AND_PLUGIN_CATALOG.md) |

The comparison matrix lives only in
[Reference platform compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md).
Historical review passes belong in [Reference review log](REFERENCE_REVIEW_LOG.md).

## Product surfaces

| Topic | Document |
|---|---|
| Build coding workspace | [Build workspace](BUILD_WORKSPACE_SPEC.md) |
| Build turn protocol | [Raiker Build process](RAIKER_BUILD_PROCESS.md) |
| Terminal commands and interactive mode | [Commands and interactive mode](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) |
| Web dashboard behavior | [Web UI control deck](WEB_UI_CONTROL_DECK_PLAN.md) |
| Visual language and responsive layout | [Visual design](VISUAL_DESIGN_SPEC.md) |
| Application host, startup, updates, and packaging | [Desktop distribution](DESKTOP_DISTRIBUTION_DESIGN.md) |

## Runtime, governance, and contracts

| Topic | Document |
|---|---|
| Ask, Deny, Allow, and Auto | [Decision modes](DECISION_MODES_SPEC.md) |
| Validation, classification, and routing | [Tools and permissions](TOOLS_AND_PERMISSIONS_SPEC.md) |
| Executor registration and capability activation | [Runtime executors](RUNTIME_EXECUTORS_SPEC.md) |
| Turn orchestration | [Runtime orchestration](RUNTIME_ORCHESTRATION_SPEC.md) |
| Turn lifecycle | [Runtime state machine](RUNTIME_STATE_MACHINE.md) |
| Nested control boundaries | [Nested boundaries architecture](NESTED_BOUNDARIES_ARCHITECTURE.md) |
| Stable identifiers and record shapes | [Contracts](CONTRACTS.md) |
| Audit events | [Event catalog](EVENT_CATALOG.md) |
| Checkpoint capture, restore, resume, and fork | [Checkpointing and rewind](CHECKPOINTING_AND_REWIND_SPEC.md) |

The cross-cutting map of every authority entry path is maintained in
[Governance entry paths](../plans/GOVERNANCE_ENTRY_PATHS.md).

## Memory, context, storage, and knowledge

| Topic | Document |
|---|---|
| Memory scopes and context policy | [Memory and context strategy](MEMORY_AND_CONTEXT_STRATEGY.md) |
| Durable-memory write rules | [Memory governance](MEMORY_GOVERNANCE_RULES.md) |
| Observation capture and gist compression | [Eidetic memory and learning](EIDETIC_MEMORY_AND_LEARNING_SPEC.md) |
| Knowledge graph and repository code map | [Graph memory and codemap](GRAPH_MEMORY_AND_CODEMAP_SPEC.md) |
| Persistence and retrieval | [Storage, database, and search](STORAGE_DATABASE_AND_SEARCH_SPEC.md) |
| Archive-first hybrid memory design | [Hybrid memory plan](HYBRID_MEMORY_IMPLEMENTATION_PLAN.md) |

Current recall gaps and planned reliability work are tracked in
[Memory reliability plan](../plans/MEMORY_RELIABILITY_PLAN.md).

## Models and execution environments

| Topic | Document |
|---|---|
| Providers, readiness, acquisition, and local inference | [Models and local inference](MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) |
| Provider adapter interface | [Model provider contract](MODEL_PROVIDER_CONTRACT.md) |
| Local, sandbox, container, SSH, and cloud execution | [Execution environments](EXECUTION_ENVIRONMENTS_SPEC.md) |
| Subagents and coordinated teams | [Multi-agent and subagent strategy](MULTI_AGENT_AND_SUBAGENT_STRATEGY.md) |

## Extensibility

| Topic | Document |
|---|---|
| Shared model for tools, hooks, skills, plugins, and channels | [Extensibility model](EXTENSIBILITY_MODEL.md) |
| Hook events, matchers, handlers, and authority | [Hooks](HOOKS_SPEC.md) |
| Plugin contributions and lifecycle | [Plugin system](PLUGIN_SYSTEM_SPEC.md) |
| Strict plugin metadata | [Plugin manifest schema](PLUGIN_MANIFEST_SCHEMA.md) |
| External messaging boundaries | [Channels](CHANNELS_SPEC.md) |
| Governed self-observation and learning | [Self-improvement model](SELF_IMPROVEMENT_MODEL.md) |

## Security

| Topic | Document |
|---|---|
| Assets, attackers, threats, and mitigations | [Threat model](THREAT_MODEL.md) |
| Owner-centered zero-trust rules | [User-centric zero-trust policy](USER_CENTRIC_ZERO_TRUST_POLICY.md) |
| OWASP LLM/GenAI Top 10 coverage | [OWASP GenAI mapping](OWASP_GENAI_SECURITY_MAPPING.md) |
| OWASP Agentic Top 10 coverage | [OWASP Agentic mapping](OWASP_AGENTIC_TOP10_MAPPING.md) |
| Per-capability threat models | [Threat-model index](../threat-models/README.md) |

## Verification and status

| Topic | Document |
|---|---|
| CI and local verification | [Verification plan](VERIFICATION_PLAN.md) |
| Pre-commit validation | [Local validation gate](LOCAL_VALIDATION_GATE.md) |
| Concise feature coverage | [Feature coverage matrix](FEATURE_COVERAGE_MATRIX.md) |
| Deferred work and open gaps | [Gap and TODO analysis](GAP_AND_TODO_ANALYSIS.md) |
| Acceptance tests by phase | [Acceptance tests by phase](ACCEPTANCE_TESTS_BY_PHASE.md) |
| Real-provider web-app testing | [Web app live test](WEB_APP_LIVE_TEST.md) |

Browser procedures and dated evidence are stored under [plans](../plans/).

## Development records

| Topic | Document |
|---|---|
| Standing implementation brief | [Handoff](HANDOFF.md) |
| Architecture-decision template | [ADR template](ADR_TEMPLATE.md) |
| Dependency-safe implementation sequence | [Build order](BUILD_ORDER.md) |
| Original phase blueprint | [Full phase implementation blueprint](FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md) |
| Small-step local-model development guide | [Local LLM builder guide](LOCAL_LLM_BUILDER_GUIDE.md) |
| Reference concept-to-requirement mapping | [Reference requirements matrix](REFERENCE_REQUIREMENTS_MATRIX.md) |
| Dated reference research | [Reference review log](REFERENCE_REVIEW_LOG.md) |
| Product boundaries and non-goals | [Non-goals and boundaries](NON_GOALS_AND_BOUNDARIES.md) |

Build order, the full phase blueprint, and dated review logs explain how Raiker
reached its current design. They are historical records and do not override the
canonical documents at the top of this page.
