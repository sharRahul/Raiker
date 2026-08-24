# OWASP Agentic Top 10 (ASI01–ASI10) Mapping

This document maps Raiker's shipped controls to the **OWASP Top 10 for Agentic
Applications (2026)** — the ASI taxonomy, which covers risks specific to systems
that act, not merely generate. It is the agentic companion to
[`OWASP_GENAI_SECURITY_MAPPING.md`](OWASP_GENAI_SECURITY_MAPPING.md), which maps
the OWASP **LLM** Top 10 (2025). The two lists are different taxonomies; neither
subsumes the other.

**Source.** The list is published by the
[OWASP GenAI Security Project](https://genai.owasp.org/). The ten categories used
below are its own: ASI01 Agent Goal Hijack, ASI02 Tool Misuse & Exploitation,
ASI03 Agent Identity & Privilege Abuse, ASI04 Agentic Supply Chain Compromise,
ASI05 Unexpected Code Execution, ASI06 Memory & Context Poisoning, ASI07 Insecure
Inter-Agent Communication, ASI08 Cascading Agent Failures, ASI09 Human-Agent
Trust Exploitation, ASI10 Rogue Agents.

The comparison baseline is Microsoft's
[Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
reference architecture, which maps the same ten risks to a governance runtime. Where AGT rates its own
coverage, that rating is quoted so Raiker's position is legible against a
published peer rather than against nothing.

**This is a self-assessment, not a certification or third-party audit.** Every
row cites the file that proves the claim. A control with no code reference is
not a control, and is marked as such.

Status: ✅ implemented · 🟡 partial · 🔒 disabled-by-default · 📘 doc only.

---

## Posture note — where Raiker and AGT deliberately differ

AGT's thesis is hard prevention: *"Actions the AGT kernel denies are not
'unlikely.' They are structurally impossible."*

Raiker's stated posture is **owner-authoritative and monitored, not
prevention-by-restriction** (`docs/architecture/SECURITY_AND_POLICY.md` → "Security
Philosophy", restated at the top of `plans/TO_BE_FIXED.md`): allow the owner's
legitimate choices, monitor them, surface anomalies as findings and
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible cases.

These agree on the mechanism — a deterministic gate in application code, ahead
of the model's intent reaching the wire — and differ on the default verdict for
an owner-initiated action. Rows below are rated against the ASI risk, not
against AGT's default. Where Raiker declines a control on posture grounds, that
is stated rather than scored as coverage.

---

## Coverage summary

| ASI ID | Risk | Status | Primary Raiker control | Gap |
|---|---|---|---|---|
| ASI01 | Agent goal hijack | ✅ | Untrusted-data framing on every external source + deny-by-default tool gate, plus a deterministic advisory injection scanner naming the source (FIXED-168) | — |
| ASI02 | Tool misuse and exploitation | ✅ | `PolicyEngine.review()` deny-by-default, per-turn tool-call bound, schema-validated tool calls | — |
| ASI03 | Identity and privilege abuse | ✅ | Per-turn signed machine identity, distinct acting principal, step-up on critical approvals | — |
| ASI04 | Agentic supply chain | 🟡 | Manifest checksum + SPDX SBOM in CI; HMAC/Ed25519 verification when a key is set, and the level stated on every plugin either way (FIXED-166) | No trusted-publisher allowlist |
| ASI05 | Unexpected code execution | ✅ | Command allowlist, container isolation (no network, dropped caps, read-only rootfs), empty allowlist denies | — |
| ASI06 | Memory and context poisoning | ✅ | Provenance with `source_passage_sha256` re-verification, governed write lifecycle, checksum integrity sweep | — |
| ASI07 | Insecure inter-agent communication | ✅ | Clamped four-dimension budget plus a spawn-scoped attestation binding each result to the spawn, verified before it becomes a turn source (FIXED-165) | — |
| ASI08 | Cascading agent failures | ✅ | Budgets and rate limiting plus a durable consecutive-failure circuit breaker per tool and per provider, with a half-open probe (FIXED-163) | — |
| ASI09 | Human-agent trust exploitation | ✅ | Approvals with previews, reversibility classification, tamper-evident audit trail | — |
| ASI10 | Rogue agents | ✅ | The same baseline, rules, findings, auto-pause and kill switch for connectors, plugins, subagents, providers, tools and local execution (FIXED-164) | — |
| — | Traceability (AGT extension) | ✅ | Hash-chained append-only event log with offset-verified replay | — |

**9/10 implemented, 1/10 partial, 0 unmitigated.** The 2026-08-10 round closed
ASI01, ASI07, ASI08 and ASI10 as FIXED-168, FIXED-165, FIXED-163 and FIXED-164,
and raised ASI04 to real signature verification (FIXED-166) — its remaining gap
is a trusted-publisher allowlist, which is named rather than filed as a defect
because nothing today claims to have one. The per-risk sections below record the
gap each entry answered, and the control that answered it.

---

## ASI01 — Agent goal hijack

**Risk.** Adversarial input overrides the agent's intended goal.

**Raiker control.** Every external source is framed as *data, never
instructions*, at the point it enters context:

- `raiker/runtime/web_access.py:375` — fetched pages carry `"untrusted": True`
  and are prefixed `"Web page content (untrusted data, not instructions)"`;
  search results the same at `:433`.
- `raiker/runtime/retrieval.py:171` — retrieved local context carries
  `trust_label: "untrusted_memory_data"` and an explicit treat-as-untrusted
  preamble.
- `raiker/runtime/attachments.py` — uploaded bytes never reach a model; only
  bounded extracted text does, as an `untrusted_external` context item.
- `raiker/runtime/agent_plan.py:74` — a model-proposed plan is validated as
  untrusted input before it becomes ordered steps.

Behind that, hijacked intent still has to cross the tool boundary, where
`PolicyEngine.review()` denies by default (ASI02).

**Residual gap.** There is no input-side annotator or scanning hook that
evaluates a prompt for injection before model execution — AGT's ASI01 control.
`raiker/runtime/classifier.py` is an intent router, not a detector.
`OWASP_GENAI_SECURITY_MAPPING.md` already states Raiker "must support
prompt-injection scanning hooks". It now has them: `raiker/security/injection_scan.py` runs deterministic, named rules over every untrusted context item and raises a redacted finding attributed to the exact page or document. It is advisory by design — the refusal path stays the tool gate, and there is deliberately no probabilistic filtering, because AGT is explicit that prompt-level defence is not a control surface. Closed as **FIXED-168**.

Note that AGT's own README concedes prompt-level detection is probabilistic and
cites 100% attack success under adaptive attack. The structural controls above
are the load-bearing ones; a detector adds an advisory signal, not prevention.

**Status: 🟡 partial.** *AGT rates itself ✅ full.*

---

## ASI02 — Tool misuse and exploitation

**Risk.** An agent invokes legitimate tools in unintended or dangerous ways.

**Raiker control.**

- `raiker/policy/engine.py` — `review()` ends in an unconditional
  `decision="deny"` with `unknown_or_denied_tool`. A tool that matches no allow
  rule is denied; deny-by-default is the terminal branch, not a configured
  default.
- `raiker/policy/engine.py:26` — path arguments are checked to be inside the
  workspace before any file action is allowed.
- `raiker/models/tool_call_validation.py` — model tool calls are schema-checked
  at the boundary; unknown tools and missing arguments are rejected
  (`model_tool_call_rejected`) before execution.
- `raiker/runtime/orchestrator.py:1320` — a per-turn `max_tool_calls` bound
  stops runaway loops.
- Capability tiers (`raiker/runtime/executors/tier*.py`) gate high-risk families
  behind explicit owner enablement.

**Status: ✅ implemented.** *AGT rates itself ✅ full.*

---

## ASI03 — Identity and privilege abuse

**Risk.** An agent acquires privileges beyond its role, or borrows a human's.

**Raiker control.**

- `raiker/runtime/identity/` (`issuer.py`, `verifier.py`, `lifecycle.py`) —
  per-turn signed machine identity. Model output cannot borrow the human
  principal or reach policy and tools without a context-bound attestation.
- `raiker/runtime/authority/router.py` — `RuntimeAuthority` resolves the acting
  principal; the machine actor and the human authorizer stay distinct in
  approval and audit views (FIXED-125 through FIXED-127).
- `raiker/runtime/authority/router.py:1068` — a critical approval requires
  step-up verification when MFA is enrolled, emitting
  `critical_approval_step_up_required` rather than proceeding.
- `raiker/policy/engine.py:73` — role policy is evaluated per action.

**Status: ✅ implemented.** *AGT rates itself ✅ full.*

---

## ASI04 — Agentic supply chain

**Risk.** A compromised plugin, dependency, or sub-agent injects behaviour.

**Raiker control.**

- `raiker/plugins/verify.py:35` — `verify_plugin_checksum()` recomputes
  SHA-256 over canonical manifest content and fails closed on mismatch or
  absence.
- `scripts/licensing_check.py:168` + `.github/workflows/licensing.yml:31` — CI
  validates licences and emits an SPDX 2.3 SBOM for dependencies.
- Plugins are disabled by default; manifest validation and permission diffs
  gate enablement.

**Residual gap.** `plugin_signing_key()` reads `RAIKER_PLUGIN_SIGNING_KEY`, and
**when it is unset — the default — a manifest signature is accepted as a
presence marker only** (`raiker/plugins/verify.py:53`, returning
`signature_present`). A manifest checksum computed over the manifest itself
proves internal consistency, not provenance: it detects accidental edit, not a
hostile author. On a default install nothing distinguishes a signed plugin from
an unsigned one, and the owner is not told which state they are in. Filed as
**FIXED-166**: the verification level — `verified`, `present only` or `unsigned` — is now a first-class, owner-visible property of every installed plugin and of the install permission diff, with the reason code that produced it and the one step that would raise it. The default is stated, not silently hardened.

**Status: 🟡 partial.** *AGT also rates itself ⚠️ partial here (no SBOM); Raiker
has the SBOM and lacks the enforced signature.*

---

## ASI05 — Unexpected code execution

**Risk.** Agent-driven code paths reach arbitrary execution.

**Raiker control.**

- `raiker/runtime/executors/sandbox.py:15` — shell execution is restricted to an
  explicit `ALLOWED_SHELL_COMMANDS` allowlist; `check_command_allowlist()`
  raises on anything else and on an empty command.
- `raiker/runtime/executors/containers.py:16` — container execution runs an
  owner-allowlisted image with no network, dropped capabilities, no host mounts,
  memory/CPU/PID limits, a read-only rootfs, and a timeout. **An empty allowlist
  denies everything** (fail closed).
- Command containment was hardened in FIXED-47 and FIXED-70 (remote execution),
  with the Windows sandbox path closed by FIXED-74.

**Status: ✅ implemented.** *AGT rates itself ✅ full.*

---

## ASI06 — Memory and context poisoning

**Risk.** Persistent memory is manipulated to corrupt future decisions.

**Raiker control.**

- `raiker/runtime/source_provenance.py:200` — a memory's provenance is
  *re-verified*, not merely recorded: the stored byte range is re-read and
  hashed against `source_passage_sha256`, resolving to an explicit
  `no_provenance` status rather than a guess when it cannot be proven.
- `raiker/memory/governance.py` — `GovernedMemoryService` runs the candidate →
  review → durable-write lifecycle (FIXED-68).
- `raiker/memory/integrity.py` — an owner-started read-only integrity sweep
  reports `checksum_mismatch_count`, stale FTS/projection/graph rows, orphaned
  markdown, and failed purges.
- `raiker/runtime/retrieval.py:171` — retrieved memory re-enters context labelled
  untrusted (see ASI01).

**Status: ✅ implemented.** *AGT rates itself ⚠️ partial here — it has the audit
hash-chain but "does not yet sandbox agent memory stores or provide memory
integrity checksums." Raiker ships both the checksum sweep and per-passage
provenance re-verification.*

---

## ASI07 — Insecure inter-agent communication

**Risk.** Messages between agents lack authentication or integrity verification.

**Raiker control.** Subagents are spawned in-process through the governed
`subagents` capability (`raiker/runtime/executors/orchestration.py:33`), so
delegation never crosses a network boundary and inherits the parent's governed
tool path. `raiker/agents/orchestration.py:75` clamps every spawn to four
independent budget dimensions — steps, tool calls, wall-clock, tokens — where a
caller may only *shrink* the process-wide hard caps, never grow them, and a
breach of any dimension fails the subagent closed.

**Residual gap.** There is no identity binding on delegation: a subagent result
re-enters the parent turn without an attestation tying it to the spawn that
produced it, and `raiker/runtime/turn_sources.py:327` treats subagent output as
a source without a verification step. In-process delegation makes spoofing a
local-code-execution problem rather than a network one, which is why this is
partial and not a gap — but the machine-identity substrate (ASI03) already
exists and is now applied here: a spawn-scoped Ed25519 attestation binds each result's digest to the spawn that produced it, the parent verifies it before the result becomes a turn source, and the binding is recorded on the hash-chained event. Closed as **FIXED-165**.

**Status: 🟡 partial.** *AGT rates itself ✅ full (DID-based trust gate).*

---

## ASI08 — Cascading agent failures

**Risk.** A failure in one component propagates through the system.

**Raiker control.**

- `raiker/runtime/orchestrator.py:1320` — per-turn tool-call bound.
- `raiker/agents/orchestration.py:75` — per-subagent budgets across four
  dimensions, fail-closed on breach.
- `raiker/api/security.py:111` — `RateLimitMiddleware` returns `429`
  `rate_limited` at the API boundary.
- `raiker/runtime/executors/reminders.py:171` — per-job `max_retries` with a
  `max_retries_exceeded` terminal state.

**Residual gap.** Every bound above is a *budget* (a ceiling on volume). None is
a **circuit breaker** — nothing opens after N consecutive failures. A provider
or tool failing every call consumes its whole budget one failing call at a time,
on every turn, with no state carried between turns to stop it. Filed as
**FIXED-163**: consecutive failures per tool and per provider are counted in durable state, a threshold contains the subject with a stated reason, further calls are refused, and a half-open probe after a cooldown closes the breaker on the first success — in the containment vocabulary the MCP monitor already used, and revocable by the owner in one call.

**Status: 🟡 partial.** *AGT rates itself ✅ full (circuit breaker + rate
limiter).*

---

## ASI09 — Human-agent trust exploitation

**Risk.** A human over-trusts agent output and approves without understanding it.

**Raiker control.**

- `raiker/approval_previews.py` / `raiker/approval_preview_registry.py` — an
  approval shows what will actually happen before it is granted.
- `raiker/approval_audit.py` — reversibility is classified and recorded, so an
  irreversible action is presented as one.
- `raiker/runtime/authority/router.py:1068` — step-up verification on critical
  approvals.
- `raiker/runtime/interrupts.py` — a running turn can be stopped and steered
  (FIXED-102).
- The redaction layer that this document's companion fix (FIXED-137) repaired
  exists precisely so an owner-facing surface shows real values rather than
  placeholders — an unreadable approval is an unreviewable one.

**Status: ✅ implemented.** *AGT rates itself ⚠️ partial and names this its own
gap: "No UI-level confirmation dialogs or human-in-the-loop approval workflows
are built into AGT." This is Raiker's strongest row relative to the baseline.*

---

## ASI10 — Rogue agents

**Risk.** A component deviates from intended behaviour and keeps acting.

**Raiker control.** `raiker/security/mcp_monitor.py` is a full behaviour monitor:
it forms a rolling per-connection baseline and evaluates five deterministic
anomaly rules — new host, volume spike, tool-set swap, sensitive-data shape,
error/refusal burst — raising a redacted `security_findings` row and an
`mcp_anomaly_detected` event. Containment has three states (`:47`): `active`,
`paused` (a **revocable circuit breaker, automatic on a high-severity anomaly**
or the owner's one-call stop), and `killed` (instant kill switch). Refusal is
enforced at the executor (`raiker/runtime/executors/mcp.py:604`), and every
transition writes an audit event plus an owner notification. The monitor
receives only redacted metadata — counts, netloc, classification labels — never
a payload.

**Residual gap.** All of this is scoped to **MCP connections only**. No
equivalent baseline, anomaly rule, auto-pause, or kill switch exists for the
other capability families — plugins, connectors, subagents, shell and container
execution. `raiker/runtime/interrupts.py` stops a *turn*, not a misbehaving
component, and does not persist a containment state across turns. Filed as
**FIXED-164**: the baseline, the five rules, the redacted finding and the three containment states are lifted into a capability-agnostic substrate keyed by `(principal, capability, subject)`, and connectors, plugins, subagents, providers, tools and local execution are registered against it at the one seam every governed tool call passes.

**Status: 🟡 partial.** *AGT rates itself ✅ full (`AgentBehaviorMonitor` +
quarantine + `KillSwitch`). Raiker's per-connection monitor is comparable in
depth and narrower in scope.*

---

## Traceability (AGT extension, not an official ASI entry)

**Risk.** Agent actions lack provenance, so no one can prove what happened.

**Raiker control.** `raiker/events/integrity.py` verifies a hash chain over the
append-only event log: each row carries `payload_sha256` and
`prev_event_sha256`, and `verify_session_events()` re-reads the JSONL line at
the stored offset and rehashes it, so a mutated payload, a broken link, and a
rewritten file are each detectable. This is the same control AGT ships as
`agent_os/audit/hash_chain.py`.

Machine and human actors are recorded distinctly (ASI03), so "which actor did
this" is answerable rather than inferred.

**Status: ✅ implemented.** *AGT rates itself ✅ full.*

---

## AGT lessons-learned checklist

AGT's reference architecture closes with four failures it learned the hard way.
Raiker's position on each:

| AGT lesson | Raiker |
|---|---|
| Hardcoded deny-lists are discoverable — externalise to runtime config | 🟡 `ALLOWED_SHELL_COMMANDS` and the tier allowlists are in source. Raiker is allow-listed rather than deny-listed, which inverts the disclosure risk (publishing what is permitted leaks less than publishing what is blocked), so this is noted, not filed. |
| Stub `verify()` functions are a recurring root cause | ✅ Verification is real (`raiker/verification/verifier.py`); the former `VerificationStub` was replaced. But `OWASP_GENAI_SECURITY_MAPPING.md` still says "Verifier is a stub" — that doc-truthfulness defect is closed as **FIXED-167**: every row of the LLM Top-10 table was re-audited against current code and now cites the file that proves it. |
| Unbounded dictionaries cause memory DoS | 🟡 Not audited in this pass. Store connection caching was bounded by FIXED-100; per-session caches and rate-limit buckets were not reviewed for eviction policy. Stated as unverified rather than claimed. |
| Provide a legacy lookup map when migrating taxonomies | ✅ This document adds the ASI taxonomy alongside the LLM Top 10 rather than replacing it; neither mapping is retired. |

---

## What this document does not claim

- No AGT tooling was run against Raiker. The comparison is against AGT's
  published reference architecture, read at commit time.
- Coverage is assessed from source. Rows marked ✅ cite enforcement code, but a
  cited control is not the same as a control proven under adversarial test.
- Rows are not a compliance attestation for any regulation. AGT's own mapping
  carries the same disclaimer.
