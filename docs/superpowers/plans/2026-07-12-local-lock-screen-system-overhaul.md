# Local-Owner Lock Screen & System Overhaul — Implementation Plan

> **Execution status (2026-07-13): COMPLETE.** All 22 tasks in this plan have
> shipped to `main`, including the final Connector Store gallery, task-create/
> stored-scheduling slice, 9-section settings integration, documentation, and
> GitHub CI verification. The unchecked boxes below are the original historical
> execution checklist; current implementation truth lives in
> `docs/IMPLEMENTATION_STATUS.md` and `docs/HANDOFF.md`.

**Goal:** Add a device-local, multi-account lock screen (username/password + optional TOTP MFA) that isolates and protects each account's connector credentials, plus the associated nav/settings/chat/task/gallery UI changes.

**Architecture:** Server-authoritative multi-stage login (password → optional MFA) issuing scoped bearer sessions over the existing loopback FastAPI. Each account maps to one `principal_id`; all per-user data (connector creds, sessions, chats, tasks, settings) already keys on `principal_id`, so isolation is automatic. Two independent encryption keys: an auto-generated internal **app key** for MFA seeds, and the user-managed **vault key** for connector secrets.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, `argon2-cffi` (scrypt fallback), `pyotp`, `cryptography.Fernet`; Vite + Svelte + TypeScript SPA (vitest); pytest + ruff + mypy.

## Global Constraints

- Loopback-only (`127.0.0.1`); no hosted/multi-tenant behavior. Verbatim from spec §1.
- Password hash: **Argon2id** `memory_cost=19456` KiB, `time_cost=2`, `parallelism=1`. Fallback **scrypt** `n=2**17`, `r=8`, `p=1`. Verbatim from spec §5.
- MFA: **TOTP only.** No SMS/Email anywhere (no channel, no stub). Verbatim from spec §6.
- MFA seed encrypted with the internal **app key** (`<workspace>/.raiker/app.key`, `0600`), never the vault key. Spec §8b.
- Vault key file `<workspace>/.raiker/vault.key` (`0600`); env `RAIKER_CONNECTOR_VAULT_KEY` overrides. Spec §8.
- Auth errors are a single generic string; no username enumeration; parameterized SQL only. Spec §13 (A03/A05).
- Honesty rule: no toggle claims behavior it lacks; unbacked settings render "not yet active / fails closed." Spec §H/§12.
- All migrations additive; `ALTER TABLE ADD COLUMN` wrapped in `contextlib.suppress(sqlite3.OperationalError)`. Existing pattern `sqlite.py:_apply_migration`.
- `ruff` + `mypy` + full `pytest` + `vitest` green before the final commit.

---

## File Structure

**New backend**
- `raiker/auth/__init__.py` — package marker.
- `raiker/auth/passwords.py` — Argon2id/scrypt hash + verify + needs-rehash.
- `raiker/auth/app_key.py` — auto-gen `0600` internal app key loader + Fernet accessor.
- `raiker/auth/vault_key_file.py` — vault key-file read/write/clear + boot loader into env.
- `raiker/auth/mfa.py` — TOTP secret gen, provisioning URI, verify, backup codes.
- `raiker/auth/accounts.py` — account create/get, login state machine, lockout, elevated grants.
- `raiker/api/routes_auth.py` — register/login/mfa/logout/elevated endpoints.
- `raiker/api/routes_vault.py` — vault key status/set/clear + require-MFA-for-vault policy.

**Modified backend**
- `raiker/storage/migrations.py` — new migration constants.
- `raiker/storage/sqlite.py` — register migration; account/settings/task/trusted-contact accessors.
- `raiker/api/sessions.py` — scope, absolute expiry, `revoke_others_for_principal`, `touch`.
- `raiker/api/auth.py` — scope enforcement in `AuthMiddleware`.
- `raiker/api/app.py` — wire new routers; boot key loaders.
- `raiker/api/routes_dashboard.py` — retire unauthenticated owner mint.
- `raiker/api/schemas.py` — new request/response DTOs.
- `raiker/api/routes_connectors.py` — gallery install/uninstall/search.
- `raiker/api/routes_dashboard.py` (tasks) or new `routes_tasks.py` — task create/schedule.
- `pyproject.toml` — `argon2-cffi`, `pyotp` deps.

**Frontend** (`apps/web/src`)
- New: `lib/views/LoginView.svelte`, `RegisterView.svelte`, `MfaView.svelte`, `SearchChatView.svelte`, `lib/views/settings/*` section components, `lib/auth.ts` (session store/guard).
- Modified: `lib/nav.ts`, `App.svelte`, `lib/views/ChatView.svelte`, `TasksView.svelte`, `ConnectionsView.svelte`, `SettingsView.svelte`, `SessionsView.svelte`, `lib/api.ts`, `lib/apiTypes.ts`, tests.

**Docs**
- `README.md`, `docs/guide/auth.md`, `docs/guide/mfa.md`, `docs/guide/settings.md`, `docs/threat-models/local-lock-screen.md`, `docs/HANDOFF.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`.

---

## PHASE 1 — Schema & Storage

### Task 1: Migration constants + registration

**Files:**
- Modify: `raiker/storage/migrations.py` (append constants)
- Modify: `raiker/storage/sqlite.py` (import + `_apply_migration` call + `ALTER` guards)
- Test: `tests/storage/test_lock_screen_migration.py`

**Interfaces:**
- Produces: tables `account_credentials`, `user_settings`, `trusted_contacts`; columns on `api_sessions` (`scope`,`absolute_expires_at`,`last_seen_at`,`device_label`) and `tasks` (`priority`,`scheduled_at`,`recurrence`,`reminder_at`). Migration id `LOCK_SCREEN_MIGRATION_ID = "RAIKER-6001-local-lock-screen"`.

- [ ] **Step 1: Write failing test**
```python
# tests/storage/test_lock_screen_migration.py
from raiker.storage.sqlite import SQLiteStore

def test_lock_screen_tables_and_columns(tmp_path):
    store = SQLiteStore(tmp_path)
    with store.connect() as c:
        c.execute("SELECT username, password_hash, hash_algo, failed_attempts, locked_until, "
                  "mfa_enrolled, mfa_secret_encrypted, backup_codes_hashed FROM account_credentials")
        c.execute("SELECT principal_id, settings_json FROM user_settings")
        c.execute("SELECT contact_id, principal_id, name, method, value FROM trusted_contacts")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(api_sessions)")}
        assert {"scope", "absolute_expires_at", "last_seen_at", "device_label"} <= cols
        tcols = {r["name"] for r in c.execute("PRAGMA table_info(tasks)")}
        assert {"priority", "scheduled_at", "recurrence", "reminder_at"} <= tcols
```
- [ ] **Step 2: Run — expect FAIL** `pytest tests/storage/test_lock_screen_migration.py -v` → "no such table/column".
- [ ] **Step 3: Implement** — add to `migrations.py`:
```python
LOCK_SCREEN_MIGRATION_ID = "RAIKER-6001-local-lock-screen"
LOCK_SCREEN_SQL = """
CREATE TABLE IF NOT EXISTS account_credentials (
  principal_id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  hash_algo TEXT NOT NULL,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  mfa_enrolled INTEGER NOT NULL DEFAULT 0,
  mfa_secret_encrypted BLOB,
  backup_codes_hashed TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_settings (
  principal_id TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trusted_contacts (
  contact_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  method TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_username ON account_credentials(username);
CREATE INDEX IF NOT EXISTS idx_trusted_contacts_principal ON trusted_contacts(principal_id);
"""
```
In `sqlite.py` import both, then after the connector-invocations apply call add:
```python
self._apply_migration(LOCK_SCREEN_MIGRATION_ID, LOCK_SCREEN_SQL, connection)
for _col, _sql in (
    ("scope", "ALTER TABLE api_sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'control'"),
    ("absolute_expires_at", "ALTER TABLE api_sessions ADD COLUMN absolute_expires_at TEXT"),
    ("last_seen_at", "ALTER TABLE api_sessions ADD COLUMN last_seen_at TEXT"),
    ("device_label", "ALTER TABLE api_sessions ADD COLUMN device_label TEXT"),
    ("priority", "ALTER TABLE tasks ADD COLUMN priority TEXT"),
    ("scheduled_at", "ALTER TABLE tasks ADD COLUMN scheduled_at TEXT"),
    ("recurrence", "ALTER TABLE tasks ADD COLUMN recurrence TEXT"),
    ("reminder_at", "ALTER TABLE tasks ADD COLUMN reminder_at TEXT"),
):
    with contextlib.suppress(sqlite3.OperationalError):
        connection.execute(_sql)
```
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** `feat(storage): add lock-screen accounts/settings schema`.

### Task 2: SQLite accessors for accounts & settings

**Files:** Modify `raiker/storage/sqlite.py`; Test `tests/storage/test_account_store.py`.

**Interfaces — Produces (exact signatures):**
```python
def upsert_account(self, principal_id, username, password_hash, hash_algo, created_at, updated_at) -> None
def get_account_by_username(self, username) -> dict | None
def get_account(self, principal_id) -> dict | None
def set_account_failed(self, principal_id, failed_attempts, locked_until) -> None
def set_account_mfa(self, principal_id, enrolled, secret_encrypted, backup_codes_hashed) -> None
def set_account_password(self, principal_id, password_hash, hash_algo, updated_at) -> None
def delete_account(self, principal_id) -> None
def get_user_settings(self, principal_id) -> dict | None
def put_user_settings(self, principal_id, settings_json, updated_at) -> None
```

- [ ] **Step 1: Failing test** covering upsert→get_by_username→get, failed-attempt set, mfa set, password set, settings roundtrip, delete. Assert parameterized (no f-string SQL).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** the accessors with `?`-parameterized queries mirroring existing store methods.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(storage): account + settings accessors`.

---

## PHASE 2 — Crypto & Keys

### Task 3: Password hashing (`raiker/auth/passwords.py`)

**Files:** Create `raiker/auth/passwords.py`, `raiker/auth/__init__.py`; Modify `pyproject.toml`; Test `tests/auth/test_passwords.py`.

**Interfaces — Produces:**
```python
def hash_password(password: str) -> tuple[str, str]   # (encoded_hash, algo) algo in {"argon2id","scrypt"}
def verify_password(password: str, encoded: str, algo: str) -> bool
def needs_rehash(encoded: str, algo: str) -> bool
ARGON2_AVAILABLE: bool
```

- [ ] **Step 1: Failing tests** — argon2id path when available: hash→verify True, wrong pw→False, params (memory 19456, time 2, parallelism 1) present in encoded string; scrypt path (force via monkeypatch `ARGON2_AVAILABLE=False`): encoded starts `scrypt$131072$8$1$`, verify True/False; constant-work verify on absent user (verify against dummy returns False without raising).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement:**
```python
from __future__ import annotations
import base64, hashlib, hmac, secrets
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    _PH = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
    ARGON2_AVAILABLE = True
except Exception:
    ARGON2_AVAILABLE = False
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**17, 8, 1

def _scrypt_hash(password: str, salt: bytes) -> str:
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"

def hash_password(password: str) -> tuple[str, str]:
    if ARGON2_AVAILABLE:
        return _PH.hash(password), "argon2id"
    return _scrypt_hash(password, secrets.token_bytes(16)), "scrypt"

def verify_password(password: str, encoded: str, algo: str) -> bool:
    if algo == "argon2id" and ARGON2_AVAILABLE:
        try:
            return _PH.verify(encoded, password)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False
    if algo == "scrypt" or encoded.startswith("scrypt$"):
        try:
            _, n, r, p, salt_b64, hash_b64 = encoded.split("$")
            dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64),
                                n=int(n), r=int(r), p=int(p), dklen=32)
            return hmac.compare_digest(dk, base64.b64decode(hash_b64))
        except Exception:
            return False
    return False

def needs_rehash(encoded: str, algo: str) -> bool:
    return ARGON2_AVAILABLE and algo != "argon2id"
```
Add to `pyproject.toml` dependencies: `argon2-cffi>=23.1`, `pyotp>=2.9`.
- [ ] **Step 4: Run — PASS** (run once with argon2 installed, once monkeypatched to scrypt).
- [ ] **Step 5: Commit** `feat(auth): password hashing (argon2id + scrypt fallback)`.

### Task 4: Internal app key (`raiker/auth/app_key.py`)

**Files:** Create `raiker/auth/app_key.py`; Test `tests/auth/test_app_key.py`.

**Interfaces — Produces:**
```python
def app_key_path(workspace_root) -> Path
def ensure_app_key(workspace_root) -> bytes        # generates 0600 file if absent
def app_fernet(workspace_root) -> Fernet
```

- [ ] **Step 1: Failing test** — first call creates `.raiker/app.key`; file mode `0o600` (POSIX; on Windows assert file exists — skip mode check via `os.name`); second call returns same key; `app_fernet` round-trips encrypt/decrypt.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** using `Fernet.generate_key()`, write bytes, `os.chmod(path, 0o600)` guarded by `if os.name == "posix"`.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(auth): internal app key for MFA-seed encryption`.

### Task 5: Vault key file loader (`raiker/auth/vault_key_file.py`)

**Files:** Create `raiker/auth/vault_key_file.py`; Test `tests/auth/test_vault_key_file.py`.

**Interfaces — Produces:**
```python
def vault_key_path(workspace_root) -> Path
def read_vault_key(workspace_root) -> str | None
def write_vault_key(workspace_root, key: str) -> None     # validates Fernet, 0600
def clear_vault_key(workspace_root) -> None
def load_vault_key_into_env(workspace_root) -> None        # only if env unset and file valid
def vault_status(workspace_root) -> str                    # configured_valid|missing|invalid
```

- [ ] **Step 1: Failing tests** — write→read roundtrip; write rejects non-Fernet key (`ValueError`); `load_vault_key_into_env` sets `RAIKER_CONNECTOR_VAULT_KEY` from file when env unset; env value wins when set; `vault_status` returns each of the three states; clear removes file.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** — validate with `Fernet(key.encode("ascii"))`, `0600` on posix. `load_vault_key_into_env`: `if not os.environ.get("RAIKER_CONNECTOR_VAULT_KEY"): if valid file: os.environ[...] = key`.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(auth): vault key-file store + boot loader`.

### Task 6: MFA TOTP (`raiker/auth/mfa.py`)

**Files:** Create `raiker/auth/mfa.py`; Test `tests/auth/test_mfa.py`.

**Interfaces — Produces:**
```python
def generate_secret() -> str
def provisioning_uri(secret: str, username: str, issuer="Raiker") -> str
def verify_totp(secret: str, code: str, valid_window=1) -> bool
def encrypt_secret(workspace_root, secret: str) -> bytes    # uses app_fernet
def decrypt_secret(workspace_root, blob: bytes) -> str
def generate_backup_codes(n=10) -> list[str]
def hash_backup_codes(codes: list[str]) -> str              # JSON of sha256 hashes
def consume_backup_code(hashed_json: str, code: str) -> tuple[bool, str]  # (ok, new_json)
```

- [ ] **Step 1: Failing tests** — `verify_totp` accepts `pyotp.TOTP(secret).now()`, rejects "000000" (statistically); encrypt→decrypt roundtrip via app key (independent of vault); backup code hash+consume removes used code; MFA path never touches `RAIKER_CONNECTOR_VAULT_KEY` (assert env unset during test still works).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** with `pyotp`; secrets via `pyotp.random_base32()`; backup codes `secrets.token_hex(4)`, hashed with sha256.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(auth): TOTP MFA (app-key encrypted seed)`.

---

## PHASE 3 — Sessions & Login State Machine

### Task 7: Session store scope + expiry + revoke-others

**Files:** Modify `raiker/api/sessions.py`, `raiker/api/auth.py`; Test `tests/api/test_session_scope.py`.

**Interfaces — Produces:**
- `create_session(principal_id, scopes, scope="control", expires_in_seconds=..., absolute_expires_in_seconds=..., device_label=None)` — extend existing; store `scope`, `absolute_expires_at`, `device_label`.
- `revoke_others_for_principal(principal_id, keep_session_id) -> int`
- `touch(session_id, when)` — update `last_seen_at`.
- `ApiSession` gains `scope: str`, `absolute_expires_at: str | None`; `is_expired` also true past absolute.
- `AuthMiddleware.authenticate(request, required_scope="control")` — reject when session scope != required (403 `scope_insufficient`), reject absolute-expired.

- [ ] **Step 1: Failing tests** — mfa_pending session rejected on a control route; revoke-others invalidates sibling sessions but keeps current; absolute expiry rejects even when sliding not elapsed; `touch` updates last_seen.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** — extend `_deserialize`, `create_session`, add methods; extend `is_expired`; add scope check + absolute check in `AuthMiddleware`. Keep default `required_scope="control"` so existing routes stay guarded.
- [ ] **Step 4: Run — PASS** + full `tests/api` regression.
- [ ] **Step 5: Commit** `feat(api): scoped sessions, absolute expiry, revoke-others`.

### Task 8: Account service + login state machine (`raiker/auth/accounts.py`)

**Files:** Create `raiker/auth/accounts.py`; Test `tests/auth/test_accounts.py`.

**Interfaces — Produces:**
```python
class AccountService:
    def __init__(self, workspace_root): ...
    def register(self, username, password) -> str            # returns principal_id; provisions Principal
    def login(self, username, password, device_label=None) -> LoginResult
    def verify_mfa(self, ticket_token, code) -> LoginResult
    def change_password(self, principal_id, old, new) -> None # revokes other sessions
    def grant_elevated(self, principal_id, password=None, mfa_code=None) -> str  # elevated token
# LoginResult: dataclass(stage: 'session'|'mfa_required', token: str|None, ticket: str|None, principal_id)
LOCKOUT_THRESHOLD = 5
GENERIC_AUTH_ERROR = "Invalid username or password"
```

- [ ] **Step 1: Failing tests** — register then login (no MFA) → stage session; wrong password → raises `AuthError(GENERIC_AUTH_ERROR)`; unknown user → same generic error + still runs a verify (timing); 5 failures → locked (`locked_until` future), 6th blocked even with right password; MFA-enrolled login → stage mfa_required + ticket that cannot hit control routes; `verify_mfa` good code → session; change_password revokes others; register maps to a distinct principal_id per username (isolation).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** the state machine over `AccountService` using Tasks 2/3/6/7, provisioning a Principal via existing store principal creation. Progressive delay = clamp; lock after threshold.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(auth): login state machine with lockout + MFA gate`.

---

## PHASE 4 — API Routes

### Task 9: Auth routes (`raiker/api/routes_auth.py`)

**Files:** Create `raiker/api/routes_auth.py`; Modify `raiker/api/schemas.py`, `raiker/api/app.py`, `raiker/api/routes_dashboard.py` (retire unauthenticated mint); Test `tests/api/test_routes_auth.py`.

**Interfaces — Produces endpoints:**
`POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/mfa/verify`, `POST /api/auth/mfa/enroll` (elevated-or-authenticated), `POST /api/auth/logout`, `POST /api/auth/elevate`.

- [ ] **Step 1: Failing tests** (FastAPI `TestClient`) — register→login returns bearer; bearer reaches `/api/sessions`; **mfa_pending ticket rejected** on `/api/sessions` (A01/A07); bad login → 401 generic body; lockout after 5; enroll+verify+login-with-code full loop; logout revokes; old unauthenticated `POST /api/auth/session` removed (404/410) or now requires credentials.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** routes delegating to `AccountService`; add DTOs to `schemas.py`; include router in `app.py`; delete/replace `mint_session` in `routes_dashboard.py`.
- [ ] **Step 4: Run — PASS** + `tests/api` regression (migrate any test using the old mint).
- [ ] **Step 5: Commit** `feat(api): auth routes (login/mfa/register/logout/elevate)`.

### Task 10: Vault routes (`raiker/api/routes_vault.py`)

**Files:** Create `raiker/api/routes_vault.py`; Modify `app.py`, `schemas.py`; Test `tests/api/test_routes_vault.py`.

**Interfaces — Produces:** `GET /api/vault/status`, `PUT /api/vault/key` (elevated), `DELETE /api/vault/key` (elevated). Response `{state: configured_valid|missing|invalid}`. When account has opted into "require MFA for Vault" and is MFA-enrolled, set/clear additionally require a fresh MFA code in the elevated grant.

- [ ] **Step 1: Failing tests** — status reflects missing/valid/invalid; PUT without elevated → 403; PUT with elevated writes key-file + status flips to configured_valid; DELETE clears; opt-in-MFA account must supply MFA to elevate.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** over `vault_key_file` + `AccountService.grant_elevated`; read policy from `user_settings`.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(api): vault key status/set/clear with elevated re-auth`.

### Task 11: Settings, tasks, connector-gallery, search routes

**Files:** Modify `raiker/api/routes_dashboard.py` (or new `routes_settings.py`, `routes_tasks.py`), `routes_connectors.py`, `schemas.py`; Tests `tests/api/test_settings_routes.py`, `test_task_schedule_routes.py`, `test_connector_gallery.py`, `test_chat_search.py`.

**Interfaces — Produces:**
- `GET/PUT /api/settings` (per-principal `user_settings` blob).
- `POST /api/tasks` (title, description, priority, scheduled_at, recurrence, reminder_at) via governed task path; `GET /api/tasks`.
- `GET /api/connectors/catalog` (all in store), `POST /api/connectors/{id}/install`, `DELETE /api/connectors/{id}/install` (per principal).
- `GET /api/sessions/search?q=&category=` over existing sessions/turns.

- [ ] **Step 1: Failing tests** — settings roundtrip is per-principal (account B can't read A's); task create persists schedule fields + is principal-scoped; catalog returns full store count; install/uninstall toggles `connector_installations`; search filters by q. All require a valid session; account isolation asserted.
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement** routes with `Depends(_auth)`; use accessors from Task 2 and existing connector installation store.
- [ ] **Step 4: Run — PASS.**
- [ ] **Step 5: Commit** `feat(api): settings, task-schedule, connector gallery, chat search`.

---

## PHASE 5 — Frontend

### Task 12: Session store + API client (`lib/auth.ts`, `lib/api.ts`, `lib/apiTypes.ts`)

**Files:** Create `apps/web/src/lib/auth.ts`; Modify `lib/api.ts`, `lib/apiTypes.ts`; Test `apps/web/src/lib/auth.test.ts`.

**Interfaces — Produces:** a Svelte store holding `{token, principalId, stage}`; `login`, `verifyMfa`, `register`, `logout`, `elevate` API calls; token attached as `Authorization: Bearer` to all `/api` fetches; 401 clears session → routes to login.

- [ ] **Step 1: Failing vitest** — login sets token; fetch wrapper adds bearer; 401 clears store.
- [ ] **Step 2–4:** implement, run PASS.
- [ ] **Step 5: Commit** `feat(web): auth session store + bearer client`.

### Task 13: Login / Register / MFA screens + app gate

**Files:** Create `LoginView.svelte`, `RegisterView.svelte`, `MfaView.svelte`; Modify `App.svelte`; Tests alongside.

**Interfaces — Consumes:** `lib/auth.ts`. App shell renders login gate when no `control` session; MFA screen when stage is `mfa_required`; only mounts the nav/app once authenticated.

- [ ] **Step 1: Failing vitest** — unauthenticated renders Login not nav; successful login shows app; mfa_required renders MFA screen and blocks app until verified.
- [ ] **Step 2–4:** implement, run PASS.
- [ ] **Step 5: Commit** `feat(web): login/register/MFA gate`.

### Task 14: Nav rewrite (`lib/nav.ts`)

**Files:** Modify `lib/nav.ts`, `App.svelte`; Tests `App.test.ts`, `a11y.test.ts`.

- [ ] **Step 1: Failing test** asserting group labels `The Hustle`, `Steering`, `System`; The Hustle order `new-chat, search-chat, tasks, approvals, projects`; System contains `sessions, activity, diagnostics, settings`; `DEFAULT_ROUTE === "new-chat"`.
- [ ] **Step 2–4:** implement group/label/order/id changes + new routes; run PASS.
- [ ] **Step 5: Commit** `feat(web): rename + reorder navigation`.

### Task 15: New Chat + Search Chat

**Files:** Modify `ChatView.svelte` (empty default, route `new-chat`); Create `SearchChatView.svelte`; wire in `App.svelte`; Tests.

- [ ] **Step 1: Failing vitest** — new-chat opens empty session; search-chat lists/searches history from `/api/sessions/search`.
- [ ] **Step 2–4:** implement, run PASS.
- [ ] **Step 5: Commit** `feat(web): New Chat empty state + Search Chat history`.

### Task 16: Task create/schedule form

**Files:** Modify `TasksView.svelte`; Test `TasksView.test.ts`.

- [ ] **Step 1: Failing vitest** — form submits title/description/priority + date-time → `POST /api/tasks`; only fields that drive runtime are labeled active, stored-only fields labeled as such (honesty).
- [ ] **Step 2–4:** implement, run PASS.
- [ ] **Step 5: Commit** `feat(web): task create + schedule form`.

### Task 17: Connector gallery

**Files:** Modify `ConnectionsView.svelte`; Test `ConnectionsView.test.ts`.

- [ ] **Step 1: Failing vitest** — gallery lists full catalog, search filters, install/uninstall calls endpoints and reflects state; write actions surface a confirmation.
- [ ] **Step 2–4:** implement, run PASS.
- [ ] **Step 5: Commit** `feat(web): connector gallery (browse/search/install/uninstall)`.

### Task 18: Settings 9-section overhaul

**Files:** Rewrite `SettingsView.svelte`; Create `lib/views/settings/*` (General, Notification, Personalisation, Voice, DataControls, Storage, SecurityLogin, TrustedContact, Account); Modify `SessionsView.svelte` reuse; Tests.

**Interfaces — Consumes:** `/api/settings`, `/api/vault/*`, `/api/auth/mfa/*`, session list/revoke.

- [ ] **Step 1: Failing vitest** — nav exposes all 9 sections; backed controls persist via `/api/settings`; unbacked controls (Voice devices, model-training, cloud metrics) render a visible "not yet active / fails closed" state (no fake success); Security&Login shows masked Vault Key field + Reveal toggle + red/green pill from `/api/vault/status`, MFA enroll, active sessions with revoke, and the opt-in "require MFA for Vault" toggle; Account delete triggers re-auth confirmation.
- [ ] **Step 2–4:** implement section components, run PASS.
- [ ] **Step 5: Commit** `feat(web): 9-section settings incl. vault key + MFA + sessions`.

---

## PHASE 6 — Security Acceptance, Suite, Docs

### Task 19: Security acceptance tests (`tests/security/`)

**Files:** Create `tests/security/test_owasp_acceptance.py`.

- [ ] **Step 1: Write tests** mapping each criterion:
  - A01/A07: mfa_pending ticket + manipulated params cannot reach any governed route; post-password-change all other sessions dead.
  - A03: representative injection strings in username/password do not break out (parameterized).
  - A04: lockout after 5.
  - A05: identical generic error for unknown-user vs bad-password.
  - A07: session token is CSPRNG length, absolute expiry enforced.
  - Independence: MFA works with vault unset; vault works with MFA off; opt-in require-MFA-for-vault enforced only when enrolled.
- [ ] **Step 2: Run — some FAIL if any gap → fix source.**
- [ ] **Step 3: Run — PASS.**
- [ ] **Step 4: Commit** `test(security): OWASP A01–A07 acceptance`.

### Task 20: Green suite gate

- [ ] `ruff check .` → clean (fix inline).
- [ ] `mypy raiker` → clean.
- [ ] `pytest` → all pass.
- [ ] `cd apps/web && npm run test` (vitest) → all pass; `npm run build` → succeeds.
- [ ] Commit any lint/type fixups `chore: lint/type/test green`.

### Task 21: Docs

**Files:** `README.md`, `docs/guide/auth.md`, `docs/guide/mfa.md`, `docs/guide/settings.md`, `docs/threat-models/local-lock-screen.md`, `docs/HANDOFF.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`.

- [ ] Document login/MFA/vault/app-key model, 9-section settings, nav changes, per-account isolation, the OWASP mapping, and the honesty stance (mark inactive surfaces). Only document what shipped real.
- [ ] Commit `docs: local lock screen, MFA, vault, settings, threat model`.

### Task 22: Final integration + push

- [ ] Re-run full `pytest` + `vitest` + `ruff` + `mypy` + web build — confirm green (paste output).
- [ ] `git add -A && git commit` (include spec + plan) then `git push origin main`.

---

## Self-Review Notes

- **Spec coverage:** Epic 1 → Tasks 3,6,7,8,9,17,19. Epic 2 → 1,11,15,16. Epic 3 → 4,5,10,18. Epic 4 → 14. Settings §4.1 → 18. Acceptance §5 → 11,17,18. Security §5.1 → 7,8,9,19. Docs §6 → 21.
- **Independence (MFA⟂Vault):** enforced by app key (Task 4) + tests in 6/8/19.
- **Honesty:** Task 16/18 explicitly test that unbacked controls show inactive state.
- **No SMS/Email:** absent from every task.
