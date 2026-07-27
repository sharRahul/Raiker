# Getting started

## Requirements

- Python 3.11 or newer
- Node 20 or newer (to build the dashboard)
- Git

## Install

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Build the dashboard once (and again after any UI change):

```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```

## Run

```bash
raiker-web --workspace . --no-browser
```

Raiker binds `127.0.0.1:8765` and serves both the API and the built SPA. Open
<http://127.0.0.1:8765>.

Useful flags:

| Flag | Purpose |
|---|---|
| `--workspace PATH` | Where runtime state lives (`.raiker/` inside it). Use a throwaway path to try Raiker without touching a real project. |
| `--port N` | Bind port (default `8765`). |
| `--host H` + `--allow-public` | Reach Raiker from another device. Also requires `RAIKER_OWNER_TOKEN` and turns on transport guardrails. Put TLS in front of it. |
| `--no-browser` | Do not auto-open a browser. |
| `--ui-dir PATH` | Serve a dashboard build from elsewhere. |

There is also a terminal client:

```bash
raiker
```

## First run

The lock screen greets you with **"Hello! I am Raiker."** and a **Create a User
Account** form — username, password, confirm password. This creates the local
**owner principal**; there is no cloud account and nothing leaves the machine.

Two things to know:

- **The session token is held in memory only, never in `localStorage`.** A page
  reload returns you to the lock screen. That is deliberate.
- On a fresh workspace the dashboard shows **"No model is selected yet, so the
  runtime will refuse the turn until you choose one."** That is your next step:
  [Connecting a model](connecting-a-model.md).

## What you get

The sidebar groups every destination:

| Group | Destinations |
|---|---|
| Home | Workbench — resume work, see what needs attention |
| Work | Chat, Build, Search Chat, Tasks, Projects, Sessions |
| Knowledge | Memory, Brain |
| Control | Approvals, Permissions, Models, Extensions |
| Observe | Observability (readiness, audit log, checkpoints, live work, notifications) |
| Utilities | Settings |

The top bar carries the notification bell, the theme toggle
(system → light → dark), and the **STOP** switch, which requests cancellation of
every task that is queued, running, paused, or waiting for your approval, at the
next safe boundary. It is governed and audited — not a force-kill.

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer from 640–1023 px, and the full sidebar at 1024 px and wider.
