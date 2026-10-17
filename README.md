# Raiker

Raiker is a **local-first personal autonomous AI agent**: a personalised
**personal AI agent for one owner**. It is an
all-purpose partner for thinking, researching, creating, communicating,
organising, coding, automating, and completing digital work across the models,
tools, files, projects, and services that owner connects and authorises. Its
working foundation combines a personal AI assistant, a coding/build agent, and
an extensible, owner-governed runtime; goal-level capabilities are planned and
staged in the [personal-agent architecture](docs/plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).

Raiker opens in its own desktop window. The desktop app, web dashboard and
terminal client are available for local, single-owner use; features without a
governed executor fail closed, and hosted multi-user operation is deferred.

## Run

Install Python 3.11+, Node.js 20+, and Git, then run:

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm --prefix web ci
npm --prefix web run build
npm --prefix desktop ci
npm --prefix desktop run build
raiker-app
```

Python **3.11 or newer** is required; check with `python --version` once the
environment is active. If the install instead starts downloading version after
version of the same package, it is on an older Python — see
[Getting started](docs/guide/getting-started.md#if-the-install-downloads-the-same-package-over-and-over).
With [uv](https://github.com/astral-sh/uv), `uv sync --extra dev` installs the
exact set in `uv.lock` and resolves nothing at all.

`raiker-app` starts Raiker on a loopback address and opens it in Raiker's
desktop window (`raiker-app --browser` uses your browser instead; without the
`desktop/` build it falls back to the browser and says why). On first run,
create the local owner account and connect a model. There is no Raiker cloud
account.

For Windows instructions, project-local workspaces, explicit server control,
and uninstall help, see [Getting started](docs/guide/getting-started.md).

### Linux

On Debian or Ubuntu, install the OS-provided Python tooling and Git first. Use
a NodeSource package, `nvm`, or another trusted source when the distribution's
`nodejs` is older than 20.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
npm --prefix web ci
npm --prefix web run build
npm --prefix desktop ci
npm --prefix desktop run build
raiker-app
```

Raiker binds to loopback and stores instance data under the normal Linux user
data directory unless `--workspace PATH` is supplied. `raiker-app service
install` registers a user-level `systemd` service; it does not require or create
a system service.

### macOS

Install the command-line prerequisites with Homebrew (or equivalent), then use
the Homebrew Python explicitly when creating the environment:

```bash
brew install python@3.11 node@20 git
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
$(brew --prefix python@3.11)/bin/python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
export PATH="$(brew --prefix node@20)/bin:$PATH"
npm --prefix web ci
npm --prefix web run build
npm --prefix desktop ci
npm --prefix desktop run build
raiker-app
```

`raiker-app service install` creates a user LaunchAgent. Current source installs
are supported; locally generated Linux `.deb`/AppImage and macOS `.pkg`
artifacts are unsigned unless a published release explicitly says otherwise.

## Documentation

- **[User guide](docs/guide/README.md)** — install, configure, and use Raiker.
- **[Documentation index](docs/README.md)** — user, technical, security, and
  project documentation.
- **[Architecture reference](docs/architecture/README.md)** — implementation,
  contracts, governance, and design specifications.
- **[Known limits](docs/architecture/KNOWN_LIMITS.md)** — important boundaries and
  unavailable features.
- **[Troubleshooting](docs/guide/troubleshooting.md)** — reason codes and fixes.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) to work on Raiker. Report
vulnerabilities according to [SECURITY.md](SECURITY.md).

## License

Raiker is licensed under the [Apache License 2.0](LICENSE). Third-party notices
are listed in [NOTICE](NOTICE).
