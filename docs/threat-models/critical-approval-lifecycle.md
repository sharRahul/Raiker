# Threat Model — Critical Approval Lifecycle (Workstream F: F7, ZT-7)

> Status marker: production behavior in `raiker/runtime/authority/router.py`
> (`RuntimeAuthority.route_action` / `resolve_critical_approval`), consuming the
> F6 classification table (`raiker/runtime/authority/critical.py`). Covers F7 —
> the critical action's `created → notified → manual human decision → deny |
> execute` lifecycle, whose **resting state is deny**.

## What this is

A *critical* action (per the F6 table, or an explicitly `CRITICAL`-risk action)
is the top of the risk ladder. Before F7 the router silently flat-denied
AI-proposed critical actions and told no one. F7 replaces that with an explicit,
always-visible human-decision lifecycle:

1. **Park + notify (`route_action`).** When `route_action` classifies an action
   as critical and no valid human confirmation accompanies it, it does not
   execute. It records a `tool_actions` row + a `critical`-flagged approval
   (immutable `action_payload_sha256` + 24 h TTL, reusing the A1 intent
   snapshot), notifies the owner asynchronously (D2:
   `notify_critical_approval_pending` → dashboard notification center + optional
   OS hook), and emits `critical_approval_created` then `critical_approval_notified`
   (each with an F1 posture snapshot). The caller gets
   `needs_human_confirmation` + the `approval_id`. Nothing runs.
2. **Manual human decision (`resolve_critical_approval`).** The *only* transition
   that can move a critical action off deny. It enforces, in order: the approval
   exists, is `critical`, and is `pending`; the resolver is a **live human**
   (a non-human attempt resolves it to `denied`); the TTL has not lapsed; the
   immutable intent still matches (TOCTOU); the approving session is not revoked
   (posture); and — to approve — **step-up verification** is satisfied. Reject,
   expiry, tamper, degraded posture, or a non-human attempt all resolve to
   **deny**; a missing step-up leaves the approval `pending` so the human can
   verify harder and retry.
3. **Execute, re-governed (Workstream A relay).** On an approved, step-up-verified
   decision the router issues a one-shot `CriticalConfirmation` and drives the
   Workstream A relay. The relay carries the confirmation onto the re-routed
   target so it clears the deny floor exactly once, while still running under the
   target's **own** capability gate, PolicyEngine review, decision mode, and B1
   pre-image capture at execution time. Success resolves the approval `executed`.

## Invariants (fail-closed)

| Control | Mechanism |
|---|---|
| Resting state is deny | Absence of an explicit human approval always means deny: silence, TTL expiry, session revocation, reject, tamper, and any non-human resolution attempt all resolve `denied`/`expired`, never execute. |
| Human-only resolution | `resolve_critical_approval` denies any non-`HUMAN` resolver and resolves the approval to `denied`. No decision mode, standing grant, scheduled routine, or subagent can call the human path — a grant's risk ceiling is sub-critical by construction, and `find_matching_standing_grant` refuses critical. |
| No confirmation smuggling | A critical action clears the floor only via `_critical_confirmation_valid`, which requires the acting principal to be a human, to *be* the principal named on the confirmation, and the referenced approval to be a real `critical` approval already claimed (`executing`) by the relay. An AI cannot satisfy the human check even with a hand-crafted confirmation. |
| Step-up before execution | Approving requires `step_up_verified` when the human's account is MFA-enrolled (conservative M2 rule pending F4's freshness signal); otherwise the approval stays `pending` (`needs_step_up`). |
| Immutable intent (TOCTOU) | The parked approval pins `action_payload_sha256`; `resolve_critical_approval` re-verifies it, and the relay re-verifies again at execution time. Drift → `critical_approval_payload_tampered`, no execution. |
| Bounded lifetime | Default 24 h TTL; a past-expiry critical approval resolves `expired` and never executes. |
| Execution-time re-verification | Execution runs through the relay + `route_action`, so the target's gate, policy, decision mode, and posture are all re-checked at execution time — the parked/approval-time state is never trusted. |
| Reconstructable control trail | Every transition (`created → notified → resolved/expired/denied/step_up_required`) is an audit event carrying the F1 posture snapshot, so "who was in control, when" is reconstructable from the append-only log alone. Metadata only — never arguments, tokens, or content. |

## Threats

- **T1 — AI self-authorizes a critical action.** An AI proposes a criterion-(a)–(e)
  action, or an explicitly-`CRITICAL` one. Mitigated: `route_action` parks it and
  never executes; only a human can resolve. Covered by
  `tests/test_critical_lifecycle.py::test_ai_critical_action_is_parked_and_owner_notified`
  and `test_critical_classification.py`.
- **T2 — AI resolves its own parked approval.** Mitigated: `resolve_critical_approval`
  denies any non-human resolver and resolves the approval to `denied`. Covered by
  `test_ai_cannot_resolve_critical`.
- **T3 — Forged confirmation bypasses the floor.** An AI hand-crafts a
  `CriticalConfirmation` and re-proposes the action. Mitigated: the human-principal
  and claimed-`executing`-approval checks fail; it is parked again. Covered by
  `test_ai_forged_confirmation_is_rejected` and
  `test_relay_cannot_execute_critical_without_confirmation`.
- **T4 — Silent resolution by TTL / delegation / automation.** Mitigated: expiry
  resolves `expired` (deny); no decision mode, grant, routine, or subagent can
  reach the human path. Covered by `test_expired_critical_approval_denies`.
- **T5 — TOCTOU: intent altered after the human sees it.** Mitigated: the intent
  hash is re-verified at resolve time and again by the relay. Covered by
  `test_tampered_critical_payload_denies`.
- **T6 — Approving session revoked between park and approval.** Mitigated: the
  posture check denies with `posture_degraded:session_revoked`; the approval
  stays actionable from a live session. Covered by
  `test_revoked_session_denies_resolution`.
- **T7 — Weak-auth approval of a critical action.** Mitigated: an MFA-enrolled
  human must present step-up before approval executes (`needs_step_up` until they
  do). Covered by `test_step_up_required_for_mfa_enrolled_human`.
- **T8 — Owner never learns a critical action was attempted.** Mitigated: parking
  always notifies the owner (D2), and every transition is an audit event. This is
  deliberately *more* visible than the old silent flat-deny.
- **T9 — Double execution / double resolution.** Mitigated: the relay's atomic
  `pending → executing → executed` state machine plus the `pending`-guarded
  resolve mean a critical approval executes at most once. Covered by
  `test_already_resolved_critical_is_refused`.

## What F7 does not cover

- **Full step-up freshness / re-auth (F4, M5).** M2 uses a conservative rule
  (MFA-enrolled ⇒ step-up required); F4 will compute the requirement from MFA
  freshness and drive an actual TOTP/re-auth challenge, relaxing to "only when
  stale". The `step_up_verified` signal is the seam.
- **Channel-relay delivery of the notification** beyond the dashboard + OS hook
  (Workstream D surfaces).
- **Narrowing the critical table.** The F6 table may only be extended; narrowing
  it (weakening the floor) is a governance change, enforced by the F5 validator.
