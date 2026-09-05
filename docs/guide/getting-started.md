# Getting started

## Requirements

- Python 3.11 or newer
- Node 20 or newer (to build the dashboard)
- Git

**Check the Python version before anything else**, and check it *inside* the
virtual environment rather than before creating it — `python` is whatever name
resolution last decided it is, and on Windows that is often not the version you
installed most recently:

```bash
python --version
```

Raiker currently runs from a source checkout; no signed desktop release has
been published. The dashboard and terminal client support local single-user
operation. Hosted multi-user, dedicated mobile, and IDE clients are not part of
the current release.

## Install

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

#### If the install downloads the same package over and over

```text
Downloading ruff-0.6.3-py3-none-win_amd64.whl (8.8 MB)
Downloading ruff-0.6.2-py3-none-win_amd64.whl (8.8 MB)
INFO: pip is looking at multiple versions of pyyaml…
```

You are on the wrong Python. Raiker needs 3.11; `cp310` in a wheel name is
CPython 3.10. Old pip resolves every dependency before it checks the project's
required Python, so on 3.10 it searches for a set that cannot exist.

Fix it by creating the environment with a 3.11+ interpreter — `py -3.11 -m venv
.venv` on Windows, `python3.11 -m venv .venv` elsewhere — and upgrading pip
before installing. Current Raiker also stops the install itself, in about a
second, with a message naming the version it found.

With [uv](https://github.com/astral-sh/uv) the question does not arise:

```bash
uv sync --extra dev
```

The following platform sections spell out the same source install with the
correct shell and package manager. Raiker does not currently publish a signed
download, Homebrew formula, or Linux repository.

### Linux

For Debian or Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
```

For Fedora, install the equivalent prerequisites:

```bash
sudo dnf install python3 python3-pip git
```

Confirm that `python3 --version` is 3.11 or newer and `node --version` is 20 or
newer. Stable distributions may ship an older Node.js; use NodeSource, `nvm`,
or another trusted versioned source rather than continuing with an unsupported
runtime. Then install and build Raiker:

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm --prefix apps/web ci
npm --prefix apps/web run build
raiker-app --print-paths
raiker-app
```

The dashboard opens from a loopback host. Without `--workspace`, Linux instance
data uses `$XDG_DATA_HOME/raiker` or the platform user-data default. To start the
same instance at sign-in:

```bash
raiker-app service install
raiker-app service status
```

This installs a `systemd --user` registration, not a privileged system service.
Keep the checkout and `.venv` at the registered paths, or uninstall and
reinstall the service after moving them.

### macOS

With Homebrew:

```bash
brew install python@3.11 node@20 git
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
$(brew --prefix python@3.11)/bin/python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
export PATH="$(brew --prefix node@20)/bin:$PATH"
npm --prefix apps/web ci
npm --prefix apps/web run build
raiker-app --print-paths
raiker-app
```

The default instance data is under `~/Library/Application Support/Raiker`.
Automatic sign-in startup uses a user LaunchAgent:

```bash
raiker-app service install
raiker-app service status
```

Source checkout execution does not require opening an installer. The release
tool can generate a `.pkg`, but local artifacts are unsigned. macOS Gatekeeper
may refuse an unsigned package or app bundle; do not bypass that warning for an
artifact you did not build or verify yourself. No notarized Raiker release is
claimed until the release channel says so.

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
python.exe -m pip install --upgrade pip
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
raiker-app
```

`raiker-app` is the primary application command. It starts Raiker on loopback
and opens the dashboard in your default browser. By default it uses the normal
application-data directory for your platform. Passing `--workspace .` instead
keeps runtime state in `.raiker/` inside the repository. Use the same workspace
for every lifecycle command, including background startup:

```bash
raiker-app --workspace . service install
raiker-app service status --workspace .
raiker-app status --workspace .
```

To open Raiker from your applications menu instead of a terminal:

```bash
raiker-app desktop install
```

That adds a launcher — an entry in the applications menu on Linux, the Start
Menu on Windows, `~/Applications` on macOS — which starts Raiker if it is not
running and opens the dashboard. Everything is written under your own home
directory. `raiker-app desktop uninstall` removes it.

Once Raiker is running it also has a system-tray icon: status, Open Raiker,
Pause or Resume, Restart, Quit.

Run `raiker-app --help` for pause, resume, quit, service, desktop, update, and
uninstall commands. [Managing the Raiker host](managing-the-host.md) explains
what each command changes, where instance data lives, and how to keep or export
it.

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
| Work | Chat, Build, Threads, Tasks, Projects |
| Knowledge | Memory, Knowledge Map |
| Control | Approvals, Permissions, Models, Extensions |
| Observe | Observability — overview, sessions, activity, checkpoints, diagnostics, live work, notifications |
| Utilities | Guide, Settings |

**Sessions is inside Observability**, not a destination of its own: it is the
complete record of every conversation *and* every task run, which is why the
sidebar's RECENT CHATS list stays conversations only. **Models** and
**Extensions** are tabbed the same way — Models by Local / Hosted / Hugging
Face / Activity / Routing / Pricing, Extensions by Connectors / MCP
servers / Skills / Plugins / Channels. Old links to the pages these absorbed
still resolve and open the right tab.

The top bar carries the notification bell, the theme toggle
(system → light → dark), and the **STOP** switch, which requests cancellation of
every task that is queued, running, paused, or waiting for your approval, at the
next safe boundary. It is governed and audited — not a force-kill.

The layout adapts live: below 1024 px the header menu opens navigation as an
overlay without changing the workspace width. At 1024 px and wider, the
256-pixel sidebar shares screen space and reflows the canvas; collapsing it
expands the bounded focus view. Sidebar and workspace scrolling stay independent.

Continue with [Connecting a model](connecting-a-model.md). For a tour of every
destination and its evidence views, see
[Dashboard and observability](dashboard-and-observability.md).
