# Milestones (M0–M7)

> PR-sized milestones. Each milestone must leave the repo green on the full validation gate and
> must not weaken CLI behaviour, tests, or truthfulness checks. No fake runtime claims at any step.

## Validation gate (run for every milestone)

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
raiker --help
raiker --prompt "Hello Raiker"
# Frontend (from M1 onward):
npm --prefix apps/web run lint
npm --prefix apps/web run check        # svelte-check / tsc
npm --prefix apps/web run test         # vitest
npm --prefix apps/web run build
```

---

## M0 — Documentation (this deliverable)
- **Scope:** author `docs/UI-implementation/` (overview, IA, security UX, API contracts,
  milestones, per-milestone prompts).
- **Deliverables:** the files in this directory.
- **Acceptance:** docs internally consistent with verified backend; no overclaims; existing
  Python validation gate still green (docs-only change).

## M1 — UI skeleton
- **Scope:** `apps/web` Vite + Svelte + TypeScript app shell; left-nav; `RuntimeStatusBanner`;
  STOP switch placeholder (wired in M3); status-badge system; routing; a11y baseline.
- **Data:** local fixture JSON only, clearly labelled fake. No backend calls, no runtime claims.
- **Deliverables:** `apps/web/` project; badge + layout components; `package.json` with
  `lint`/`check`/`test`/`build`; CI-runnable frontend scripts; component tests for badges & shell.
- **Acceptance:** `npm run build/check/lint/test` green; keyboard nav + focus states; no claims
  that any runtime works.

## M2 — Read-only runtime dashboard
- **Scope:** wire read endpoints; build `CapabilityMatrix`, `EventLogViewer`, `CheckpointViewer`,
  `DiagnosticsPanel`, `DisabledCapabilityExplainer`, read-only Runtime Gates & Models views.
- **Backend:** add `POST /api/auth/session`, `GET /api/sessions`, `/api/turns/{id}`, `/api/events`,
  `/api/checkpoints[/{id}]`, `/api/models`, `/api/diagnostics`, `/api/tasks`.
- **Acceptance:** every screen shows real backend state; unsupported data shows
  "unavailable/not implemented"; Tier 2–6 caps render disabled/deferred; backend route tests pass
  (auth, schema, governance preserved).

## M3 — Prompt/session workflow + STOP switch
- **Scope:** `POST /api/prompts` + SSE stream; `ChatTurnTimeline` (gather→plan→act→verify);
  `ActionProposalCard`; live errors + policy decisions. Add `POST /api/interrupts`,
  `GET /api/tasks` wiring; activate STOP switch (cancel-at-safe-boundary).
- **Acceptance:** a prompt produces a streamed governed turn; a write-file proposal appears as
  `Approval-required` with a diff; STOP cancels active tasks at safe boundary with the right
  events; tests cover prompt lifecycle + interrupt events + AI-principal rejection on interrupt.

## M4 — Approval workflow
- **Scope:** `GET /api/approvals[/{id}]`, `POST /api/approvals/{id}/resolve`; `ApprovalQueue`,
  detail, diff; approve/deny with reason; persistent metadata-only banner.
- **Acceptance:** approving records `approval_received` with `executes_action=false` (UI states it);
  denying records `approval_denied`; tampered payload rejected; tests assert metadata-only.

## M5 — Security Settings (Runtime Mutations + Secret Settings)
- **Scope:** `StepUpAuthDialog`; `SecuritySettingsPanel` over existing control routes; Tier-2
  confirmation token + threat-model-ack inputs; fail-closed/deferred caps un-enableable; Secret
  Settings read-only with "secret storage deferred" notice. Capabilities/Runtime Gates stay
  read-only.
- **Acceptance:** enabling a *supported* gate succeeds + is event-logged; a fail-closed cap cannot
  be enabled (explainer shown); AI/non-authorised principal is blocked (403 + plain English);
  no secret input exists; tests assert governance + deferred display.

## M6 — Diagnostics & validation
- **Scope:** flesh out `DiagnosticsPanel`: readiness, validator status, missing config, disabled
  caps, provider health. No production-readiness claim beyond local single-user runtime.
- **Acceptance:** diagnostics match `/api/runtime-readiness`; no browser-side shell/validator
  execution; tests cover the diagnostics schema.

## M7 — Tests, docs & truthfulness
- **Scope:** frontend component/contract tests (vitest); backend endpoint + contract tests
  (pytest); a11y checks; **security regression tests**; docs + truthfulness validator update;
  `LOCAL_VALIDATION_GATE.md` update.
- **Security regression tests (required):**
  - UI/API cannot bypass policy/authority (denials still fire via API).
  - Disabled/deferred capabilities display correctly and are not enableable.
  - Approval resolution stays metadata-only (`executes_action=false`).
  - Sensitive domains (email/calendar/finance/medical/cctv/home_security/hardware) stay
    blocked/deferred unless backend says otherwise.
  - STOP only cancels at safe boundary; AI principal cannot interrupt/mutate gates.
- **Truthfulness update (alignment, not loosening):** update `README.md`, `docs/ARCHITECTURE.md`,
  `docs/IMPLEMENTATION_STATUS.md`, `docs/SECURITY_ARCHITECTURE.md`,
  `docs/API_AND_CONTRACT_SCHEMAS.md`, `docs/GAP_AND_TODO_ANALYSIS.md`,
  `docs/LOCAL_VALIDATION_GATE.md`, and `scripts/validate_repo_truthfulness.py` so the
  "launchable UI" marker includes the local web dashboard. Keep **every** `metadata_only` /
  `disabled_deferred` / risk marker enforced.
- **Acceptance:** full validation gate (Python + frontend) green.

## Dependencies & ordering

M0 → M1 → M2 → {M3, M4} → M5 → M6 → M7. M3 and M4 can be parallel after M2. The truthfulness
validator change lands in M7 (or the first milestone that makes the web UI actually launchable),
together with the doc updates, so the repo is never in an overclaiming state.
