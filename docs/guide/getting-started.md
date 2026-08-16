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

### Windows PowerShell

The editable package-install step above installs `raiker-app` into the virtual
environment. Activate that environment before running the command:

```powershell
.\.venv\Scripts\Activate.ps1
raiker-app --print-paths
```

If PowerShell reports that `raiker-app` is not recognized, either the virtual
environment is not active or the package was not installed into it. From the
Raiker repository, reinstall it and try again:

```powershell
.\.venv\Scripts\Activate.ps1
python.exe -m pip install -e ".[dev]"
Get-Command raiker-app
raiker-app
```

You can also invoke the installed executable directly without activating the
environment:

```powershell
.\.venv\Scripts\raiker-app.exe
```

If reinstalling reports `WinError 32` for `raiker-app.exe`, a running Raiker
host is holding the Windows entry point open. Stop that instance, reinstall,
and start it again:

```powershell
raiker-app quit --workspace .
python.exe -m pip install -e ".[dev]"
raiker-app --workspace .
```

If the failed reinstall has already made `raiker-app` unavailable, close the
running Raiker process from Task Manager and rerun the `pip install` command.
The `ModuleNotFoundError: No module named 'apps'` message after this failure is
a consequence of the interrupted editable install, not a separate problem.

Build the dashboard once (and again after any UI change):

```bash
npm --prefix apps/web ci
npm --prefix apps/web run build
```

## Run

```bash
raiker-app --workspace .
```

`raiker-app` is the primary application command. It starts Raiker on loopback
and opens the dashboard in your default browser. Passing `--workspace .` keeps
runtime state in `.raiker/` inside the repository. Use the same workspace for
every lifecycle command, including background startup:

```bash
raiker-app --workspace . service install
raiker-app service status --workspace .
raiker-app status --workspace .
```

Run `raiker-app --help` for pause, resume, quit, service, and uninstall
commands.

For explicit server control without the application lifecycle wrapper, use
`raiker-web`:

```bash
raiker-web --workspace . --no-browser
```

It binds `127.0.0.1:8765` by default and serves both the API and the built SPA.
Open <http://127.0.0.1:8765>.

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
| Home | Workbench — the live board: what is running, which agents are standing, what is scheduled, and what needs a decision |
| Work | Chat, Build, Search Chat, Tasks, Projects |
| Knowledge | Memory, Knowledge Map |
| Control | Approvals, Permissions, Models, Extensions |
| Observe | Observability — overview, sessions, activity, checkpoints, diagnostics, live work, notifications |
| Utilities | Settings |

**Sessions is inside Observability**, not a destination of its own: it is the
complete record of every conversation *and* every task run, which is why the
sidebar's RECENT CHATS list stays conversations only. **Models** and
**Extensions** are tabbed the same way — Models by Providers / Routing /
Pricing / Posture, Extensions by Connectors / MCP servers / Skills / Plugins /
Channels. Old links to the pages these absorbed still resolve and open the right
tab.

The top bar carries the notification bell, the theme toggle
(system → light → dark), and the **STOP** switch, which requests cancellation of
every task that is queued, running, paused, or waiting for your approval, at the
next safe boundary. It is governed and audited — not a force-kill.

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer from 640–1023 px, and the full sidebar at 1024 px and wider.
