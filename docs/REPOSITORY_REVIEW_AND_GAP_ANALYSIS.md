# Raiker Repository Review & Gap Analysis

Status: review snapshot · Date: 2026-06-19 · Branch: `claude/sweet-wozniak-9yz075`

This document is a critical, evidence-based review of the Raiker repository against its own
vision and against the reference platforms named in the review brief (Claude Code docs,
OpenClaw, Hermes-Agent, Ruflo, Graphify, Superpowers, memsearch, mem0, OWASP GenAI/LLM Top 10,
llama.cpp, LangChain/LangGraph).

It distinguishes four states, using the repository's own vocabulary
(`docs/IMPLEMENTATION_STATUS.md:9-19`) plus an explicit **stub** call-out:

- **implemented_verified** — real logic exists and is covered by tests.
- **partial / stub** — code exists but is a placeholder or pass-through, not the documented behaviour.
- **specified_not_implemented** — documented in detail, but no code exists.
- **phase_scheduled_disabled** — contracts/registries exist, runtime intentionally disabled.

> Method note: claims below were verified by reading source under `raiker/`, tests under
> `tests/`, and docs under `docs/`. Where a doc claims a capability the code does not support,
> it is called out explicitly. Reference links were live-fetched where reachable (see Appendix A).

---

## 1. Platform Alignment

**Does the repository clearly explain what Raiker is?** — **Yes, strongly.**
`README.md:5-17` defines Raiker as a *local-first, security-gated agent runtime* with
equal-status interfaces, not a chatbot. The "Why Raiker" framing (`README.md:21-37`) is
specific and native: every interface flows through one runtime, contracts, policy, event log,
storage, approval-preview, and checkpoint path. This is a coherent, non-generic thesis.

**Is the architecture aligned with building an AI platform?** — **Yes.** The nested-boundary
model (interface → event-logging → security/privacy → agent-core) in
`docs/03_ARCHITECTURE.md` / `docs/NESTED_BOUNDARIES_ARCHITECTURE.md`, and the code layout under
`raiker/` (gateway, runtime, policy, tools, events, storage, approvals, checkpoints, sessions,
tasks) match the documented design. The agent loop is a real deterministic state machine
(`raiker/runtime/orchestrator.py`, `raiker/runtime/state_machine.py`), and the tool broker is
the single execution path (`raiker/tools/broker.py`). This is genuine platform architecture,
not a wrapper script.

**Are capabilities described as Raiker-native?** — **Mostly yes.** Capabilities are framed as
Raiker contracts/events/policy, not vague "AI features." The main weakness is that the
*reference alignment* docs (`docs/REFERENCE_PLATFORM_COMPATIBILITY.md`) omit several named
references from the brief (Superpowers, mem0, memsearch) and the precise Claude Code doc pages.

**Verdict:** Platform identity and architecture are a clear strength. The risk is not vagueness
— it is **documentation running ahead of implementation** (Section 4).

---

## 2. Capability Coverage

Legend: ✅ implemented_verified · 🟡 partial/stub · 📘 specified_not_implemented (doc only) ·
🔒 phase_scheduled_disabled (deliberate).

| Capability | Doc coverage | Code state | Evidence |
|---|---|---|---|
| Agent runtime / loop | Strong | ✅ | `raiker/runtime/orchestrator.py`, `state_machine.py`; `tests/test_phase_1_integration.py` |
| Tool execution / broker | Strong | ✅ (read tools real; write/shell approval-gated) | `raiker/tools/broker.py`, `filesystem.py`; `tests/test_tool_broker.py` |
| CLI behaviour | Strong | ✅ | `apps/cli/main.py`, `raiker/cli/main.py`, `raiker/tui/app.py` |
| Interactive mode (REPL) | Strong | ✅ (basic) | `raiker/tui/app.py` |
| Commands (slash) | Strong (50+) | ✅ (inspection/planning surfaces) | `raiker/cli/commands.py` |
| Hooks | Strong | ✅ implemented (`builtin`+`command`) | `raiker/hooks/`; `tests/test_hooks.py`; `http`/`mcp_tool`/`prompt`/`agent` deferred |
| Plugins | Strong | 🔒 (manifest validation only, no exec) | `raiker/plugins/policy.py`, `manifest.py` |
| Channels | Strong | 🔒 (registry only, no transport) | `raiker/channels/registry.py`; `config/channel-connectors.json` |
| Checkpointing / rollback | Strong | 🟡 (write real; restore is plan-only) | `raiker/checkpoints/service.py` (`plan_restore` → `can_execute=False`) |
| Memory | Strong | 🔒 (candidates/governance only; no writes) | `raiker/memory/*`; `memory/readiness.py` (all flags `False`) |
| Context gathering | Thin | 🟡 **stub** | orchestrator records fixed `sources=["current_prompt"]` |
| Repository understanding | Strong (graph/codemap) | 🔒 (dry-run plan only) | `raiker/graph/planner.py` (`can_index=False`) |
| Code review workflow | **Absent** | ❌ missing | no review module; not in `raiker/` |
| Task planning / execution | Good | ✅ (tasks) / 🟡 (planner minimal) | `raiker/tasks/manager.py`; `raiker/runtime/planner.py` |
| Security controls | Strong | ✅ (path safety, policy, approvals) | `raiker/policy/engine.py`, `tools/filesystem.py` |
| OWASP GenAI/LLM coverage | Strong doc, partial code | 🟡 | `docs/OWASP_GENAI_SECURITY_MAPPING.md`; controls partial (Section 5) |
| Local model support | Documented | ✅ llama.cpp native default + deterministic test provider | `raiker/models/providers/openai_compatible.py`, `raiker/models/router.py` |
| llama.cpp / local inference | Documented | ✅ implemented (async httpx OpenAI-compatible path) | `raiker/models/providers/openai_compatible.py`; async runtime tests |
| Agent-framework integration (LangChain/LangGraph) | Light | 📘 concept-only | `docs/REFERENCE_PLATFORM_COMPATIBILITY.md:155-165` |
| Extensibility model | Scattered | 📘 (see new `docs/EXTENSIBILITY_MODEL.md`) | plugins+hooks+skills+channels not unified |
| Self-improvement model | Scattered | 📘 (see new `docs/SELF_IMPROVEMENT_MODEL.md`) | folded into `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` |

**Net:** Phase 1 (runtime core) and most of Phase 2 (workspace/inspection) are genuinely built
and tested. Everything beyond local read/edit/approve is **documented or readiness-tracked, not
executing** — which the repo states honestly for the *deliberately* disabled set, but **not**
for hooks, local providers, the verifier, or context gathering.

---

## 3. Documentation Completeness

**Strengths**
- 77 markdown docs with a builder reading order (`README.md:283-325`) and a status ledger
  (`docs/IMPLEMENTATION_STATUS.md`). Few projects document failure handling, events, and tests
  per feature this thoroughly.
- Security is documented at three layers: model (`SECURITY_AND_POLICY.md`), threats
  (`THREAT_MODEL.md`), OWASP mapping (`OWASP_GENAI_SECURITY_MAPPING.md`).
- Disabled-runtime invariants are stated repeatedly and enforced by
  `scripts/validate_phase_status.py`.

**Gaps / weaknesses**
1. **Duplicated content.** `README.md:50-51` repeats the Phase 3 status row almost verbatim
   (one with backticks, one bold). The trailing per-slice dump (`README.md:427-465`) inlines
   nine Slice summaries that already live in their own specs — noise in the entry-point doc.
2. **Reference omissions.** `REFERENCE_PLATFORM_COMPATIBILITY.md` does not name **Superpowers**,
   **mem0**, or **memsearch**, and maps Claude Code at a high level rather than per doc page
   (hooks/tools/checkpointing/channels/commands/cli/interactive). Addressed in this pass.
3. **Shallow vs reference depth.** `HOOKS_SPEC.md` is good but predates the Claude Code hooks
   reference (31 events; 5 handler types `command|http|mcp_tool|prompt|agent`; three-level
   `matcher`→`hooks[]` config; `if` conditions). `CHANNELS_SPEC.md` predates the
   channels-reference (MCP `claude/channel` capability, `notifications/claude/channel`,
   sender-gating, permission relay with five-letter request IDs).
4. **Status drift.** Several docs assert capabilities the code does not back (Section 4). The
   ledger's integrity depends on closing these.
5. **No top-level docs index** beyond the README map; with 77 files a `docs/README.md` index
   would help (one exists only under `docs/completed/`).

**Per-capability "enough to implement/test/maintain?"** — Yes for Phase 1/2 (contracts, events,
tests are concrete). Partial for hooks/providers/code-review: the *interfaces* are described but
there is no module skeleton, adapter interface, or test fixture to build against.

**Roadmap/architecture/status consistency** — Internally consistent for Phase 1–3 scope. The
one structural inconsistency: Phase 2 is marked `implemented_verified` and lists "Local model
providers" as Phase 2, while only the mock provider is wired and the router rejects all others.

---

## 4. Implementation Readiness

**Does the structure support the vision?** — Yes for the runtime core. The package boundaries
map to the architecture and leave clear seams for future modules.

**Documented-but-not-coded (claims without support):**

| Claim in docs | Reality in code | Evidence |
|---|---|---|
| Verification/reflection step in the loop | Resolved (Phase 1/2): deterministic safety/result-shape verifier integrated into the loop | `raiker/verification/`, `raiker/runtime/orchestrator.py`, `tests/test_phase_1_2_verifier.py` |
| Context gathering / repository understanding feeding the model | Resolved (Phase 1/2-safe bounded local metadata only): bounded `ContextBundle` with provenance/redaction/budgeting; fixed single source removed | `raiker/context/`, `tests/test_phase_1_2_context_gatherer.py` |
| Coding-agent / code-review workflow | Still absent — separate follow-up, not required by Phase 1/2 acceptance | absent |

**Code-without-docs (functionality not documented):** minimal — the repo is doc-heavy. The
`raiker/readiness/` and `rollback_*` planning surfaces are documented in the Slice specs. No
significant undocumented runtime behaviour was found.

**Missing modules/interfaces to realize the vision (recommended, not built here):**
`raiker/hooks/` (dispatcher + handler-type adapters), a `ModelProvider` adapter package with at
least one real local client (`raiker/models/providers/`), a real context-gatherer
(`raiker/context/`), a verification implementation, and a code-review workflow module.

---

## 5. Security & Safety Review (OWASP LLM Top 10 — 2025)

The OWASP mapping doc is strong on intent; the gap is **documented control vs implemented
control**. Per-risk status:

| OWASP LLM (2025) | Documented? | Implemented? | Gap / recommended control |
|---|---|---|---|
| LLM01 Prompt Injection | Yes | 🟡 partial | Trust labels are documented; code does not yet tag context provenance. Add source-trust tagging on every context item; never let file/tool/channel content carry instruction authority. |
| LLM02 Sensitive Information Disclosure | Yes | 🟡 partial | `redact_secret_like_text()` exists for approval previews; not applied uniformly to event logs/model egress. Add a single redaction pass on all persisted text + egress classifier. |
| LLM03 Supply Chain | Yes | 🔒 | Plugin manifest validation real, but no signature/checksum verification. Add manifest signing + dependency policy (currently zero deps — keep an allowlist gate). |
| LLM04 Data/Model Poisoning | Yes | 🔒 | Memory writes disabled; governance documented. When enabled, enforce provenance + contradiction checks already specified. |
| LLM05 Improper Output Handling | Yes | ✅ improved | Model tool calls are now schema-validated at the boundary (`raiker/models/tool_call_validation.py`): unknown tools/missing args are rejected (`model_tool_call_rejected`) before becoming a `ToolAction`. |
| LLM06 Excessive Agency | Yes | ✅ improved | Tool broker + approvals + a per-turn **max-tool-calls budget** in the orchestrator (`PromptOptions.max_tool_calls`). Subagent depth N/A (subagents disabled). Time/token budgets still to add. |
| LLM07 System Prompt Leakage | Yes | 📘 | Documented; no system-prompt separation in code yet (mock provider). Implement with first real provider. |
| LLM08 Vector/Embedding Weaknesses | Yes | 🔒 | Vector writes disabled. Apply sensitivity filters + provenance when enabled. |
| LLM09 Misinformation | Yes | 🟡 | Verifier is a stub. Implement verification/citation gating to make this real. |
| LLM10 Unbounded Consumption | Yes | 🟡 partial | Per-turn tool-call budget now enforced in the orchestrator; token/time/rate budgets still to add. |

**Strongest implemented safeguards today:** workspace path-safety (symlink/traversal rejection,
`raiker/tools/filesystem.py`), policy-gated tool execution with approvals, append-only event
log, and "disabled by default" for every high-risk capability.

**Highest-leverage additions:** (1) context provenance tagging (LLM01), (2) uniform redaction on
persistence/egress (LLM02), (3) tool-call schema validation (LLM05), (4) per-turn budgets
(LLM06/LLM10). These are small, local changes to the orchestrator/broker and would convert four
"documented-only" controls into real ones.

---

## 6. Gap Analysis

| Capability / area | Current status | Missing / weak | Risk / impact | Recommended fix | Priority |
|---|---|---|---|---|---|
| Hooks | ✅ implemented (core) | `http`/`mcp_tool`/`prompt`/`agent` handlers deferred | — | Done: `raiker/hooks/` dispatcher + `builtin`/`command` handlers, scoped config, decision authority, broker/gateway wiring, tests (`tests/test_hooks.py`) | Resolved |
| Local model providers / llama.cpp | ✅ implemented | — | — | Done: `raiker/models/providers/openai_compatible.py` is the async OpenAI-compatible backend for llama.cpp and similar profiles using httpx; deterministic provider remains test-only; model-driven tool-call loop + validation added | Resolved |
| Verifier | 🟡 stub | Pass-through; no checks | LLM09 misinformation; "verify" phase is hollow | Implement minimal verification (test-run / diff sanity) with events | High |
| Context gathering | 🟡 stub | Fixed single source | No real repository understanding feeding the model | Implement a context-gatherer using existing safe tools (grep/glob/read) + budget | High |
| Code review workflow | ❌ missing | No module despite "coding platform" framing | Headline use case absent | Specify + build a review workflow (diff in → findings out) reusing tool broker | Medium |
| Reference alignment docs | 🟡 incomplete | Superpowers/mem0/memsearch/Claude-Code-per-page absent | Brief explicitly requires these | Extend `REFERENCE_PLATFORM_COMPATIBILITY.md` (done) | Medium |
| Self-improvement model | 📘 scattered | Not a first-class doc | Hard to implement/test as a unit | New `docs/SELF_IMPROVEMENT_MODEL.md` (done) | Medium |
| Extensibility model | 📘 scattered | Plugins/hooks/skills/channels not unified | Contributors lack one mental model | New `docs/EXTENSIBILITY_MODEL.md` (done) | Medium |
| OWASP controls | 🟡 doc>code | 4 controls documented-only | LLM01/05/06/10 unenforced | Implement provenance tags, redaction pass, tool-call schema, per-turn budgets | High |
| README hygiene | 🟡 | Duplicated Phase-3 row; slice dump | Entry-point noise | De-dupe + link out (done) | Low |
| Status ledger accuracy | 🟡 | Over-claims (above) | Trust in `implemented_verified` | Add evidence-backed clarifying notes (done) | High |
| Plugin/channel signing | 🔒 | No signature/checksum verification | LLM03 supply chain | Add signing + permission-diff enforcement when enabled | Medium |

---

## 7. Updates Made In This Pass

Documentation-only (no runtime code changed; no disabled capability enabled):

- **New** `docs/REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md` (this file).
- **New** `docs/SELF_IMPROVEMENT_MODEL.md` — first-class self-improvement/skill-learning spec.
- **New** `docs/EXTENSIBILITY_MODEL.md` — unified plugins+hooks+skills+channels+tools surface.
- **Updated** `docs/REFERENCE_PLATFORM_COMPATIBILITY.md` — added Superpowers, mem0, memsearch,
  and per-page Claude Code mappings; deepened LangChain/LangGraph.
- **Updated** `docs/HOOKS_SPEC.md` — added a **Code Status** banner (specified_not_implemented)
  and Claude Code hooks-reference alignment notes.
- **Updated** `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` — **Code Status** banner clarifying
  mock-only wiring; deeper llama.cpp specifics.
- **Updated** `docs/OWASP_GENAI_SECURITY_MAPPING.md` — explicit LLM Top-10 (2025) table with a
  documented-vs-implemented status column and concrete recommended controls.
- **Updated** `docs/IMPLEMENTATION_STATUS.md` and `README.md` — additive, evidence-backed status
  clarifications (hooks, providers, verifier, context, code-review); README de-dupe and doc-map
  additions. (Validator markers preserved; `scripts/validate_phase_status.py` still passes.)

---

## 8. Final Report

**What is already strong**
- A clear, native platform thesis and a real, tested Phase 1 runtime core.
- Security-first design: single tool execution path, policy gating, approvals, path safety,
  append-only audit, and disabled-by-default for risky capabilities.
- Unusually disciplined documentation and an enforced status ledger.

**What is missing**
- Hooks code, real model providers (local inference), a real verifier, real context gathering,
  and a code-review workflow. Four OWASP controls are documented but not enforced.

**What is misaligned**
- Phase 2 `implemented_verified` while local providers are unwired; hooks specced with no code;
  reference docs omit named references from the brief. (Addressed by ledger clarifications and
  reference-doc updates in this pass.)

**What was updated** — see Section 7 (documentation only).

**What still needs implementation (engineering backlog, in priority order)**
1. ~~`raiker/hooks/` dispatcher + handler adapters + decision-authority tests.~~ Done — see
   `raiker/hooks/` and `docs/HOOKS_SPEC.md`.
2. ~~One real `ModelProvider` adapter behind the existing contract.~~ Done — the llama.cpp
   server is the native default backend (`raiker/models/providers/llama_cpp_server.py`), with a
   model-driven tool-call loop and tool-call validation (OWASP LLM05).
3. Real context-gatherer (`raiker/context/`) using existing safe tools + budget (still a stub).
4. Real verifier (test-run/diff sanity) wired into the loop (still a stub).
5. OWASP hardening: provenance tags, uniform redaction, per-turn budgets (tool-call schema
   validation now done; per-turn tool-call budget now enforced).
6. Code-review workflow module.

**Recommended next steps**
- Treat this report's Section 6 as the backlog; convert each row into a phase task with tests.
- Before adding new capabilities, close the doc/code gaps so `implemented_verified` stays
  trustworthy.
- Keep the disabled-runtime invariants; wire real providers behind the existing policy gates.

**Risks that could block Raiker from being a complete native agent/coding platform**
- **Trust erosion** if the ledger keeps marking unbuilt features verified (highest risk).
- **No real model path** — until a provider beyond mock is wired, the agent cannot actually
  reason; everything else is scaffolding.
- **Hollow verification/context** — without real context gathering and verification, the
  "gather → act → verify" loop is structurally present but functionally thin.
- **Security controls that exist only on paper** (LLM01/05/06/10) become real liabilities the
  moment a real model and tools are wired.

---

## Appendix A — References consulted

Live-fetched during this review: Claude Code `how-claude-code-works`, `tools-reference`,
`hooks`, `plugins-reference`, `channels-reference`, `checkpointing`, `skills`/commands; `mem0`
(github). Knowledge-based (not fetched this pass): OpenClaw, Hermes-Agent, Ruflo, Graphify,
Superpowers, memsearch (zilliztech), llama.cpp, LangChain/LangGraph, OWASP GenAI/LLM Top 10
portals. Where a reference was knowledge-based, mappings describe the well-known public design
of that project and should be re-verified against its current README before implementation.
