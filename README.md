# Raiker

Raiker is a **personal autonomous AI agent** you install on your
own computer: a personal AI agent for one owner. It is an all-purpose partner
for thinking, researching, creating, communicating, organising, coding,
automating and completing digital work across the models, tools, files,
projects and services you connect and authorise. Its working foundation
combines a personal AI assistant (Chat), a coding/build agent (Build), image
work (Design), and an extensible, owner-governed runtime. **Goals** carry an
outcome across sessions as a plan of governed steps, under an execution profile
you set in Settings; further goal-level capabilities are planned and staged in the
[personal-agent architecture](docs/plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).

Raiker runs as a desktop application on Windows, macOS and Linux. Its desktop
window, web dashboard and terminal client are available for local, single-owner
use; features without a governed executor fail closed, and hosted multi-user
operation is deferred. There is no Raiker cloud account.

## Download and install Raiker

Raiker is packaged as a desktop application for Windows, macOS and Linux. The
standard installation needs **no development environment and no manual
dependency setup**: no Python, Node.js, Git, package manager or terminal. The
Raiker engine is bundled inside the application.

1. Open the [latest Raiker release](https://github.com/sharRahul/Raiker/releases/latest).
2. Download the installer for your computer (table below).
3. Run the installer.
4. Follow the guided setup: create your local account, check what your device
   can run, choose an AI provider (or decide later), choose where model
   requests may go, review what Raiker may do, and let Raiker check the
   installation.
5. Start using Raiker.

| Your computer | Download |
|---|---|
| Windows 10 (1809+) or 11, Intel/AMD | `Raiker-<version>-windows-x86_64-setup.exe` |
| Windows 11 on Arm | `Raiker-<version>-windows-arm64-setup.exe` (the x86-64 program, tested on Windows on Arm; it runs under Windows 11's built-in emulation — there is no native Arm build yet) |
| Mac with Apple silicon (M1 or later), macOS 12+ | `Raiker-<version>-macos-arm64.dmg` |
| Linux x86-64 (Ubuntu 22.04+, Debian 12+, Fedora 36+) | `Raiker-<version>-linux-x86_64.AppImage` |
| Linux ARM64 | `Raiker-<version>-linux-arm64.AppImage` |

Each release carries exactly one download per platform. The `.msi`, `.deb` and
`.rpm` packages are built and tested on every release run but are not attached
to the release; see [Releasing](docs/guide/releasing.md).

Raiker sets up everything it needs on first start. Local AI models and other
optional components are added later, from inside Raiker, only when you choose
them. Full instructions: [Installing Raiker](docs/guide/getting-started.md).

## System requirements

| | Minimum | Recommended |
|---|---|---|
| Operating system | Windows 10 1809, macOS 12, Linux with glibc 2.35 | Windows 11, macOS 14, Ubuntu 24.04 |
| Architecture | x86-64 or ARM64 (64-bit only) | — |
| Memory | 4 GB | 8 GB with a hosted provider; 16 GB+ for local models |
| Free storage | 2 GB | 20 GB+ if you will download local models |
| Graphics | Not required | An NVIDIA, AMD or Apple-silicon GPU speeds up local models |
| Network | Not required to install | Needed for hosted providers, web research and connectors |

These are checked **while Raiker installs**, on your computer and without
sending anything anywhere: a computer that cannot run Raiker is told so before
anything is installed or any account exists.

## Installing and first run

1. **The installer checks this computer.** The Windows installer shows a
   *Checking this computer* page before it copies a file (Windows version,
   64-bit, memory, free space for the program and for your data); the `.deb`
   and `.rpm` packages check memory before they unpack. A requirement that is
   not met stops the install with its fix.
2. **Raiker Setup finishes the installation** the first time you open Raiker,
   on every platform (it is the only install step a dragged Mac app or an
   AppImage has): it checks this computer in full — including credential
   protection, network and graphics — prepares encrypted storage, starts
   Raiker and verifies every part, showing each step as it runs. If something
   fails it says what in one sentence, with **Try again** and **Open logs**.
3. **Account** — a local owner account and password. It never leaves your
   computer.
4. **Model** — connect a local runtime, a home-network endpoint or a hosted
   provider, and choose a default model; or decide later.
5. **Privacy** — whether model requests stay on this device or may go to the
   providers you connect.

Raiker starts conservatively and asks before it takes a governed action, so
there is no permissions step; review them any time on the Permissions page.

Setup can be left and resumed at any point, and does not appear again once
complete. Running Raiker from a source checkout has no installer, so there the
in-app setup also includes **This device** and **Check** stages.

## Running Raiker under WSL2 or on a VPS

The desktop installers above are the standard installation. Two other setups
run the **same single-owner host** (`raiker-web`) from a source checkout: inside
WSL2 on a Windows PC, or on a Linux virtual private server (VPS) you control.
Neither makes Raiker a hosted multi-user service, and there is still no Raiker
cloud account: the host, its encrypted data and its credentials stay on the
machine you install it on.

Both need Python 3.11+, Node.js 24+ and Git on that machine.

### WSL2 (Windows 10 21H2+ or Windows 11)

1. In an administrator PowerShell, install WSL2 with Ubuntu and restart when
   asked:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

2. Open **Ubuntu** from the Start menu, then install the build tools and
   Node.js 24:

   ```bash
   sudo apt update && sudo apt install -y git python3 python3-venv python3-pip build-essential curl
   curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
   sudo apt install -y nodejs
   ```

3. Clone and build Raiker **inside the Linux file system** (`~`, not
   `/mnt/c/…`: the Windows drive is much slower from WSL and its permissions do
   not protect Raiker's data):

   ```bash
   git clone https://github.com/sharRahul/Raiker.git ~/Raiker && cd ~/Raiker
   python3 -m venv .venv && . .venv/bin/activate
   python -m pip install -e .
   npm --prefix web ci && npm --prefix web run build
   ```

4. Start the host on loopback and open it from Windows:

   ```bash
   raiker-web --workspace ~/raiker-workspace --no-browser
   ```

   WSL2 forwards `localhost` to Windows, so open <http://127.0.0.1:8765/> in a
   Windows browser and complete setup there. Keep the host on loopback; do not
   pass `--allow-public` just to reach it from the same PC.

Notes for WSL2:

- **Models.** A model server running on Windows (Ollama, LM Studio) is reached
  from WSL at the Windows host's address, not `127.0.0.1`, unless WSL's
  mirrored networking is on (`networkingMode=mirrored` in `%UserProfile%\.wslconfig`).
  Hosted providers need nothing extra.
- **Credentials.** WSL usually has no unlocked Secret Service, so
  *This device* reports *Credential protection — private file*. Provider keys
  are still encrypted at rest; see [Troubleshooting](docs/guide/troubleshooting.md).
- **Starting it again.** WSL stops when its last terminal closes. Reopen
  Ubuntu, `cd ~/Raiker && . .venv/bin/activate`, and run `raiker-web` again,
  or keep it running with the systemd unit shown for a VPS below (enable
  systemd in WSL with `[boot] systemd=true` in `/etc/wsl.conf`).

### VPS (a Linux server you control)

Use a VPS with at least 2 vCPU, 4 GB of memory and 20 GB of disk running
Ubuntu 22.04/24.04 or Debian 12, and a hosted AI provider (a small VPS cannot
run useful local models). Run Raiker as its own unprivileged user.

1. Install the tools (as above for Ubuntu), then create the user and build:

   ```bash
   sudo adduser --disabled-password --gecos "" raiker
   sudo -iu raiker
   git clone https://github.com/sharRahul/Raiker.git ~/Raiker && cd ~/Raiker
   python3 -m venv .venv && . .venv/bin/activate
   python -m pip install -e .
   npm --prefix web ci && npm --prefix web run build
   exit
   ```

2. Run the host under systemd, **bound to loopback**:

   ```ini
   # /etc/systemd/system/raiker.service
   [Unit]
   Description=Raiker host
   After=network-online.target

   [Service]
   User=raiker
   WorkingDirectory=/home/raiker/Raiker
   ExecStart=/home/raiker/Raiker/.venv/bin/raiker-web --workspace /home/raiker/workspace --host 127.0.0.1 --port 8765 --no-browser
   Restart=on-failure
   NoNewPrivileges=true

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now raiker
   ```

3. **Reach it through an SSH tunnel** (recommended). Nothing is exposed to the
   internet; from your own computer:

   ```bash
   ssh -N -L 8765:127.0.0.1:8765 raiker-vps
   ```

   then open <http://127.0.0.1:8765/> and complete setup. The first person to
   create the owner account owns the instance, so do this before anything else
   can reach the port.

4. **Or reach it over a private network** if you need a browser on another
   device without a tunnel. Put the VPS on a VPN you control (WireGuard,
   Tailscale), then bind Raiker to that private address — never to a public
   one. Raiker refuses a non-loopback bind unless you pass `--allow-public`
   *and* set a hardened `RAIKER_OWNER_TOKEN`, and it then turns on its
   transport guardrails (security headers, HSTS, rate limit):

   ```ini
   # in raiker.service, replacing ExecStart
   Environment=RAIKER_OWNER_TOKEN=<a long random value, e.g. from: openssl rand -hex 32>
   ExecStart=/home/raiker/Raiker/.venv/bin/raiker-web --workspace /home/raiker/workspace --host 100.64.0.10 --port 8765 --allow-public --no-browser
   ```

   Terminate TLS in front of it if your VPN does not already encrypt the
   traffic, with the proxy connecting to that private address.

5. **Or behind a reverse proxy on the same machine** (Caddy, nginx). Give the
   proxy its own listener and point the proxy there, **never at port 8765**:

   ```ini
   Environment=RAIKER_OWNER_TOKEN=<a long random value>
   ExecStart=/home/raiker/Raiker/.venv/bin/raiker-web --workspace /home/raiker/workspace --proxy-socket /run/raiker/proxy.sock --no-browser
   ```

   ```caddyfile
   raiker.example.com {
       reverse_proxy unix//run/raiker/proxy.sock
   }
   ```

   Every request on the proxy listener is remote, whatever headers it carries:
   rate limited, password recovery refused, and HSTS when the proxy received
   HTTPS. The socket is created for its owner and group only (`0660`), so add
   the proxy's user to Raiker's group. `--proxy-port 8766` opens
   `127.0.0.1:8766` instead, for Windows or a proxy that cannot use a socket.
   Port 8765 stays for this computer: a request reaching it with a forwarding
   header (`X-Forwarded-For`, `Forwarded` and the like) is refused with what to
   change, and **Diagnostics** shows the refusals. A proxy that sends no such
   header and is pointed at 8765 anyway cannot be told apart from a browser on
   the server itself, which is why the proxy gets a listener of its own.

   A remote instance is still a single-owner instance:
   every action stays governed, approved and audited, and the owner password
   protects it — choose a strong one and turn on **Settings → Security &
   sign-in → Enroll in MFA**.

Update a WSL2 or VPS installation with `git pull`, `python -m pip install -e .`
and `npm --prefix web ci && npm --prefix web run build`, then restart
`raiker-web` (`sudo systemctl restart raiker`). Back up the workspace directory
first. Updating from a release before 2026-10-26 also needs
`python -m pip uninstall -y sqlcipher3-wheels` before the install: SQLCipher now
comes from the upstream `sqlcipher3` package (SQLCipher 4.19.0, SQLite 3.53.4,
FTS5), and both packages provide the same module. More: [Managing the host](docs/guide/managing-the-host.md#explicit-web-server-control).

## AI providers

| Kind | Supported |
|---|---|
| On this computer | Ollama, LM Studio, llama.cpp (managed GGUF), MLX on Apple silicon |
| Your own network | vLLM and any OpenAI-compatible endpoint on your LAN or home lab |
| Hosted | Anthropic, OpenAI, Google Gemini, OpenRouter, ChatGPT subscription through the local subscription client, and other OpenAI-compatible providers |

Raiker detects a local runtime that is already installed. If you want local
models and have none, Models links to the runtime's official download; Raiker
never runs a third-party installer for you, and never downloads a model until
you choose one (sizes are shown first). Hosted-provider keys are stored
encrypted. Connecting a provider once in **Models** is the whole setup: the
connection authorizes that provider's own address and nothing else, with no
separate allowlist to configure, and **Permissions → Hosted models** turns every
hosted provider off again in one step. See
[Connecting a model](docs/guide/connecting-a-model.md).

## Working offline

Installing and starting Raiker needs no network. With a local model, Chat,
Build, memory, tasks and files work offline. Hosted providers, web research,
GitHub, messaging connectors and update checks need a connection, and say so
when it is missing.

## Desktop features

- Its own window, with a native menu and keyboard shortcuts for every place,
  window size and position remembered, and one window brought forward if you
  open Raiker again.
- Closing the window leaves Raiker working in the background (scheduled work,
  reminders, approvals); the first time, a notification says so. Quit from
  **Host** in the top bar or the tray.
- **Quick Entry**: Ctrl+Shift+Space (Cmd+Shift+Space on a Mac) opens a small
  box from anywhere on your computer to start a task or add to a recent
  conversation, without bringing Raiker forward.
- Optionally keep Raiker in the tray when its window closes, with a dot while a
  decision waits; open a project in a second window.
- Notifications for things that need you, chosen by event (approval needed,
  input needed, response ready, task failed, task finished), which bring the
  window forward.
- Light and dark themes following your system.
- Visible background work and agent status, with **Stop** controls.

## Security and privacy

- Raiker listens on this computer only (`127.0.0.1`) and requires your sign-in.
- Your workspace database is encrypted. Provider keys are encrypted with a key
  held by Windows Data Protection, the macOS Keychain or the Linux Secret
  Service where available, and by a private file otherwise.
- Every action is governed: permissions start conservative, governed actions
  ask first, and completing setup grants nothing.
- The installer never asks for administrator rights on Windows and never
  downloads anything.
- Release installers are code-signed and notarised (macOS) when published,
  each covered by an Ed25519-signed manifest.

See [Security and privacy](docs/guide/security-and-privacy.md).

## Updating

Updates are verified against Raiker's release signing key before anything is
installed, and your data is never touched by an update.

- **Windows (setup.exe), macOS, AppImage:** **Settings → About & updates** checks the
  update channel you have pinned, and installs a verified update in place,
  keeping the previous version for rollback on macOS and AppImage.
- **`.deb`, `.rpm`, `.msi`:** install the new release's package over the old
  one with your system's installer.

Raiker never contacts an update server until you pin a channel. See
[Managing the host](docs/guide/managing-the-host.md#update-and-roll-back).

## Troubleshooting and repair

- The **Check** step and **Diagnostics** name any component that is not
  working, with the fix.
- If the window says Raiker's host did not start, open Raiker again; if it
  persists, reinstall. Reinstalling never removes your data.
- See [Troubleshooting](docs/guide/troubleshooting.md) for reason codes.

## Uninstalling

| System | How | Your data |
|---|---|---|
| Windows | Settings → Apps → Raiker → Uninstall | Kept unless you choose **Yes** when asked |
| macOS | Move Raiker from Applications to the Bin | Kept; remove it first with Settings → General → Delete my account |
| Linux | `sudo apt remove raiker`, `sudo dnf remove raiker`, or delete the AppImage | Kept |

Models installed with other tools (Ollama, LM Studio), folders you attached and
backups on other drives are never removed. Data locations:
`%LOCALAPPDATA%\Raiker`, `~/Library/Application Support/Raiker`,
`~/.local/share/raiker`.

## For developers

Contributors run Raiker from a source checkout with Python 3.11+, Node.js 24+
and Git:

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv && . .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"              # or: uv sync --extra dev
npm --prefix web ci && npm --prefix web run build
npm --prefix desktop ci && npm --prefix desktop run build
raiker-app
```

`raiker-app` starts Raiker on a loopback address and opens its desktop window
(`--browser` uses your browser). To build this platform's installers locally:
`python scripts/build_native_runner.py && python scripts/build_desktop_app.py`
(output in `desktop-release/`). Details: [Getting started from
source](docs/guide/getting-started.md#run-from-source),
[Releasing](docs/guide/releasing.md), [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- **[User guide](docs/guide/README.md)** — install, configure, and use Raiker.
- **[Documentation index](docs/README.md)** — user, technical, security, and
  project documentation.
- **[Architecture reference](docs/architecture/README.md)** — implementation,
  contracts, governance, and design specifications.
- **[Desktop distribution decision](docs/adr/ADR-0003-desktop-distribution.md)**
  and the [release acceptance matrix](docs/plans/RELEASE_ACCEPTANCE_MATRIX.md).
- **[Known limits](docs/architecture/KNOWN_LIMITS.md)** — important boundaries
  and unavailable features.
- **[Troubleshooting](docs/guide/troubleshooting.md)** — reason codes and fixes.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) to work on Raiker. Report
vulnerabilities according to [SECURITY.md](SECURITY.md).

## License

Raiker is licensed under the [Apache License 2.0](LICENSE). Third-party notices
are listed in [NOTICE](NOTICE).
