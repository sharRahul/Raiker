# Raiker documentation

This is the entry point for Raiker's documentation. It lists **every**
maintained document in this directory and says which question each one answers,
so nothing here is reachable only by knowing its filename.

Where two documents could answer the same question, one is marked **canonical**
and the other links to it. Where a document records history rather than current
behaviour, it is under [Historical record](#historical-record) and is not
maintained against the code.

## Canonical documents

Read these first, and prefer them where anything else disagrees.

| Question | Canonical document |
|---|---|
| How do I use Raiker? | [User guide](guide/README.md) |
| What are the components, and how does a governed action flow? | [Architecture](ARCHITECTURE.md) |
| What is implemented **right now**? | [Implementation status](IMPLEMENTATION_STATUS.md) |
| What are the trust boundaries and fail-closed controls? | [Security architecture](SECURITY_ARCHITECTURE.md) |
| What is Raiker's security philosophy, and what does enabling a capability mean? | [Security and policy](SECURITY_AND_POLICY.md) |
| How does Raiker compare with Claude Cowork, Claude Code, ChatGPT, Codex, OpenClaw, DeepSeek Harness and Hermes Agent? | [Reference platform compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md) |
| What does the local web API expose, and in what shape? | [API and contracts](API_AND_CONTRACT_SCHEMAS.md) |
| What can this build **not** do? | [Known limits](KNOWN_LIMITS.md) |
| What is still broken? | [To be fixed](plans/TO_BE_FIXED.md) |
| What has been fixed, and how? | [Fixed items](plans/FIXED_ITEMS.md) |

**The comparison matrix lives in exactly one place.** Other documents may cite a
single reference behaviour in passing; none of them should carry a matrix. Link
to [`REFERENCE_PLATFORM_COMPATIBILITY.md`](REFERENCE_PLATFORM_COMPATIBILITY.md)
instead.

## Start here

- [User guide](guide/README.md) — install, connect a model, permissions, Chat,
  Build, tasks, extensions, and troubleshooting by reason code. The same
  sections are served inside the product under Utilities → **Guide**.
- [Architecture](ARCHITECTURE.md) — components and the governed action flow.
- [Security architecture](SECURITY_ARCHITECTURE.md) — trust boundaries and
  fail-closed controls.
- [User-centric zero-trust policy](USER_CENTRIC_ZERO_TRUST_POLICY.md) — the
  owner policy that keeps safe work frictionless without weakening control.
- [Non-goals and boundaries](NON_GOALS_AND_BOUNDARIES.md) — what Raiker is
  deliberately not.

## The product surfaces

| Surface | Document |
|---|---|
| Raiker Build — the coding agent | [Build workspace](BUILD_WORKSPACE_SPEC.md) |
| The protocol a Build turn runs under | [Build process](RAIKER_BUILD_PROCESS.md) |
| The terminal client | [Commands and interactive mode](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md) |
| What every screen is for | [Web UI control deck plan](WEB_UI_CONTROL_DECK_PLAN.md) |
| How anything is drawn | [Visual design](VISUAL_DESIGN_SPEC.md) |
| Installation, background host, `raiker-app` lifecycle | [Desktop distribution](DESKTOP_DISTRIBUTION_DESIGN.md) |

## Governance and control

| Topic | Document |
|---|---|
| Per-capability Ask / Deny / Allow / Auto | [Decision modes](DECISION_MODES_SPEC.md) |
| How a proposed action is validated, classified and routed | [Tools and permissions](TOOLS_AND_PERMISSIONS_SPEC.md) |
| The tools a model may call, and the terminal command surface | [Tool and plugin catalog](RAIKER_TOOL_AND_PLUGIN_CATALOG.md) |
| How a capability gate becomes flippable, and each capability's honest status | [Runtime executors and capability activation](RUNTIME_EXECUTORS_SPEC.md) |
| How a turn is orchestrated | [Runtime orchestration](RUNTIME_ORCHESTRATION_SPEC.md) |
| The turn state machine | [Runtime state machine](RUNTIME_STATE_MACHINE.md) |
| The control boundaries every implementation must preserve | [Nested boundaries architecture](NESTED_BOUNDARIES_ARCHITECTURE.md) |
| What is emitted to the audit log | [Event catalog](EVENT_CATALOG.md) |
| Contract shapes and identifiers | [Contracts](CONTRACTS.md) |

## Memory, context and knowledge

| Topic | Document |
|---|---|
| What Raiker remembers, at what scope, and how it is governed | [Memory and context strategy](MEMORY_AND_CONTEXT_STRATEGY.md) |
| The rules a durable memory write must satisfy | [Memory governance](MEMORY_GOVERNANCE_RULES.md) |
| High-fidelity observation capture and gist compression | [Eidetic memory and learning](EIDETIC_MEMORY_AND_LEARNING_SPEC.md) |
| The graph and the repository code map | [Graph memory and codemap](GRAPH_MEMORY_AND_CODEMAP_SPEC.md) |
| Where everything is stored and how it is searched | [Storage, database and search](STORAGE_DATABASE_AND_SEARCH_SPEC.md) |
| Checkpoints, rewind, resume and fork | [Checkpointing and rewind](CHECKPOINTING_AND_REWIND_SPEC.md) |
| The archive-first hybrid memory contract | [Hybrid memory implementation plan](HYBRID_MEMORY_IMPLEMENTATION_PLAN.md) |
| What recall can actually do today | [Memory reliability plan](plans/MEMORY_RELIABILITY_PLAN.md) |

## Models and execution

| Topic | Document |
|---|---|
| Providers, local inference, readiness and acquisition | [Models and local inference](MODEL_RUNTIME_AND_LOCAL_INFERENCE.md) |
| The interface a provider adapter implements | [Model provider contract](MODEL_PROVIDER_CONTRACT.md) |
| Local, native-sandbox, container, SSH and cloud execution | [Execution environments](EXECUTION_ENVIRONMENTS_SPEC.md) |
| Subagents and coordinated teams | [Multi-agent and subagent strategy](MULTI_AGENT_AND_SUBAGENT_STRATEGY.md) |

## Extensibility

| Topic | Document |
|---|---|
| One mental model over tools, hooks, skills, plugins and channels | [Extensibility model](EXTENSIBILITY_MODEL.md) |
| Hook events, matchers, handlers and decision authority | [Hooks](HOOKS_SPEC.md) |
| What a plugin may contribute, and what it may never do | [Plugin system](PLUGIN_SYSTEM_SPEC.md) |
| The strict plugin manifest schema | [Plugin manifest schema](PLUGIN_MANIFEST_SCHEMA.md) |
| External messaging surfaces as a governed, untrusted input boundary | [Channels](CHANNELS_SPEC.md) |
| What Raiker may learn about itself, and the review that gates it | [Self-improvement model](SELF_IMPROVEMENT_MODEL.md) |

## Security

| Topic | Document |
|---|---|
| Assets, trust boundaries, threats and mitigations | [Threat model](THREAT_MODEL.md) |
| Per-capability threat models — one for every capability with a real executor | [Threat models index](threat-models/README.md) |
| OWASP LLM Top 10 (2025) against enforced controls | [OWASP GenAI mapping](OWASP_GENAI_SECURITY_MAPPING.md) |
| OWASP Agentic Top 10 (ASI01–ASI10, 2026), each row citing code | [OWASP Agentic mapping](OWASP_AGENTIC_TOP10_MAPPING.md) |
| Licence policy and third-party obligations | [Licensing policy](licensing/LICENSING_POLICY.md) |

## Verification and status

| Topic | Document |
|---|---|
| What CI runs, and what to run locally | [Verification plan](VERIFICATION_PLAN.md) |
| The checks to run before committing | [Local validation](LOCAL_VALIDATION_GATE.md) |
| A concise area-by-area coverage view | [Feature coverage](FEATURE_COVERAGE_MATRIX.md) |
| Deferred work and open gaps | [Gaps and deferred work](GAP_AND_TODO_ANALYSIS.md) |
| The boundaries Raiker chose, and where it is behind | [Known limits](KNOWN_LIMITS.md) |
| Acceptance tests grouped by phase | [Acceptance tests by phase](ACCEPTANCE_TESTS_BY_PHASE.md) |
| The repeatable browser procedure — every route, tab and control, in two tiers | [Live manual test plan](plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md) |
| What each dated round actually found | [Live test rounds](plans/LIVE_TEST_ROUNDS.md) |
| Exercising the web app against a real model backend | [Web app live test](WEB_APP_LIVE_TEST.md) |
| Recorded evidence, and what it does and does not prove | [Screenshot evidence](plans/screenshots/README.md) |

## Working on Raiker

| Topic | Document |
|---|---|
| The standing brief — goal, security posture, non-negotiable runtime rules | [Handoff](HANDOFF.md) (its dated sections are a historical record, not current status) |
| Proposed additions, with tiers and reasoning | [To be added](plans/TO_BE_ADDED.md) |
| Open Build and Chat gaps | [Build and Chat gap analysis](plans/GAP_BUILD_CHAT.md) |
| Recording an architecture decision | [ADR template](ADR_TEMPLATE.md) |
| Implementing in small, reliable steps | [Local LLM builder guide](LOCAL_LLM_BUILDER_GUIDE.md) |
| Mapping a borrowed concept into a Raiker requirement | [Reference requirements matrix](REFERENCE_REQUIREMENTS_MATRIX.md) |
| Plans and designs for in-flight work | [`superpowers/plans/`](superpowers/plans/), [`superpowers/specs/`](superpowers/specs/) |

## Historical record

These are kept because they explain how Raiker got here. **They are not
maintained against the code**, and where they disagree with a canonical document
above, the canonical document is right.

| Document | What it is |
|---|---|
| [Build order](BUILD_ORDER.md) | The dependency-safe implementation sequence the phases were built in |
| [Full phase implementation blueprint](FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md) | The original per-phase behaviour, storage, security and test specification |
| [Reference review log](REFERENCE_REVIEW_LOG.md) | Every dated reference review since 2026-08-16, and the concept-to-specification maps. Split out of [`REFERENCE_PLATFORM_COMPATIBILITY.md`](REFERENCE_PLATFORM_COMPATIBILITY.md) on 2026-08-23 so the canonical comparison describes the product rather than the passes that got there |
| [Apache 2.0 relicensing audit](licensing/APACHE_2_RELICENSING_AUDIT.md) | The audit behind the current licence |

