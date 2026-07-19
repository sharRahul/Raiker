# 1. Install & launch the web app

## Prerequisites

- **Python 3.11+** and **Node 20+** (this guide was verified on Python 3.11 and Node 22).
- `git`, and a POSIX shell or PowerShell.
- No credentials are required to run the app.

## Step 1 — Install Raiker (Python)

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

This exposes the `raiker` and `raiker-web` commands. Verify:

```bash
raiker --help
```

## Step 2 — Build the web dashboard (one time)

The dashboard is a Vite + Svelte SPA. Build it once so `raiker-web` can serve it:

```bash
npm --prefix apps/web install       # first time only
npm --prefix apps/web run build      # produces apps/web/dist
```

A successful build ends with something like `dist/assets/index-*.js … built in Ns`.
If you skip this, `raiker-web` still runs but serves the API only and prints a
build hint.

## Step 3 — Launch

```bash
raiker-web --workspace .            # serves API + dashboard on http://127.0.0.1:8765
```

Open **http://127.0.0.1:8765**. The dashboard is single-user and loopback-only by
default.

### Useful flags

| Flag | Purpose |
|------|---------|
| `--workspace <path>` | Where local runtime state (SQLite, events, vault key file) lives. |
| `--port <n>` | Bind port (default `8765`). |
| `--no-browser` | Don't auto-open a browser tab. |
| `--ui-dir <path>` | Serve a different built dashboard directory. |

### Optional environment variables

These are read from the server process environment only — never hard-code
secrets:

| Variable | Effect |
|----------|--------|
| `RAIKER_CONNECTOR_VAULT_KEY` | A **Fernet** key used to encrypt stored connector/provider credentials. You can also set it in the UI (see [page 9](09-security-vault-and-settings.md)). |
| `RAIKER_MODEL_EGRESS_ALLOWLIST` | Comma-separated hostnames an off-machine model provider is allowed to reach (e.g. `api.anthropic.com`). |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` | Provider keys, if you prefer env-based credentials to the in-app vault. |

## Verify it's up

- `http://127.0.0.1:8765/` returns the dashboard (HTTP 200).
- The lock screen's footer shows a green **System status → Runtime operational**.

> ✅ **Verified:** clean build (198 modules) and launch; the dashboard loads with
> zero browser console errors across every view.

Next: [Create your account & unlock →](02-account-and-login.md)
