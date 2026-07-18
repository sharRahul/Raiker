# Control Deck Task 5 Credential Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner redacted, actionable credential lifecycle and local runtime-health findings without storing or exposing raw secrets.

**Architecture:** Add owner-scoped lifecycle and monitor-state rows alongside the existing shared `security_findings` and `notifications` substrate. `CredentialLifecycle` computes 75/90-day status and verifies manual replacement; `SecurityMonitor` performs explicit local pattern, opt-in HIBP, and vault-health checks. The existing Security & Login view renders the typed, redacted server state.

**Tech Stack:** Python 3.13, SQLite additive migrations, FastAPI/Pydantic, Svelte 5/TypeScript, Vitest, Playwright.

## Global Constraints

- Never persist, emit, return, or display a raw credential, password, full hash, HIBP suffix/body, matched local content, or line number.
- HIBP is disabled unless the authenticated owner explicitly enables it and `api.pwnedpasswords.com` is in the owner egress allowlist.
- Reuse `security_findings` and `notifications`; deduplicate active state transitions and create a recovery notification only when a finding clears.
- No provider-side credential rotation, background daemon, email/desktop delivery, or universal-security claim.
- Windows plugin runtime defaults to direct `python`; preserve `python3` elsewhere so the full test gate remains reliable.

---

### Task 1: Lifecycle and monitor persistence

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Create: `tests/test_credential_security.py`

**Interfaces:**
- Produces `upsert_credential_lifecycle(principal_id, provider, verified_at)` and `list_credential_lifecycle(principal_id)`.
- Produces `get_monitor_state(principal_id, source, subject_id, code)` and `set_monitor_state(...)` for state-transition deduplication.

- [x] Write failing tests for a 75-day warning, a 90-day overdue record, and an owner-isolated lifecycle list.

```python
def test_lifecycle_is_overdue_after_ninety_days(store: SQLiteStore) -> None:
    store.upsert_credential_lifecycle("owner", "github", verified_at="2026-04-01T00:00:00Z")
    assert CredentialLifecycle(store, clock=lambda: "2026-07-01T00:00:00Z").list("owner")[0].status == "overdue"
```

- [x] Run the focused test and confirm RED because the service/storage methods are absent.
- [x] Add migration `RAIKER-1021-credential-security` with `credential_lifecycle` and `security_monitor_state`, both keyed by `principal_id`; add SQLite methods that never accept a secret value.
- [x] Run the focused test and confirm GREEN.

### Task 2: Redacted lifecycle, breach, and health services

**Files:**
- Create: `raiker/security/credentials.py`
- Create: `raiker/security/monitoring.py`
- Modify: `raiker/storage/sqlite.py`
- Create: `tests/test_runtime_monitoring.py`

**Interfaces:**
- `CredentialLifecycle.verify_replacement(principal_id, provider) -> CredentialLifecycleView` requires a configured encrypted credential metadata row before changing the verified timestamp.
- `SecurityMonitor.scan_configured_paths(principal_id) -> list[SecurityFinding]`, `check_password_breach(principal_id, password, enabled)`, and `check_vault_health(principal_id)` write redacted finding/notification transitions. Scan roots come only from owner-configured workspace-relative paths.

- [x] Write failing tests for unverified replacement refusal, a local credential-like pattern with no matched text in SQLite, an offline HIBP skip, a five-character SHA-1 range prefix, alert deduplication, and one recovery alert.

```python
def test_hibp_request_uses_only_sha1_prefix(http_fn) -> None:
    SecurityMonitor(store, http_fn=http_fn).check_password_breach("owner", "correct horse", enabled=True)
    assert http_fn.urls == ["https://api.pwnedpasswords.com/range/AAF4C"]
```

- [x] Run `python -m pytest -p no:cacheprovider tests/test_credential_security.py tests/test_runtime_monitoring.py -q` and confirm RED.
- [x] Implement the services using `classify_memory_sensitivity` for local text classification and the existing bounded `get_url` helper for HIBP. Keep response data transient; persist only a `breached` boolean/count class and remediation text.
- [x] Implement one shared transition helper: open a finding plus notification only if current state changes; resolve it and send one recovery notification only when a prior active state becomes healthy.
- [x] Run both focused files and confirm GREEN.

### Task 3: Authenticated contracts and Security & Login view

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.svelte`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.test.ts`
- Modify: `tests/test_api_security.py`

**Interfaces:**
- Owner-scoped `GET /api/security/credentials`, `GET /api/security/findings`, and `GET /api/security/health` return redacted DTOs.
- Explicit authenticated actions are `POST /api/security/credentials/{provider}/verify`, `POST /api/security/scan`, `POST /api/security/breach-check`, and `POST /api/security/health-check`; the scan action accepts no browser-supplied path.

- [x] Write failing API/component tests: another owner sees no lifecycle/finding rows; the UI shows warning/overdue status and remediation; a scan action renders its redacted finding; raw test secret text is absent.
- [x] Run the targeted Python and Vitest files and confirm RED because the routes/client/view controls are absent.
- [x] Add dashboard DTO mapping and Pydantic request validation; require a human session, read only owner-configured workspace-relative scan paths, and make the breach action accept the password only for the transient request.
- [x] Add the minimal Security & Login card: lifecycle table, redacted findings/health status, a verified-replacement button, explicit scan/check buttons, and an explicit breach opt-in with plain-English remediation. Do not add a generic settings framework.
- [x] Run targeted API/Vitest tests and confirm GREEN.

### Task 4: Verification, evidence, and documentation

**Files:**
- Modify: `docs/plans/2026-07-16-raiker-control-deck-implementation.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/HANDOFF.md`
- Create: `docs/threat-models/credential-security.md`

- [x] Build the web app and use a disposable workspace to register/login, trigger a redacted local finding and health failure, inspect remediation, perform the opt-in breach request, and capture screenshots. Native Python Playwright was unavailable; the installed Node Playwright runtime drove system Chrome instead.
- [x] Run all Python tests in two alphabetical file batches with `-p no:cacheprovider`, then `ruff`, `mypy`, `compileall`, all five validators, web check/lint/test/build, and `git diff --check`.
- [x] Update the authoritative Task 5 result and future bounded-detector roadmap in the tracked plan, status, handoff, user guides, and threat model; record every command result and the browser-runtime limitation honestly.
- [x] Commit the Task 5 implementation plus the already-tested Windows interpreter fix, push `main`, and verify the pushed commit's GitHub workflows are green. The initial CI run caught missing type annotations in a new test; follow-up `e92882c` fixed them, and its CI (Python 3.11/3.12) plus Phase Status Validation completed successfully.

## Plan Self-Review

- Coverage: Tasks 1–3 implement each approved control and the required web view; Task 4 supplies browser, CI, and document proof.
- No placeholders: every task names concrete files, interfaces, test behavior, and commands.
- Scope: future detectors remain documented follow-up work; no unsupported provider rotation or universal detection is implied.
