# Raiker

Raiker is a **local-first personal autonomous AI agent** you install on your
own computer: a personal AI agent for one owner. It is an all-purpose partner
for thinking, researching, creating, communicating, organising, coding,
automating and completing digital work across the models, tools, files,
projects and services you connect and authorise. Its working foundation
combines a personal AI assistant (Chat), a coding/build agent (Build), image
work (Design), and an extensible, owner-governed runtime;
goal-level capabilities are planned and staged in the
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
| Windows 10 (1809+) or 11, Intel/AMD | `Raiker-<version>-windows-x86_64-setup.exe` (or `.msi`) |
| Windows 11 on Arm | The x86-64 `setup.exe` (runs under Windows 11's built-in emulation; there is no native Arm build yet) |
| Mac with Apple silicon (M1 or later), macOS 12+ | `Raiker-<version>-macos-arm64.dmg` |
| Linux x86-64 (Ubuntu 22.04+, Debian 12+, Fedora 36+) | `.AppImage`, `.deb` or `.rpm` for `linux-x86_64` |
| Linux ARM64 | `.AppImage`, `.deb` or `.rpm` for `linux-arm64` |

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

## AI providers

| Kind | Supported |
|---|---|
| On this computer | Ollama, LM Studio, llama.cpp (managed GGUF), MLX on Apple silicon |
| Your own network | vLLM and any OpenAI-compatible endpoint on your LAN or home lab |
| Hosted | Anthropic, OpenAI, Google Gemini, OpenRouter, ChatGPT subscription (Codex) and other OpenAI-compatible providers |

Raiker detects a local runtime that is already installed. If you want local
models and have none, Models links to the runtime's official download; Raiker
never runs a third-party installer for you, and never downloads a model until
you choose one (sizes are shown first). Hosted-provider keys are stored
encrypted. See [Connecting a model](docs/guide/connecting-a-model.md).

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
- Notifications for things that need you, which bring the window forward.
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

- **Windows (setup.exe), macOS, AppImage:** **Settings → Updates** checks the
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
| macOS | Move Raiker from Applications to the Bin | Kept; remove it first with Settings → Account → Delete my account |
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
