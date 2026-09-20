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
npm --prefix web ci
npm --prefix web run build
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
npm --prefix web ci
npm --prefix web run build
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
npm --prefix web ci
npm --prefix web run build
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

### The four screens after the account

Setup runs once and asks two questions.

| Stage | What it is |
|---|---|
| **Welcome** | What Raiker is: Chat, Build and Design. Nothing to configure. |
| **Model** | Connect a provider or a runtime. It leads with the easiest working path — a runtime already running on this machine needs no account and no key — and keeps the full provider matrix behind **Other options**. **Advanced setup** opens [Models](connecting-a-model.md) for deeper configuration; you do not need it to finish. |
| **Privacy** | *Where may Raiker send model requests?* **Local only**, or **Local, and the providers I connect**. This is about where your words travel. [Permissions](permissions-and-runtime-modes.md) governs the actions Raiker may take. |
| **Ready** | Finish into **Chat**, **Build** or **Design**, or **Start using Raiker** for the dashboard. The screen says what it actually set up: *Your Raiker is ready* when a model is chosen, and *Setup saved* when you deferred that choice — with each mode naming what it still needs and the page that supplies it. Every mode opens either way; exploring one before connecting a model is how you find out what it is. |

Backup is offered on the last screen as optional setup rather than asked for
before your first turn, and nothing claims a backup exists until Raiker has
written and verified an encrypted snapshot. Raiker starts conservatively and asks
before it takes a governed action, so there is no permissions matrix to fill in
on first run.

### Unlocking, afterwards

**Unlock Raiker** is the action on the lock screen, and the only one you need.
Beneath it: **Create a User Account**, which adds another account to *this*
Raiker, **Forgot password?**, and **Use or create another instance**.

That last one is a different thing from the first, and the screen now says so
before you take it: a separate instance has its own workspace, its own models and
its own memory, shares nothing with the one you are unlocking, and opens in its
own tab. It used to be labelled *Create a User Account* too — the same words as
the control above it — so the only way to learn that it left this instance was to
press it.

## What you get

Destinations are split by how often you go to them. The sidebar carries the
work; everything you set up once lives behind **More** in the top bar.

| Where | Group | Destinations |
|---|---|---|
| Sidebar | Core | Workbench, Chat, Build, Design, Threads, Tasks, Projects, Approvals, Messaging |
| Sidebar | Knowledge | Memory, Knowledge Map |
| More | — | Settings, directly, as the first row |
| More | Manage | Permissions, Models, Extensions |
| More | Observe | Observability |
| More | Support | Guide |
| More | Settings | the ten Settings sections, each as a direct link |

**More was a gear**, and it opened a window that could not take you to Settings:
its ten sections were listed, the destination itself was not. A gear promises the
settings screen everywhere else you have used a computer, so it is named for what
it is now, and Settings leads the window.

**Workbench** is the live board: what is running, which agents are standing,
what is scheduled, and what needs a decision. **Approvals** sits in the sidebar
rather than behind More because a decision waiting on you is the work, arriving
many times a day, while Permissions and Models are configured once and
revisited.

**Needs your attention** on that board means exactly that. A run that is running
is progress and stays on the board below with its Stop control; what reaches the
rail is work that will not move again until you act — a run waiting on an
approval, or a paused one — along with approvals themselves and any runtime
readiness problem.

**"Nothing needs you right now" is a claim about all three, and it is only made
when all three were read.** If Raiker cannot read its own readiness it says so
and names the gap — *No approvals are waiting and no work is blocked. Raiker
could not read its own runtime readiness, so this is not an all-clear* — rather
than counting an unread check as zero problems. A readiness claim nobody checked
is worse than no claim, because you would act on it.

**Sessions is inside Observability**, not a destination of its own: it is the
complete record of every conversation *and* every task run, which is why
**Threads** — the board you pick work up from — lists conversations and the
threads your routines are advancing, and nothing else.

Four destinations are tabbed:

| Destination | Tabs |
|---|---|
| Models | Overview, My models, Add model, Runtime & routing, Usage |
| Extensions | Connectors, MCP servers, Skills, Hooks, Plugins |
| Observability | Overview, Sessions, Activity, Checkpoints, Live work, Notifications |
| Settings | General, Notifications, Personalisation, Security & sign-in, Privacy, Account, Web access, Git credential, Runtime configuration, Updates |

Old links to the pages these absorbed still resolve and open the right tab, and
so does the path form — `#/extensions/mcp` opens Extensions on MCP servers,
exactly as `#/extensions?tab=mcp` does.

The top bar carries the notification bell, **More** — Settings and every
destination that is not on the sidebar — the host control, and the **STOP**
switch.

**STOP** is quiet while nothing is running: an icon, in the row with the bell
and More. When work is under way it turns red and states how many tasks it
would reach, and pressing it requests cancellation of every task that is queued,
running, paused, or waiting for your approval, at the next safe boundary. It is
governed and audited — not a force-kill. It is in the same place, and one press
from the same dialog, whether or not anything is running: with an empty queue it
says so immediately rather than asking you to confirm a stop that would reach
nothing.

The theme is a preference rather than a shell control, and lives in
**Settings → Personalisation**.

The layout adapts live: below 1024 px the header menu opens navigation as an
overlay without changing the workspace width. At 1024 px and wider, the
256-pixel sidebar shares screen space and reflows the canvas; collapsing it
expands the bounded focus view. Sidebar and workspace scrolling stay independent.

Continue with [Connecting a model](connecting-a-model.md). For a tour of every
destination and its evidence views, see
[Dashboard and observability](dashboard-and-observability.md).
