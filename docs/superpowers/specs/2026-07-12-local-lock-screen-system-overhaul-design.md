# Design — Local-Owner Lock Screen & System Overhaul

- **Date:** 2026-07-12
- **Status:** Draft for review
- **Author:** Raiker maintainer + Claude (brainstorming)
- **Scope:** Single comprehensive spec covering all 9 epics from the product brief.

---

## 1. Objective & Locked Decisions

Add a **device-local, multi-account lock screen** to Raiker whose real purpose is to
protect per-user connector credentials (OAuth tokens + API keys for GitHub, Gmail, etc.),
plus a set of interface/settings/navigation changes.

Raiker stays **single-machine, loopback-only** (`127.0.0.1`). It does **not** become a
hosted multi-tenant service. "Multi-user" means two or more local profiles sharing one
device (user 1, user 2, … — the people are arbitrary), each fully isolated from the others.

**Decisions locked during brainstorming:**

| # | Decision | Choice |
|---|---|---|
| 1 | Account isolation | **Full per-account isolation** — one `principal_id` per account; separate connections, sessions, chats, vault entries. |
| 2 | Vault crypto | **Single machine-wide key** (`RAIKER_CONNECTOR_VAULT_KEY`, Fernet). Login gates access; per-principal rows are all encrypted with this one key. Password reset never loses stored tokens. |
| 3 | MFA methods | **TOTP only.** No SMS/Email at all (not even a stub) — deferred entirely, may be picked up later. |
| 3b | MFA ⟂ Vault | **Independent.** MFA and Vault are separate user choices; neither requires the other. A user may enable MFA without a Vault, or use a Vault without MFA. Optional policy toggle in Security & Login: *"require MFA for Vault operations."* Off by default; never force-coupled. |
| 4 | Delivery | **One comprehensive spec** (this doc) covering all 9 epics. |
| 5 | Honesty (Section H) | **No lying toggles.** Settings without runtime backing render as clearly-labeled "not yet active / fails closed." |
| 6 | Vault key persistence | Web App is the control surface. Master key stored in a `0600` key-file loaded at boot (env var overrides); set/replace/clear behind elevated re-auth. |

### Three classes of secret (do not conflate)

| Class | What | Storage | Reversible? |
|---|---|---|---|
| Account password | login password | Argon2id encoded hash in `account_credentials` | No — one-way, never shown back |
| Connector credentials | API keys, OAuth tokens | Fernet-encrypted in `connector_credentials`, per-`principal_id` | Yes (by vault key), never revealed to UI |
| Vault master key | the Fernet key protecting class 2 | single `0600` key-file; env overrides | it is the bootstrap secret |

---

## 2. What Already Exists (build on, don't rebuild)

- **Session store** — `raiker/api/sessions.py`: CSPRNG `secrets.token_hex(32)`, SHA-256 hash at rest, `expires_at`, `revoke_session`, `list_sessions`. Table `api_sessions`.
- **Auth gate** — `raiker/api/auth.py` `AuthMiddleware.authenticate` (Bearer). Every governed `/api` route already depends on it via `Depends(_auth)`.
- **Owner mint seam** — `raiker/api/routes_dashboard.py:36` `POST /api/auth/session` currently mints an owner token **unauthenticated** (loopback trust). This is the exact endpoint that becomes username+password+MFA login.
- **Principals** — `raiker/runtime/authority/models.py` `Principal`; `SQLiteStore.get_principal`. Owner-bootstrap chain exists.
- **Vault** — `raiker/runtime/connector_ecosystem.py`: `ConnectorVault` (Fernet), `configured()`, fail-closed on missing/invalid key. Credentials keyed by `principal_id` + `connector_id`. OAuth refresh + egress allowlist present.
- **Connector catalog** — `raiker/config/connector-store.json` (currently **26** connectors — brief said 23; gallery targets "all in the store").
- **Transport hardening** — `raiker/api/security.py`: rate-limit, max-body, security-headers middleware in `create_app`.
- **Migrations** — `raiker/storage/migrations.py`: additive `CREATE TABLE IF NOT EXISTS` blocks keyed by migration id (e.g. `PHASE_5_ORG_ROLES_MIGRATION_ID`). `users`, `roles` tables already present.
- **Web** — Vite + Svelte SPA in `apps/web/src`; views in `lib/views/*`, grouped nav in `lib/nav.ts`, `App.svelte` shell.

---

## 3. Auth Spine — Server-Authoritative Multi-Stage State Machine

The server owns login state. The client cannot skip a stage (defeats OWASP A01/A07 MFA bypass).

```
POST /api/auth/register  {username, password}          # provisions Principal + account_credentials
POST /api/auth/login     {username, password}
   password fail  -> 401 generic "Invalid username or password"     (A05 no enumeration)
   password ok, no MFA  -> SESSION ISSUED   (scope: control)
   password ok, MFA on  -> PRE-AUTH TICKET  (scope: mfa_pending, ~5 min TTL, CANNOT call governed /api)
POST /api/auth/mfa/verify {ticket, code}
   ok  -> SESSION ISSUED (scope: control)
POST /api/auth/logout                                   # revokes current session
```

- `AuthMiddleware` rejects any governed route whose session `scope` is `mfa_pending`.
  A password-only token literally lacks the `control` scope → no downstream API access,
  no matter what URLs/params/tokens the client manipulates.
- Pre-auth ticket is a row in `api_sessions` with `scope='mfa_pending'` and a short absolute expiry.
- Elevated actions (change vault key, reset MFA) require a fresh `scope='elevated'` grant
  obtained by re-entering password or passing MFA; short TTL.

**Rate-limit / lockout (A04):** per-username **and** per-IP failed-attempt counters in
`account_credentials.failed_attempts` + `locked_until`. Progressive delay, lock after 5
consecutive failures. Reset on success.

**Enumeration resistance (A05):** one generic error string for every
username-not-found / bad-password / locked outcome. Constant-ish time: always run a hash
verify (against a dummy hash if the user is absent).

---

## 4. Data Model (new migration `RAIKER-6001-local-lock-screen`)

```sql
CREATE TABLE IF NOT EXISTS account_credentials (
  principal_id          TEXT PRIMARY KEY,
  username              TEXT NOT NULL UNIQUE,
  password_hash         TEXT NOT NULL,          -- self-describing argon2id / scrypt encoded string
  hash_algo             TEXT NOT NULL,          -- 'argon2id' | 'scrypt'
  failed_attempts       INTEGER NOT NULL DEFAULT 0,
  locked_until          TEXT,
  mfa_enrolled          INTEGER NOT NULL DEFAULT 0,
  mfa_secret_encrypted  BLOB,                   -- Fernet( TOTP seed ) with the APP key, not the vault key (A02 seed-at-rest)
  backup_codes_hashed   TEXT,                   -- JSON array of hashes
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL
);

-- extend api_sessions
ALTER TABLE api_sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'control';   -- control|mfa_pending|elevated
ALTER TABLE api_sessions ADD COLUMN absolute_expires_at TEXT;                -- hard cap, non-sliding
ALTER TABLE api_sessions ADD COLUMN last_seen_at TEXT;
ALTER TABLE api_sessions ADD COLUMN device_label TEXT;

CREATE TABLE IF NOT EXISTS user_settings (
  principal_id TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL,                  -- the 9-section config blob
  updated_at TEXT NOT NULL
);

-- extend tasks
ALTER TABLE tasks ADD COLUMN priority TEXT;                 -- low|normal|high|urgent
ALTER TABLE tasks ADD COLUMN scheduled_at TEXT;
ALTER TABLE tasks ADD COLUMN recurrence TEXT;              -- none|daily|weekly|monthly|cron-ish
ALTER TABLE tasks ADD COLUMN reminder_at TEXT;

CREATE TABLE IF NOT EXISTS trusted_contacts (
  contact_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  method TEXT NOT NULL,                          -- email|phone
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

Registration provisions a Principal + `account_credentials` row. Because connector
credentials, installations, sessions, tasks, and chats all already key on `principal_id`,
per-account isolation is automatic.

`ALTER TABLE ... ADD COLUMN` runs only if the column is absent (guarded via `PRAGMA table_info`
check in the migration runner, matching existing additive style).

---

## 5. Password Hashing (Epic 1)

- Primary: **Argon2id** via `argon2-cffi` — `memory_cost=19456` KiB (19 MiB), `time_cost=2`,
  `parallelism=1`. Encoded hash self-describes params; verify re-derives them.
- Fallback (Argon2 unavailable): **scrypt** (`hashlib.scrypt`) — `n=2**17`, `r=8`, `p=1`,
  32-byte salt, stored as `scrypt$n$r$p$salt$hash`.
- Salt per password (argon2-cffi salts internally; scrypt uses `secrets.token_bytes(16)`).
- Verify path selects by `hash_algo`. Needs-rehash check upgrades scrypt→argon2 on next login
  if argon2 becomes available.
- New dependency: `argon2-cffi` in `pyproject.toml` (with graceful import guard → scrypt).

---

## 6. MFA — TOTP only (Epic 1)

MFA is **fully independent of the Vault** — either can be used without the other. To make
that possible, the TOTP seed is encrypted with an **internal app key** (§8b), which always
exists, not the user-managed connector vault key.

- `pyotp` (new dep). Server generates a 160-bit base32 secret → Fernet-encrypt with the
  **app key** → store `mfa_secret_encrypted`. No dependency on vault configuration.
- Enroll: `POST /api/auth/mfa/enroll` → returns `otpauth://` provisioning URI (UI renders QR)
  + one-time display of backup codes (stored hashed). Activate on first valid `verify`.
- Verify: `POST /api/auth/mfa/verify` with drift window ±1 step.
- Reset/disable MFA: requires `elevated` scope; **revokes all other sessions** on success.
- Enrollment prompted at registration (skippable) and available in Security settings.
- **No SMS/Email.** Removed entirely from scope — no channel, no stub, no egress. May be
  revisited in a future iteration.
- Optional policy (§12): *require MFA for Vault operations.* When a user opts in **and** has
  MFA enrolled, vault-key set/replace/clear additionally requires a fresh MFA verification.
  Off by default; never auto-coupled.

---

## 7. Session Security (Epic 1 / A07)

- Keep CSPRNG + SHA-256-at-rest tokens.
- Add **absolute expiry** (`absolute_expires_at`), enforced in `AuthMiddleware` alongside
  sliding `expires_at`.
- Add `ApiSessionStore.revoke_others_for_principal(principal_id, keep_session_id)` — called on
  password change and MFA reset → all other devices invalidated server-side immediately.
- `last_seen_at` updated per authenticated request (for the Sessions settings list).
- Security & Login settings tab lists active sessions (device label, created, last seen) with
  per-session and "revoke all others" controls.

---

## 8. Vault Key UX & Fail-Closed (Epic 3)

- `GET /api/vault/status` → `{state: configured_valid | missing | invalid}` drives the pill:
  `[ Active / Valid ]` green vs `[ Missing / Fail-Closed Active ]` bright red.
- Settings field: masked (`••••••••`) with **Reveal** toggle.
- `PUT /api/vault/key` (set/replace) and `DELETE /api/vault/key` (clear) — both require
  `scope='elevated'` (re-enter password or pass MFA first). Writes/removes the `0600` key-file
  at `<workspace>/.raiker/vault.key`; env var `RAIKER_CONNECTOR_VAULT_KEY` overrides file when set.
- Boot loader: if env unset and key-file present + valid, load into process env before the
  vault is used.
- Fail-closed already enforced by `ConnectorVault._fernet()`; add a startup readiness line and a
  clear non-descriptive admin-log error when connector init aborts on missing/invalid key
  (acceptance 5-final). Retrieval, session use, and outbound routing already refuse without a
  valid key.

---

## 8b. Internal App Key (decouples MFA from Vault)

Distinct from the user-managed connector vault key. The app key encrypts Raiker's own
internal at-rest secrets (currently only MFA TOTP seeds) so those features never depend on
whether the user has set up a connector vault.

- Location: `<workspace>/.raiker/app.key`, mode `0600`.
- **Auto-generated** on first boot if absent (`Fernet.generate_key()`) — always present,
  never user-facing, never entered through the UI.
- Not the connector vault key, not overridable by `RAIKER_CONNECTOR_VAULT_KEY`, and its
  absence does **not** trigger connector fail-closed (separate concern).
- If the file is deleted, existing MFA seeds become undecryptable → affected users must
  re-enroll MFA (documented; matches the honest fail behavior).

---

## 9. Navigation & Sidebar (Epic 4) — rewrite `apps/web/src/lib/nav.ts`

- **The Hustle** (renamed from *Work*): `New Chat`, `Search Chat`, `Tasks`, `Approvals`, `Projects`
  — Approvals now **below** Tasks.
- **Steering** (renamed from *Governance*): `Capabilities`, `Models`, `Connections`, `Checkpoints`.
- **System**: `Sessions`, `Audit log`, `Diagnostics`, `Settings` — Sessions + Audit **moved here**.

New route ids: `new-chat`, `search-chat`. `DEFAULT_ROUTE` → `new-chat`. Update `App.svelte`
routing + any `routeFromHash` consumers and tests (`App.test.ts`, `a11y.test.ts`).

---

## 10. Interface Features (Epic 2)

- **New Chat** — `ChatView` renamed/retargeted to route `new-chat`; opens a clean empty session
  ready for input (no auto-loaded history).
- **Search Chat** — new `SearchChatView.svelte`, route `search-chat`. Searchable, categorized
  repository over existing sessions/turns store. Backend: `GET /api/sessions/search?q=&category=`
  (filters existing session/turn data; no new storage).
- **Task window** — `TasksView` gains a create form (title, description, priority) and a schedule
  block (date-time picker → `scheduled_at`, `reminder_at`, `recurrence`). Wire to the governed
  task-create path; new/extended endpoint `POST /api/tasks`. Truthful about which scheduling
  fields actually drive runtime behavior vs. are stored-only (per Section H).

---

## 11. Connector Gallery (Acceptance §5)

- `ConnectionsView` becomes a unified gallery: browse, search, install, uninstall **all**
  connectors in `connector-store.json` (currently 26). Install/uninstall write
  `connector_installations` per `principal_id`.
- Credentials add/remove/replace via existing vault put/delete (masked, never revealed back).
- Write actions ("write" ops, e.g. draft/booking) already carry `requires_confirmation` on
  non-GET operations and route through the approval/confirmation path → LLM write-action confirm
  is satisfied by the existing broker; gallery surfaces the confirmation.
- Tokens tied to `principal_id`; auth only at initial setup or on token expiry (OAuth refresh
  path already exists).

---

## 12. Settings — 9-Section Taxonomy (Epic §4.1)

Rebuild `SettingsView.svelte` into a left-rail 9-section layout. Persisted per principal in
`user_settings`. Honesty rule (Section H) applied per field.

| Section | Backed-for-real now | Honest "not yet active" |
|---|---|---|
| General | language, region, default startup route | — |
| Notification | in-app popup/desktop/email toggles (stored; in-app honored) | email delivery (no SMTP yet) |
| Personalisation | theme (light/dark), layout spacing, font | — |
| Voice | — | input/output device, STT sensitivity (no voice runtime) |
| Data Controls | history-tracking state, export request (maps to storage-lifecycle) | model-training permission (no trainer) |
| Storage | cache clear, local usage metrics, attachment threshold | cloud usage metrics (no cloud) |
| Security & Login | password reset, active sessions, MFA enroll (independent of Vault), **Vault Key config**, opt-in toggle *"require MFA for Vault operations"* (only effective if MFA enrolled) | — |
| Trusted Contact | store recovery contacts (`trusted_contacts`) | emergency-access automation |
| Account | profile update, account deletion | — |

Account deletion removes the principal, its `account_credentials`, sessions, vault rows,
installations, settings — real and irreversible (confirmation + re-auth gated).

---

## 13. Security Acceptance Mapping (§5.1)

| Criterion | Mechanism |
|---|---|
| A01/A07 MFA bypass (CWE-287) | Server state machine; `mfa_pending` scope cannot reach governed routes |
| A02 crypto (CWE-311) | Argon2id password hash; MFA seed Fernet-encrypted with the internal app key (§8b); connector creds Fernet-encrypted with the vault key. Loopback origin; TLS is a deployment-layer concern (documented) |
| A03 injection (CWE-89) | Parameterized SQLite everywhere (existing norm); no string-built SQL |
| A04 brute-force (CWE-307) | Per-username + per-IP counters, progressive delay, lockout after 5 |
| A05 error leakage (CWE-209) | Single generic auth error; constant-work verify; non-descriptive admin logs |
| A07 session (CWE-613) | CSPRNG + hashed tokens, absolute expiry, revoke-all-others on password/MFA change |

---

## 14. File Inventory

**Backend (new):**
`raiker/api/routes_auth.py` (register/login/mfa/logout/elevated),
`raiker/api/routes_vault.py` (status/set/clear key),
`raiker/auth/passwords.py` (argon2/scrypt),
`raiker/auth/mfa.py` (TOTP, encrypts seed with app key),
`raiker/auth/accounts.py` (account + login state machine),
`raiker/auth/app_key.py` (auto-generated 0600 internal app key, §8b),
`raiker/auth/vault_key_file.py` (0600 vault key-file boot loader).

**Backend (edit):**
`raiker/storage/migrations.py` (+migration), `raiker/storage/sqlite.py` (accessors),
`raiker/api/sessions.py` (scope, absolute expiry, revoke-others, last_seen),
`raiker/api/auth.py` (scope enforcement), `raiker/api/app.py` (wire routers, boot key-load),
`raiker/api/routes_dashboard.py` (retire unauthenticated mint), `raiker/api/schemas.py`,
`raiker/api/routes_connectors.py` (gallery install/uninstall/search),
task-create path, `pyproject.toml` (+argon2-cffi, +pyotp).

**Frontend (new):** `LoginView.svelte`, `RegisterView.svelte`, `MfaView.svelte`,
`SearchChatView.svelte`, settings section components.
**Frontend (edit):** `nav.ts`, `App.svelte`, `ChatView.svelte`, `TasksView.svelte`,
`ConnectionsView.svelte`, `SettingsView.svelte`, `SessionsView.svelte`, `api.ts`, `apiTypes.ts`,
tests.

---

## 15. Testing

- **pytest** — password hashing params (argon2id 19MiB/2/1; scrypt 2^17/8/1), login state
  machine, `mfa_pending` cannot reach governed routes, lockout after 5, enumeration-resistant
  generic errors, MFA enroll/verify + drift, session absolute-expiry + revoke-others, vault
  fail-closed init abort, vault key-file 0600 + env override, app key auto-gen + 0600,
  **MFA works with no vault configured**, **vault works with MFA disabled**, **opt-in
  require-MFA-for-vault enforced only when enrolled**, per-account isolation
  (account B cannot read account A's connector creds/sessions).
- **`tests/security/`** — explicit A01/A03/A04/A05/A07 acceptance cases.
- **vitest** — login/register/MFA screens, 9-section settings, nav order + renames, New/Search
  Chat, task create+schedule form, connector gallery install/uninstall.
- Full suite + `ruff` + `mypy` green before commit.

---

## 16. Docs to Update (§6)

`README.md`, `docs/guide/*` (auth, settings, connectors, MFA), `docs/threat-models/*`
(new `local-lock-screen.md` + update `connector-ecosystem.md`), `docs/HANDOFF.md`,
`docs/ARCHITECTURE.md`, `SECURITY.md` (§5.1 mapping). Keep the "docs never run ahead of code"
rule: document only what ships real; mark inactive surfaces as such.

---

## 17. Phased Task Order (single plan)

1. Migration + `account_credentials`/`user_settings`/task columns + sqlite accessors.
2. Password hashing module + deps.
3. Login state machine + session scope/absolute-expiry/revoke-others + rate-limit/lockout.
4. `routes_auth.py`; retire unauthenticated mint; wire `AuthMiddleware` scope checks.
5. App key auto-gen loader (§8b) + MFA module + routes.
6. Vault key-file loader + `routes_vault.py` + fail-closed hardening + opt-in "require MFA for Vault" policy.
7. Frontend auth flow (login/register/MFA gate before app shell).
8. Nav rewrite + New Chat / Search Chat.
9. Task create/schedule.
10. Connector gallery.
11. Settings 9-section (hosts vault key, sessions, MFA).
12. Security acceptance tests + full green suite.
13. Docs.
14. Commit + push `origin main`.

---

## 18. Open Risks / Non-Goals

- **Non-goal:** hosted/multi-tenant, off-loopback exposure, TLS termination (deployment concern).
- **Risk:** existing tests assume the unauthenticated mint; they must migrate to the new login.
- **Non-goal:** SMS/Email MFA — removed from scope entirely; possible future iteration.
- **Note:** MFA and Vault are independent; MFA seeds use the internal app key (§8b), so neither
  feature blocks the other. Optional user opt-in can require MFA for vault operations.
- **Connector count:** brief says 23, store has 26; gallery targets the store to stay truthful.
