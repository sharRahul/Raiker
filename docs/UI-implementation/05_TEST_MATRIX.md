# Security Test / Acceptance Matrix

> Planning document. Each row maps a **security invariant** the UI must never violate to the
> **regression test** that proves it and the **milestone** that owns it. These are the tests that
> must fail if a future change weakens governance. Cross-references `03_API_CONTRACTS.md`
> (per-route test obligations) and the M7 prompt.

## Invariants → tests

| # | Invariant | How it's proven (test) | Layer | Milestone |
|---|---|---|---|---|
| 1 | UI/API cannot bypass policy/authority | API call that would be denied still returns `403 {ok:false, reason_code}`; assert `RuntimeAuthority` denial fires (not the route) | backend (pytest) | M7 (routes from M2–M5) |
| 2 | Disabled/deferred caps are not enableable | `POST /api/capability-gates/{cap}/set` on a no-executor cap → blocked; `CapabilityGateView.can_current_principal_change=false` | backend + frontend | M5/M7 |
| 3 | Disabled/deferred caps display honestly | `CapabilityMatrix` renders backend `state`/label verbatim; a disabled cap never shows "enabled" | frontend (vitest) | M2/M7 |
| 4 | Approval resolution stays metadata-only | `POST /api/approvals/{id}/resolve` response `executes_action=false`; action not executed; only `approval_received`/`approval_denied` emitted | backend | M4/M7 |
| 5 | Sensitive Tier-6 domains stay blocked/deferred | email/calendar/finance/medical/cctv/home_security/hardware gates report disabled/deferred and route_action denies (no executor) | backend | M7 |
| 6 | STOP cancels only at safe boundary | `POST /api/interrupts` emits `interrupt_received`→`safe_boundary_reached`→`task_cancelled`; no hard-kill semantics | backend | M3/M7 |
| 7 | AI principal cannot mutate gates/modes | mutation routes with an AI principal → `403 ai_cannot_manage_runtime_gates` / `ai_cannot_enable_runtime_gate` | backend | M5/M7 |
| 8 | AI principal cannot interrupt | `POST /api/interrupts` as AI principal → 403 | backend | M3/M7 |
| 9 | AI cannot self-approve | resolve as the proposing AI principal → denied (`ai_cannot_approve_own_action`) | backend | M4/M7 |
| 10 | Token never persisted in browser storage | frontend test asserts token held in memory only; not written to localStorage/sessionStorage | frontend | M2/M7 |
| 11 | Server bound local-only | `apps/api/main.py` binds `127.0.0.1`; no permissive CORS configured | backend/config | M2/M7 |
| 12 | Secret storage is not implied | Security Settings → Secret Settings has no secret input; shows "deferred" notice | frontend | M5/M7 |
| 13 | `reason_code` catalog has no overclaims | every code listed in `02_SECURITY_UX.md` exists in the codebase (grep/AST assertion) | backend (pytest) | M7 |
| 14 | Truthfulness markers preserved | `scripts/validate_repo_truthfulness.py` + `validate_phase_status.py` pass after the launchable-UI marker update; no disabled/metadata marker removed | validators | M7 |
| 15 | No silent hosted fallback | `GET /api/models` reports `no_silent_hosted_fallback`; selecting a hosted profile does not enable a hosted runtime | backend | M2/M7 |

## Notes
- Tests 1, 2, 5, 7–9 are the core "no privileged interface" proofs — they assert the *backend*
  denies, so they hold regardless of frontend behaviour.
- Test 13 is the anti-drift guard for `02_SECURITY_UX.md`; if a `reason_code` is renamed in code
  without updating the doc, this test fails.
- Frontend tests (3, 10, 12) assert presentation honesty; backend tests assert enforcement.
