# Raiker Web App — To Be Fixed

> Issues found while exercising the **Raiker web dashboard** end-to-end to write
> the [`webapp/`](webapp/README.md) user guide. Each item was reproduced against a
> freshly built `raiker-web` (`http://127.0.0.1:8765`) on a clean workspace, with
> a real browser (Chromium) driving the UI. Screenshots live in
> [`screenshots/not-working/`](screenshots/not-working/).
>
> **Nothing here is a security bypass request.** Several items are Raiker
> *correctly* failing closed; the problem is the **experience** (unclear errors,
> dead-end flows, missing hints), not the guardrail itself.

## Summary

| ID | Severity | Area | Status | One-liner |
|----|----------|------|--------|-----------|
| FIX-01 | Medium | Auth / first-run | ✅ **Fixed** | Primary button says "Unlock Raiker" before any account exists → "Authentication failed." |
| FIX-02 | High | Error clarity | ✅ **Fixed** | Provider connect error was over-redacted to `[REDACTED_SECRET]`. |
| FIX-03 | High | Models / governance | ✅ **Fixed** | Hosted-model activation was impossible from the web dashboard (dead-end). |
| FIX-04 | Low | MCP | ✅ **Fixed** | "Create server" button is clickable while the capability is disabled. |
| FIX-05 | Medium | Docs vs runtime | ✅ **Fixed** | Fresh workspace shows **all** gates `disabled`, contradicting the README's "integrated gates default enabled_runtime". |
| FIX-06 | Low | Tasks | ✅ **Fixed** | Queue open/scheduled/finished counts are confusing on a fresh workspace. |
| FIX-07 | Medium | Security / vault | ✅ **Fixed** | Vault-key field requires a Fernet key but gives no format hint. |

> **All seven items are resolved in this branch.** FIX-02 and FIX-03 landed
> earlier (below); FIX-01, FIX-04, FIX-05, FIX-06, and FIX-07 are addressed here.
> Hosted providers
> (Anthropic/OpenAI/Gemini) can now be enabled and used **entirely from the web
> dashboard**, with the threat-model acknowledgement and confirmation token
> collected in the governed step-up dialog — the security gate is preserved, not
> weakened. Verified end-to-end: enable *Hosted models* → connect the Anthropic
> key → select `claude-haiku-4-5-…` → live reply in Chat
> (`screenshots/working/26–29`).

---

### FIX-01 — First-run primary button says "Unlock Raiker" but no account exists yet

> ✅ **Fixed in this branch.** `LoginView.svelte` now drives the primary CTA's
> label, submit handler, confirm-password field, password autocomplete, and the
> greeting from a combined `registerIntent = isRegister || isFirstRun`. On first
> run the button reads **"Create a User Account"** and calls `auth.register`, so
> the copy and the action no longer disagree. The redundant account-switch,
> recovery, and secondary instance-creation controls (which have nothing to act on
> before any account exists) are hidden on first run. Covered by
> `LoginView.test.ts` ("registers the first account directly from the first-run
> CTA and validates confirmation").

- **Screenshot:** `screenshots/not-working/01-firstrun-cta-confusion.png`
- **Where:** `apps/web/src/lib/views/LoginView.svelte`
- **Repro:**
  1. Start `raiker-web` against a brand-new workspace and open it.
  2. The panel heading reads *"Welcome to Raiker → Create a User Account to get
     started"*, but the large primary button reads **"Unlock Raiker"**.
  3. Fill username/password and press the primary button.
- **Actual:** it calls the **login** path and returns *"Authentication failed."*
  (there is no account yet). The user must instead press the secondary **Create a
  User Account** button to switch into register mode.
- **Expected:** on first run (`isFirstRun`), the primary CTA should **register**,
  not log in — its label and submit handler should follow `isFirstRun`, not just
  `isRegister`.
- **Notes:** the copy (`isFirstRun`) and the button label/handler (`isRegister`)
  are driven by different conditions, so they disagree on first run.

---

### FIX-02 — Connect error is over-redacted to `[REDACTED_SECRET]`

> ✅ **Fixed in this branch.** `raiker/context/redaction.py` now spares lowercase
> `snake_case` reason codes from the high-entropy catch-all (via a callable
> replacement that matches `[a-z]+(?:_[a-z]+)+`), while still redacting real
> secrets (API keys, Fernet/base64 tokens always carry mixed case and/or digits).
> Errors like `provider_requires_explicit_policy_approval` now render verbatim.

- **Screenshot (before):** `screenshots/not-working/02-model-connect-redacted-error.png`
- **Where:** `raiker/context/redaction.py:47`
- **Repro:**
  1. Models → Anthropic → **Connect**, paste a key, **Connect**.
  2. With `hosted_model_runtime` disabled the server returns HTTP 403.
- **Actual:** the dialog shows **"Could not connect (403: `[REDACTED_SECRET]`)"**.
  The real reason code is `provider_requires_explicit_policy_approval` — verified
  directly against `ModelProviderFactory.create()`.
- **Root cause:** the redaction pass has a "long token looks like a secret" rule:
  ```python
  (re.compile(r"\b[A-Za-z0-9+/_\-]{40,}\b"), REDACTED_SECRET)
  ```
  `provider_requires_explicit_policy_approval` is a 42-character
  `[A-Za-z0-9_]` token, so it matches and is clobbered to `[REDACTED_SECRET]`.
- **Expected:** legitimate machine-readable reason codes must survive redaction so
  the user (and the guide) can see *why* a connection failed. Options: exclude
  reason-code fields from the generic token rule, require the token to contain
  mixed classes typical of secrets, or redact only known credential shapes.
- **Impact:** turns every long-reason-code error in the UI into a useless,
  slightly alarming message.

---

### FIX-03 — Hosted-model activation is impossible from the web dashboard

> ✅ **Fixed in this branch — the security gate is preserved, not weakened.**
> Changes:
> - **New governed endpoint** `POST /api/capability-gates/{capability}/threat-ack`
>   (owner/gate-manager only; only accepted for capabilities that actually
>   require an ack) records the acknowledgement and an audit event
>   (`threat_model_acknowledged`). Backed by `SQLiteStore.record_threat_model_ack`
>   and `RuntimeControlService.record_threat_model_ack`.
> - **Gate DTO now reports its real activation preconditions**
>   (`requires_threat_model_ack`, `requires_human_confirmation`,
>   `threat_model_ack_recorded`), so the frontend stops relying on a hardcoded
>   Tier-2 list.
> - **The step-up dialog** now shows the confirmation-token field *and* the
>   threat-model acknowledgement for any gate that needs them (driven by the DTO
>   flags), records the ack via the new endpoint, then runs the transition.
>
> Result: enabling *Hosted models* from the dashboard succeeds, and the full
> Anthropic path (connect key → select model → chat) works end-to-end. The human
> still explicitly acknowledges the threat model and supplies a confirmation
> token — nothing is auto-granted. Verified live; see
> `screenshots/working/26–29`.

- **Screenshot (before):** `screenshots/not-working/03-hosted-model-enable-deadend.png`
- **Where:** `apps/web/src/lib/views/CapabilitiesView.svelte`,
  `apps/web/src/lib/components/StepUpDialog.svelte`, `apps/web/src/lib/api.ts`
  (`setCapabilityState`), and the missing API route for threat-model acks.
- **Repro:**
  1. Capabilities → expand **Hosted models** → **Turn on**.
  2. Enter a reason → **Confirm change**.
- **Actual:** *"Activation is blocked. Satisfy the activation requirement first."*
  with **no way in the dialog to satisfy it**. The backend rejects with
  `activation_blocked:no_threat_model_ack:hosted_model_runtime` (verified via the
  API).
- **Root cause (two compounding bugs):**
  1. The step-up dialog only shows the **threat-model acknowledgement** when a
     *confirmation token* is required
     (`requireThreatAck = pending.requireToken`), and `hosted_model_runtime` is
     **not** in `TIER2_STEPUP_CAPS`, so no ack UI is shown.
  2. Even the collected `threatAck` boolean is **never sent**:
     `api.setCapabilityState` posts only `{ target_state, reason,
     confirmation_token }`. And there is **no governed API route** to record a
     threat-model ack at all — the only writer is the CLI
     (`raiker/cli/principal_resolver.py`, `INSERT … threat_model_acks`).
- **Expected:** a web-only owner should be able to complete hosted-model
  activation — the dialog should present the threat-model acknowledgement for any
  gate that needs one, and the client + a governed endpoint should persist it.
  Failing that, the dialog should tell the user the exact out-of-band step
  (which CLI command records the ack) instead of a dead-end.
- **Impact:** **hosted providers (Anthropic / OpenAI / Gemini) cannot be used from
  the web app alone.** Because saving the key also 403s until the gate is on
  (FIX-02), the whole hosted path is unreachable via the dashboard.

---

### FIX-04 — MCP "Create server" button is clickable while the capability is disabled

> ✅ **Fixed in this branch.** `McpView.svelte` now disables the **Create server**
> button (plus the name input and template select) whenever `mcp_builder_runtime`
> is off, and adds a `title` hint pointing to Capabilities — matching the other
> gated controls. Failing closed is unchanged; the doomed 403 request is no longer
> fireable from a live button.

- **Screenshot:** `screenshots/not-working/05-mcp-capability-disabled.png`
- **Where:** `apps/web/src/lib/views/McpView.svelte`
- **Repro:** MCP Servers → type a server name → **Create server** (with the MCP
  capabilities disabled, i.e. the default).
- **Actual:** the button is enabled and the click issues a request that returns
  **403**, then the page shows *"The MCP capability is disabled. Enable it in
  Capabilities to continue."*
- **Expected:** the button should be **disabled** while the capability is off
  (matching other gated controls like "Save key"), or it should route the user
  straight to the enable flow. Failing closed is correct; letting the user fire a
  doomed request is the snag.
- **Severity:** low — the message is clear and no harm is done.

---

### FIX-05 — Fresh workspace shows all capability gates `disabled` vs README claim

> ✅ **Fixed in this branch — reconciled as documentation + a UI affordance.** The
> real cause is two deliberate design layers, now spelled out instead of implied:
> (1) the web dashboard runs under **per-principal controls that fail closed** —
> `RuntimeAuthority.get_effective_capability_gate` returns `disabled`
> (`source: principal_fail_closed`) for any account principal until the owner turns
> a gate on, so the `enabled_runtime` static default only describes the single-user
> CLI posture; and (2) reaching `enabled_runtime` at all requires an active
> runtime-enablement mode (`local_single_user_runtime`/`multi_user_local_runtime`),
> not the default **Development preview**. `README.md`, `docs/RUNTIME_EXECUTORS_SPEC.md`,
> and `docs/guide/core-concepts.md` now state both facts, and the **Capabilities**
> view shows an inline note (when integrated gates read off) pointing the user to
> **Settings → Runtime mode**.

- **Where:** `README.md` (Project Status), `raiker/phase_gates.py`
  (`REAL_EXECUTOR_CAPABILITIES`), runtime-mode activation.
- **Repro:** `GET /api/capability-gates` on a fresh workspace.
- **Actual:** **all 61 gates** report `state: disabled`, `runtime_enabled: false`
  — including the integrated real-executor capabilities.
- **Expected / to reconcile:** the README states *"Integrated capabilities (those
  with a real executor) default to `enabled_runtime`."* Either (a) that default
  only applies after a non-preview **runtime mode** is activated (in which case
  the docs and the Diagnostics/Capabilities UI should say so prominently), or
  (b) it's an inaccuracy. Today a new user in **Development preview** sees
  everything off and no obvious "activate runtime so integrated tools come online"
  affordance.
- **Impact:** sets the wrong expectation about what works out of the box.

---

### FIX-06 — Task queue counts are confusing on a fresh workspace

> ✅ **Fixed in this branch — product decision: chat turns are not user tasks.**
> Every chat turn spawns an internal governance task (`title="Chat turn"`,
> `parent_turn_id` set) via `AgentGateway.astream_prompt`. Those are internal
> records, surfaced in Sessions/Audit — not user-planned work — so
> `DashboardService.list_tasks` (the `/api/tasks` reader) now excludes tasks with a
> `parent_turn_id`. The **open / scheduled / finished** counters and the **Parent
> work** picker therefore reflect only user-created tasks. Interrupts still operate
> on the raw store list, so a running chat turn can still be stopped. Covered by
> `tests/test_phase_2_task_manager.py::TestDashboardTaskFiltering`.

- **Screenshot:** `screenshots/working/07-tasks-created-all-types.png` (counts row)
- **Where:** `apps/web/src/lib/views/TasksView.svelte` (`active` / `scheduled` /
  `history` derivations).
- **Repro:** on a fresh workspace, create one **Task**; watch the
  **open / scheduled / finished** summary.
- **Actual:** the three counters move in ways that don't match intuition — an
  immediate task that runs without a model lands in **finished**, and prior chat
  turns appear as selectable **Parent work**, so "finished" can be non-zero after
  creating a single task.
- **Expected:** clarify whether chat turns should count as tasks/parents, and make
  the counters reflect only user-created tasks (or label them so the numbers are
  self-explanatory).
- **Severity:** low — needs a product decision; flagged for verification.

---

### FIX-07 — Vault key field requires a Fernet key but gives no format hint

> ✅ **Fixed in this branch.** `SecurityLogin.svelte` now states the required
> format inline ("a **Fernet key**: 32 random bytes, URL-safe base64, 44 chars"),
> shows the copy-pasteable `Fernet.generate_key()` command, and adds a **Generate
> key** button that mints a valid key client-side (Web Crypto `getRandomValues` →
> URL-safe base64, mirroring `Fernet.generate_key()`) and reveals it for review.
> The key still saves only through the existing governed, elevated-re-auth flow.
> The invalid-key error was rewritten from the bare reason code to actionable
> guidance ("a plain passphrase will not work"). The backend
> `raiker/auth/vault_key_file.py` is unchanged — it correctly requires a real
> Fernet key.

- **Screenshot:** `screenshots/not-working/04-vault-key-invalid-no-hint.png`
- **Where:** `apps/web/src/lib/views/settings/SecurityLogin.svelte`,
  `raiker/auth/vault_key_file.py` (`Fernet(value.encode("ascii"))`).
- **Repro:** Settings → Security & Login → **Vault key** = `mypassphrase123`,
  confirm password, **Save key**.
- **Actual:** *"Could not save the vault key. (connector_vault_key_invalid)"*. The
  field placeholder is just dots, and the only guidance ("Configure
  `RAIKER_CONNECTOR_VAULT_KEY`") never states the format.
- **Expected:** the field should state that a valid **Fernet key** is required
  (32-byte URL-safe base64, 44 chars), ideally with a **Generate** button or a
  copy-pasteable command:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
  A plain passphrase silently failing "invalid" is a dead end for most users.
- **Impact:** blocks the entire Connections/connector flow for anyone who doesn't
  already know Fernet key format.

---

## What was verified working (for contrast)

These all behaved correctly and are documented in [`webapp/`](webapp/README.md):

- Build + launch; all 17 views render with **zero console errors**, light & dark.
- First-run registration → dashboard; password unlock; in-memory-only session
  token.
- Chat: send → honest `model_unavailable` failure with a "how this turn was
  governed" trail; conversation saved under **Recent chats**, listed in
  **Sessions**, and found in **Search Chat**.
- Tasks: all four kinds (Task, Schedule once, Daily routine, Background agent)
  create and queue.
- Capabilities: governed decision-mode change (reason + confirm, enforced
  server-side) with clear `decision_mode_requires_executor` guardrails.
- Models: local rows, hosted connect dialog, fallback editor, advisor selector,
  read-only posture card.
- Connections: Connector Store renders; **Install** works once a **valid** Fernet
  vault key is set (badge flips to "Active / Valid").
- Settings: all six tabs; runtime-mode controls; MFA-enrol and credential-scan
  controls.
- Sessions / Audit log / Checkpoints / Diagnostics / Brain View / Memory: honest,
  data-backed content and empty states.

## How to reproduce this test run

```bash
# 1. build + launch
npm --prefix apps/web install && npm --prefix apps/web run build
raiker-web --workspace ./.ws --port 8765 --no-browser

# 2. drive the UI with Chromium (Playwright), or click through manually
#    following docs/guide/webapp/*.md
```
