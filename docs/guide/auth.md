# Guide — Accounts, Login & MFA

Raiker's web dashboard is protected by a **device-local lock screen**. It supports multiple
local accounts on one machine, each isolated by its own `principal_id`. Raiker stays
single-machine and loopback-only.

## First run

Open the dashboard (`raiker-web`) and choose **Create a new local account**. The first account
becomes the workspace owner. Pick a username and a strong password.

Passwords are hashed with **Argon2id** (19 MiB memory, 2 iterations, 1 lane); if argon2 is
unavailable the runtime falls back to **scrypt** (n=2¹⁷, r=8, p=1). Passwords are never stored
in reversible form.

## Signing in

Enter your username and password. If you have MFA enabled you are then prompted for a 6-digit
code before any part of the app loads — the pre-MFA session cannot reach any governed API.

Failed sign-ins are rate-limited; after 5 consecutive failures the account is temporarily
locked. All failures return the same generic message so usernames cannot be enumerated.

## Multi-factor authentication (TOTP)

Under **Settings → Security & Login**:

1. Click **Enroll in MFA**. Add the shown `otpauth://` URI to an authenticator app
   (Google/Microsoft Authenticator, etc.).
2. Enter the current 6-digit code and click **Activate**.

MFA is fully local (no SMS/email). The TOTP seed is encrypted at rest with an internal app key
that is independent of the connector vault, so MFA works whether or not a vault is configured.

## Connector Vault Key

The **Vault Key** encrypts your stored connector credentials (GitHub, Gmail, … API keys and
OAuth tokens). Under **Settings → Security & Login**:

- The status pill shows **Active / Valid** or **Missing / Fail-Closed Active** (bright red).
- The key field is masked; use **Reveal** to show it.
- Saving or clearing the key requires re-entering your password (elevated re-auth). Optionally
  enable **Require MFA for Vault operations** to also demand a TOTP code.

If the key is missing or invalid, all connectors fail closed — no credential is retrieved and
no outbound connector call is made.

## Sessions

Session tokens are cryptographically random, stored only as hashes, and carry both a sliding
and an absolute expiry. Changing your password or resetting MFA immediately revokes all your
other active sessions on the device.

## Scope note

Connector credentials, per-account settings, and chat/task history are isolated per account:
sessions you create are attributed to your account and another account cannot list or open them.
Legacy/unattributed sessions (e.g. CLI-created) remain shared. See
`docs/threat-models/local-lock-screen.md` for the full model.
