# User-Centric Zero Trust Security Policy

Status: **adopted** (owner policy, 2026-07-19). This document is the canonical,
normative statement of the owner's security policy for Raiker. Implementation
work translates the numbered requirements below into code; requirements whose
mechanism is not yet built are marked **Planned** and trace to
[`docs/plans/2026-07-19-execution-breadth-and-zero-trust-plan.md`](plans/2026-07-19-execution-breadth-and-zero-trust-plan.md).
Nothing in this document upgrades an implementation claim: the ledger
([`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)) remains the source of
truth for what is built, and capabilities without a real executor remain
fail-closed regardless of any requirement here.

---

## 1. The policy (owner-authored, verbatim)

> My security policy is to establishes a User-Centric, Zero Trust security
> model. The objective of this framework is not to restrict user access, but to
> implement a frictionless architecture that continuously and invisibly
> verifies identity and device posture. By embedding security seamlessly into
> organizational workflows, this policy empowers users to operate productively
> and securely without arbitrary administrative barriers.
>
> I believe that robust protection and user productivity are not mutually
> exclusive. This policy should enforce Zero Trust principles—never trust,
> always verify—through a user-centric lens. Security controls shall be
> engineered to run in the background, minimizing impact on user workflows.
> Security is defined here as an enabler of safe operations, not a mechanism
> for restriction.
>
> The security is to govern infrastructure protection using a User-Centric,
> Zero Trust framework. This strategy moves away from legacy perimeter
> restrictions, focusing instead on a frictionless system that secures data at
> the point of interaction, allowing users to execute their duties securely and
> without disruption.

## 2. Normative interpretation for Raiker

- **"Never trust, always verify"** means every action — regardless of which
  model proposed it, which interface submitted it, or which plugin or connector
  carries it — passes the same verification chain. There are no privileged
  interfaces and no bypass lanes.
- **"Frictionless"** means *fewer, better-scoped, asynchronous* human
  decisions: deterministic risk-tiering, scoped standing grants with expiry,
  and non-blocking notification-based approvals. It never means silent
  execution of high-risk actions or weakening of verification.
- **"Invisible"** means verification runs in the background and surfaces only
  on deviation. It never means the owner is uninformed of decisions that are
  theirs to make.
- **"User-centric"** means every trust decision belongs to the device owner:
  inspectable, reversible, and requiring no external administrator.
- **"Security as an enabler, not a mechanism for restriction"** means the
  system's answer to risk is *more verification, not less capability*: when an
  action can be made safe to run — through verification, scoping, audit, and
  reversibility — the system runs it, and escalation prefers step-up
  verification over lock-out (ZT-6). Blocking is reserved for what cannot yet
  be verified: no-executor domains and hard-denies stay fail-closed as the
  floor for the unverifiable, never as a ceiling on the user.
- **Precedence rule (owner decision, 2026-07-19):** where frictionless goals
  meet a critical-risk action or a fail-closed invariant, verification and
  visibility win. A critical action's resting state is deny; only a notified
  human's manual approval can change its outcome.

## 3. Requirements

Each requirement has a stable ID for traceability. Code, tests, and plan slices
reference these IDs. "Existing" cites the mechanism already in the codebase;
"Planned" cites the implementing plan slice.

| ID | Requirement (normative) | Mechanism | Status |
|---|---|---|---|
| ZT-1 | Every AI-proposed or human action MUST pass capability gate → policy review → risk classification → decision mode → audit event. No model, interface, plugin, or connector may bypass this chain. | `RuntimeAuthority`/`ActionRouter` (`raiker/runtime/authority/router.py`), `ToolBroker` + `PolicyEngine` | Existing |
| ZT-2 | Every governed action MUST carry a resolved acting principal; unknown or inactive principals are denied. | Acting-principal resolution; `PolicyEngine` role checks | Existing |
| ZT-3 | Identity and device posture (session validity, auth strength, MFA freshness, interface) MUST be captured on every governed action and re-verified between a recorded decision and its execution. | Posture snapshot (`raiker/runtime/authority/posture.py`; `RuntimeAuthority._capture_action_posture`) | Existing — F1 (per-action capture + re-verify via A4) |
| ZT-4 | Background verification (event hash-chain integrity, session validity, gate/decision-mode drift, egress-allowlist drift) MUST run continuously without user interaction and surface only deviations. | Scheduled integrity sweep | Planned — F2 |
| ZT-5 | Unprompted execution MUST be limited to deterministic low-risk decisions (`auto` mode) or scoped standing grants. Grants MUST be user-owned, scope-bound, expiry-bound, revocable, listed in Security Settings, and only ever narrow from a human-made decision. | Decision modes (`raiker/runtime/authority/decision_modes.py`); standing-grant engine (`raiker/runtime/authority/grants.py`) | Existing — modes + F3 (grants) |
| ZT-6 | When posture degrades or an action exceeds a grant's risk ceiling, the system MUST escalate to fresh verification (step-up TOTP/re-auth) rather than silently allowing or terminally blocking. | Step-up verification | Planned — F4 |
| ZT-7 | Critical-risk actions MUST notify the owner and resolve only by a live human's manual approve/reject with step-up verification. Their resting state is deny: silence, TTL expiry, session revocation, delegation, or any non-human resolution attempt resolves to deny. No decision mode, standing grant, scheduled routine, or subagent may resolve or pre-authorize a critical action. | Critical floor + production classification table (`raiker/runtime/authority/critical.py`); notify/decide lifecycle | Existing — floor + F6 (production classification); Planned — F7 (notify/decide lifecycle) |
| ZT-8 | Capabilities without a real executor MUST remain fail-closed and non-flippable; empty allowlists MUST mean no egress; missing credentials or vault key MUST mean the capability is unavailable — never a silent fallback. | Executor registry gating; `enforce_model_egress`; vault fail-closed | Existing |
| ZT-9 | Data MUST be secured at the point of interaction: approval prompts and audit events carry redacted, metadata-only previews; credentials never enter profiles, logs, or events; secret/credential-like durable memory content is denied before any record is created. | Broker redaction; `classify_memory_sensitivity` hard-deny | Existing |
| ZT-10 | Every governed decision and execution MUST be recorded as an append-only, hash-chained audit event, reconstructable per session from the log alone. | JSONL + SQLite event layer; `raiker/events/integrity.py` | Existing |
| ZT-11 | All trust decisions (gates, modes, grants, allowlists, runtime modes) belong to the device owner or their designated `runtime_gate_manager`, are reversible, and require no external administrator. AI principals can never make them. | Owner bootstrap; human-only authority actions | Existing |
| ZT-12 | Interfaces are zero-authority clients: every surface (terminal, web dashboard, and any future TUI/desktop/IDE surface) MUST route through the same governed gateway and MUST NOT add authority of its own. | `AgentGateway`; loopback-only API | Existing; applies to Workstream D surfaces |

## ZT-4 implementation update (2026-07-21)

F2 is implemented by `raiker/security/integrity_sweep.py` through the existing
scheduled-routines executor. It is silent when its event-chain, session,
owner-control baseline, and egress-allowlist checks are green, and produces an
owner-scoped metadata-only dashboard notification only on a deviation.

## 4. Translation discipline

- New tests that enforce a requirement SHOULD reference its ID (e.g.
  `ZT-7`) in the test name or docstring so coverage is traceable.
- A plan slice that lands a **Planned** mechanism updates this table's Status
  column in the same change, subject to the repo's validation gate — this
  document must never claim a mechanism before the ledger does.
- Changes to Section 1 (the policy text) or Section 2 (interpretation,
  including the precedence rule) are owner-only decisions.
- Recording an approval decision is metadata-only today; executing an approved
  action is governed separately (Workstream A) and re-verifies at execution
  time per ZT-3. Deferred and no-executor capabilities stay disabled/deferred
  and fail closed per ZT-8.
