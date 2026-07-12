# Threat Model — Local-Owner Lock Screen

Status: implemented (backend + login/MFA/vault UI). See the design at
`docs/superpowers/specs/2026-07-12-local-lock-screen-system-overhaul-design.md`.

## Purpose & scope

The lock screen is a **device-local, multi-account** gate whose job is to protect each
account's connector credentials (API keys, OAuth tokens) and to keep one local user's data
isolated from another's. Raiker remains **single-machine, loopback-only** (`127.0.0.1`); this
is not a hosted or multi-tenant service.

"Multi-user" means two or more local profiles on one device (user 1, user 2, …), each mapped
to its own `principal_id` and fully isolated for the surfaces that key on the principal.

## Assets

| Asset | Storage | Protection |
|---|---|---|
| Account password | `account_credentials.password_hash` | Argon2id (19 MiB / t=2 / p=1); scrypt fallback (n=2¹⁷ / r=8 / p=1). One-way, never returned. |
| Connector credentials | `connector_credentials` (per principal) | Fernet-encrypted with the **vault key**. |
| MFA TOTP seed | `account_credentials.mfa_secret_encrypted` | Fernet-encrypted with the **internal app key** (auto-generated `0600` file), independent of the vault. |
| Vault master key | `<workspace>/.raiker/vault.key` (`0600`) | Filesystem perms + loopback + elevated re-auth to change; env var overrides. |
| Session tokens | `api_sessions` | CSPRNG (`secrets.token_hex(32)`), SHA-256 at rest, sliding + absolute expiry, revocable. |

## Login state machine (server-authoritative)

```
login(username, password)
  → bad password / unknown user → 401 "Invalid username or password"   (generic; no enumeration)
  → ok, no MFA → control session
  → ok, MFA on → mfa_pending ticket (cannot reach governed /api)
mfa/verify(ticket, code) → control session
```

A `mfa_pending` session **cannot** reach any governed route — `AuthMiddleware` requires the
`control` (or `elevated`) scope. This is enforced server-side, so URL/token/parameter
manipulation cannot bypass the MFA stage.

## OWASP mapping (spec §5.1)

| Criterion | Control | Test |
|---|---|---|
| A01 / A07 — access control / MFA bypass (CWE-287) | Scoped sessions; `mfa_pending` blocked from governed routes | `tests/test_owasp_acceptance.py::test_a01_*` |
| A02 — crypto at rest (CWE-311) | Argon2id password hash; MFA seed (app key) + connector creds (vault key) Fernet-encrypted. Loopback origin; TLS is a deployment concern. | `tests/test_passwords.py`, `tests/test_mfa.py` |
| A03 — injection (CWE-89) | Parameterized SQLite everywhere | `tests/test_owasp_acceptance.py::test_a03_*` |
| A04 — brute force (CWE-307) | Per-account failed-attempt counter, lock after 5 | `test_a04_lockout_after_five` |
| A05 — enumeration (CWE-209) | Single generic error; dummy-verify on missing user | `test_a05_generic_error_no_enumeration` |
| A07 — session (CWE-613) | CSPRNG + hashed tokens, absolute expiry, revoke-others on password/MFA change | `test_a07_password_change_revokes_other_sessions` |

## MFA ⟂ Vault independence

MFA and the connector vault are **independent** user choices. MFA seeds use the internal app
key (always present), so MFA works with no vault configured, and the vault works with MFA off.
An opt-in policy (`security.require_mfa_for_vault`, in Security & Login settings) additionally
requires a fresh TOTP code for vault-key changes when the user has MFA enrolled.

## Fail-closed

If the vault key is missing, corrupted, or unreadable, connector credential retrieval and
outbound connector routing fail closed (`raiker/runtime/connector_ecosystem.py`). The Security
& Login settings pill shows **Missing / Fail-Closed Active** in that state.

## Known limitations (honest scope)

- **Chat/task isolation:** connector credentials and per-account settings are isolated per
  `principal_id`. Sessions/turns/tasks are **not yet** principal-scoped at the storage layer, so
  full cross-account isolation of chat history and tasks is a follow-up (schema + query change).
- **First-run bootstrap:** before any account is registered, the loopback owner-bootstrap mint
  is available; it fails closed once the first account exists.
- **TLS:** not terminated by the app (loopback only). Networked exposure is out of scope.
- **SMS/Email MFA:** intentionally out of scope. TOTP only.
