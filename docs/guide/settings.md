# Guide — Settings

The **Settings** page (System → Settings) is a per-account, 9-section panel. It is a left rail
of sections; each section is self-contained. Preferences are saved to your account
(`/api/settings`) and isolated from other local accounts.

Honesty rule: a control that the local runtime does not back yet renders a **Not yet active**
note rather than pretending to work.

## Sections

| Section | What you can do | Backed now |
|---|---|---|
| **General** | Language, region, default startup view; governed **Runtime mode** (re-confirmed each change) | Yes |
| **Notification** | In-app popups, desktop alerts | In-app/desktop yes; email delivery not yet active |
| **Personalisation** | Theme (Light/Dark/System), layout spacing, font | Theme yes; spacing/font saved as preferences |
| **Voice** | — | Not yet active (no voice runtime) |
| **Data Controls** | Keep chat & task history | History toggle yes; model-training & export not yet active |
| **Storage** | Live local usage counts, attachment size threshold | Counts + threshold yes; cache clear & cloud metrics not yet active |
| **Security & Login** | Vault Key (masked, status pill, elevated re-auth), MFA enroll, credential lifecycle, bounded local scan/health, opt-in breach check, password reset, active device sessions (revoke) | Yes |
| **Trusted Contact** | Add/remove recovery contacts | Contacts saved; emergency-access automation not yet active |
| **Account** | Display name; **delete account** (elevated, irreversible) | Yes |

## Security & Login highlights

- **Vault Key** — encrypts connector credentials. Status pill shows Active/Valid or
  Missing/Fail-Closed. Saving/clearing requires re-entering your password (and a TOTP code if
  you enabled "require MFA for Vault operations").
- **Password reset** — changing your password signs out all your other devices.
- **Active device sessions** — see and revoke your other sessions; the current device is marked.

### Credential security

Credential status warns at 75 days and becomes overdue at 90. The local scan uses only
configured workspace paths and renders redacted findings. A breach check requires explicit
consent and allowed egress; it sends only a five-character SHA-1 prefix.

## Account deletion

Deleting your account permanently removes its credentials, sessions, settings, and stored
connector credentials. It requires an elevated (re-authenticated) session and cannot be undone.
