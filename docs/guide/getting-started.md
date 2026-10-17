# Getting started

## Install the desktop app

Raiker is a desktop application for Windows, macOS and Linux. The installer
carries everything Raiker needs, including its own engine: there is nothing
else to install first, and no terminal.

1. Download the installer for your computer from the
   [Raiker releases](https://github.com/sharRahul/Raiker/releases/latest):

   | Your computer | Download | Then |
   |---|---|---|
   | Windows 10 (1809+) or 11 | `Raiker-<version>-windows-x86_64-setup.exe` | Open it, choose where to install (your user folder by default), finish. No administrator password is asked for. An `.msi` is also published for managed installs. |
   | Windows 11 on Arm | the same x86-64 `setup.exe` | Windows runs it under its built-in emulation. |
   | Mac with Apple silicon / Intel (macOS 12+) | `Raiker-<version>-macos-arm64.dmg` / `-macos-x86_64.dmg` | Open the `.dmg` and drag **Raiker** into **Applications**. |
   | Ubuntu, Debian | `Raiker-<version>-linux-<arch>.deb` | Open it with Software, or `sudo apt install ./Raiker-….deb`. |
   | Fedora, openSUSE | `Raiker-<version>-linux-<arch>.rpm` | Open it with Software, or `sudo dnf install ./Raiker-….rpm`. |
   | Any other Linux desktop | `Raiker-<version>-linux-<arch>.AppImage` | Mark it executable (file properties) and open it. |

2. Open **Raiker** from your applications menu, Start menu or Launchpad. The
   first time, **Raiker Setup** finishes the installation (below).
3. Create your local account and follow the guided setup ([First run](#first-run)).

**No signed release has been published yet** (2026-10-17). Until one is, the
installers built by CI for each change are attached to the **Desktop package**
workflow runs under the repository's **Actions** tab. They are unsigned test
builds: Windows SmartScreen shows *Windows protected your PC* (choose **More
info → Run anyway** only if you trust the build), and macOS refuses to open an
unsigned app that was downloaded from the internet.

### What the installer does and does not do

- Installs the application files only: on Windows into
  `%LOCALAPPDATA%\Programs\Raiker` for your account, on macOS into
  Applications, on Linux into `/opt/Raiker`.
- Adds Start-menu and desktop shortcuts (Windows) or an applications-menu entry
  (Linux).
- **Checks this computer before installing anything.** The Windows installer's
  *Checking this computer* page shows the Windows version, 64-bit, memory and
  free space for the program and for your data, each with ✔, ! (works, with a
  limit worth knowing) or ✖ (not met, with its fix); with a ✖ it will not
  continue, and a silent install (`/S`) exits with code 2 instead. The `.deb`
  and `.rpm` packages check memory before unpacking. macOS refuses versions
  before 12 itself.
- Downloads nothing, creates no account, connects no model and makes no backup.
  Those happen in setup, when you choose them.

### Raiker Setup: finishing the installation

The first time you open Raiker — and after each update — a **Raiker Setup**
window finishes the installation before Raiker itself opens. On a Mac or with
an AppImage, where copying the app is the whole install, this is the
installation step. Press **Set up**:

1. **Checking this computer** — operating system, architecture, memory,
   processor, graphics acceleration (never required), free storage, network
   route (no packet is sent), and how provider keys will be protected. Each
   result is listed as it is found; a requirement that is not met stops setup
   and names its fix. Nothing is created yet, so there is nothing to clean up.
2. **Starting Raiker** — your encrypted data
   folder is created and Raiker starts, reachable only from this computer.
3. **Verifying** — the encrypted store opens, text search
   works, and the interface is served.

Each step shows how long it is taking; **Show details** shows the live log,
which is also written to `logs/setup.log` in Raiker's shell profile
(`%APPDATA%\Raiker`, `~/Library/Application Support/Raiker` or
`~/.config/Raiker`). If a step fails you get one plain sentence, **Try again**,
**Open logs** and **Quit** — nothing in it deletes your data. Then **Open
Raiker** takes you to the account screen. If Raiker later fails to start, the
same window opens to check it again; you can also run it yourself by starting
Raiker with `--repair`.

Your data lives outside the application, in `%LOCALAPPDATA%\Raiker`,
`~/Library/Application Support/Raiker` or `~/.local/share/raiker`, so
reinstalling or updating never touches it.

## Run from source

Contributors run Raiker from a source checkout. This needs:

- Python 3.11 or newer
- Node 20 or newer (to build the dashboard and the desktop window)
- Git

**Check the Python version before anything else**, and check it *inside* the
virtual environment rather than before creating it — `python` is whatever name
resolution last decided it is, and on Windows that is often not the version you
installed most recently:

```bash
python --version
```

The dashboard and terminal client support local single-user operation. Hosted
multi-user, dedicated mobile, and IDE clients are not part of the current
release. To build this platform's installers from a checkout, see
[Releasing](releasing.md#building-installers-locally).

### Install from source

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

Then build Raiker's desktop window, which is how `raiker-app` opens Raiker:

```bash
npm --prefix desktop ci
npm --prefix desktop run build
```

Without it Raiker still works: `raiker-app` says the window is not built and
opens your default browser instead.

## Run

```bash
raiker-app
```

`raiker-app` is the primary application command. It starts Raiker on loopback
and opens it in **Raiker's own desktop window** — a native window with its own
menu, shortcuts and notifications. Add `--browser` to open your default browser
instead; if the window is not available, `raiker-app` says why and opens the
browser for you. See [The desktop window](managing-the-host.md#the-desktop-window).
By default it uses the normal
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
running and opens its window. Everything is written under your own home
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
| `--no-browser` | Do not auto-open a browser. (`raiker-app --no-browser` opens neither the window nor a browser.) |
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

### The screens after the account

Setup runs once. It can be left at any stage and resumes where it stopped. It
is a focused screen of its own, without the app's navigation; a link in it
(such as **Advanced setup**) opens the app, and setup resumes at your next
sign-in until it is finished. On the desktop app the computer and the
installation were already checked by the installer and Raiker Setup, so
**This device** and **Check** appear only when you run Raiker from a source
checkout. There is no welcome or permissions screen: the app introduces Chat,
Build and Design itself, and [Permissions](permissions-and-runtime-modes.md)
is a page you can open any time — finishing setup grants nothing.

| Stage | What it is |
|---|---|
| **This device** *(source checkouts only)* | What this computer can run, measured on it and sent nowhere: operating system, architecture, memory, processor, graphics acceleration (never required), free storage, network, how provider keys are protected (Windows Data Protection, macOS Keychain, Linux Secret Service, or a private file), local model runtimes already installed, where your data is kept, and a local model size that will run here. A requirement that is not met is named with its fix. |
| **Model** | Connect a provider or a runtime. It leads with the easiest working path — a runtime installed on this machine that already names a model needs no account and no key — checks the model you choose, and keeps the full provider matrix behind **Other options** — or, when the recommendation is a connected account, **Choose a model** opens it. A model you already chose as the default on Models counts as your choice here. **Advanced setup** opens [Models](connecting-a-model.md) for deeper configuration; you do not need it to finish. |
| **Privacy** | *Where may Raiker send model requests?* **Local only**, or **Local, and the providers I connect**. This is about where your words travel. [Permissions](permissions-and-runtime-modes.md) governs the actions Raiker may take. |
| **Check** *(source checkouts only)* | Raiker checks its own parts from inside: the host, the interface, the encrypted database, the data format, long-term memory storage, the permission registry, the governed command runner and the credential vault — then makes one short request to the model you chose. A part that is not working says how to fix it; **Check again** reruns it. |
| **Ready** | Finish into **Chat**, **Build** or **Design**, or **Start using Raiker** for the dashboard. The screen says what it actually set up: *Your Raiker is ready* when a model is chosen, and *Setup saved* when you deferred that choice — with each mode naming what it still needs and the page that supplies it. Every mode opens either way; exploring one before connecting a model is how you find out what it is. |

Backup is offered on the last screen as optional setup rather than asked for
before your first turn, and nothing claims a backup exists until Raiker has
written and verified an encrypted snapshot. Raiker starts conservatively and asks
before it takes a governed action, so there is no permissions matrix to fill in
on first run. Once setup is complete it does not appear again.

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
| Sidebar | — | Home, Chat, Build, Design, Work, Memory |
| More | Recent | the last few places you opened, newest first |
| More | Review | Approvals |
| More | Connect | Models, Extensions |
| More | Settings | Settings itself, Permissions, and every Settings section as a direct link |
| More | Diagnostics & help | Observability, Guide |

More is grouped by what you come to do — review something, connect Raiker to
something, change a setting — with diagnostics and help last. It has no search
box of its own: **Search pages, settings and commands** at its top opens the
command palette (`Ctrl K`, `⌘K` on a Mac), which finds every page and every
Settings section by name. On a phone More is a full-height sheet with **Back**,
and it says which page you are on.

**More was a gear**, and it opened a window that could not take you to Settings:
its ten sections were listed, the destination itself was not. A gear promises the
settings screen everywhere else you have used a computer, so it is named for what
it is now, and Settings leads the window.

**Workbench** is the live board: what is running, which agents are standing,
what is scheduled, and what needs a decision. **Approvals** is a counted button
in the top bar, visible from every page, because a decision waiting on you is
the work, arriving many times a day, while Permissions and Models are configured
once and revisited; More lists it under **Review** too.

**Needs your attention** on that board means exactly that. A run that is running
is progress and stays on the board below with its Stop control; what reaches the
rail is work that will not move again until you act — a run waiting on an
approval, or a paused one — along with approvals themselves and any runtime
readiness problem. Below those, the rail lists what else is waiting on you from
each part of Raiker's own record — memories it proposed, a channel delivery that
did not arrive, an MCP tool held for your review, a containment signal — each
with the one place to resolve it. An item goes away when that part of Raiker
says it is resolved; a part that could not be read is named rather than taken
as clear.

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

**The interface is deliberately quiet.** Pages open with their content, not a
sentence about it: a page's one-line description is its title's tooltip, the
way into its guide chapter is the ⓘ icon, and an empty list shows its title
and the action that fills it. Pages that answered one question are one page
with tabs — **Work** holds Threads, Tasks and Projects; **Memory** holds the
Knowledge Map; **Extensions** holds messaging Channels.

Six destinations are tabbed:

| Destination | Tabs |
|---|---|
| Work | Threads, Tasks, Projects |
| Memory | Overview, Memories, Suggestions, Sources, Recall & indexing, Map |
| Models | Overview, My models, Add model, Runtime & routing, Usage |
| Extensions | Overview, Connectors, Channels, MCP servers, Skills, Hooks, Plugins |
| Observability | Overview, Sessions, Activity, Checkpoints, Live work, Notifications |
| Settings | General, Notifications, Personalisation, Security & sign-in, Privacy, Account, Web access, Git credential, Runtime configuration, Memory engine, Updates |

Old links to the pages these absorbed still resolve and open the right tab —
`#/tasks` opens Work on Tasks, `#/brain` opens Memory on Map, `#/messaging`
opens Extensions on Channels — and
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
**Settings → Personalisation**. Theme, density and typeface show as soon as you
choose them and are kept when you press **Save changes**; **Discard changes**,
or leaving with them unsaved, puts back what you had. The theme is kept on this
device. None of them changes Raiker's instructions, personality or what it may
do.

Settings keeps your edits until you press **Save changes** or **Discard
changes**, across all of its sections. If you leave Settings for another page
with an edit unsaved, Raiker asks first, and staying keeps the edit where it
was; reloading or closing the tab gets your browser's own *Leave site?* prompt.

Two tabs can have Settings open at once without one undoing the other. A save
from a page opened before another save is merged when the two changed different
settings — the page says *One setting changed elsewhere since this page opened
was kept as it was* — and refused when both changed the same one: *Not saved: a
setting you changed here was also changed somewhere else*. Your edits stay on
the page; **Show the newer settings (drops these edits)** loads what was saved.

The layout adapts live: below 1024 px the header menu opens navigation as an
overlay without changing the workspace width. At 1024 px and wider, the
256-pixel sidebar shares screen space and reflows the canvas; collapsing it
expands the bounded focus view. Sidebar and workspace scrolling stay independent.

Continue with [Connecting a model](connecting-a-model.md). For a tour of every
destination and its evidence views, see
[Dashboard and observability](dashboard-and-observability.md).
