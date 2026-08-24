# Raiker

Raiker is a local-first AI assistant and coding agent. Chat, repository work,
tools, approvals, permissions, and audit records run through one governed local
runtime, whether the model is local, on your private network, or hosted.

Raiker provides two main workspaces:

- **Chat** for conversations, attachments, research, memory, and approvals.
- **Build** for repository-aware planning, edits, commands, commits, and pushes.

## Project status

Raiker is ready for local, single-user use from a source checkout. The web dashboard
and terminal client are available. Features without a governed executor
fail closed. Hosted multi-user operation is deferred. Read the
[current limitations](docs/guide/known-limits.md) before relying on Raiker for
important work.

## Run

Install Python 3.11+, Node.js 20+, and Git, then run:

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix apps/web ci
npm --prefix apps/web run build
raiker-app
```

`raiker-app` starts Raiker on a loopback address and opens the dashboard in
your browser. On first run, create the local owner account and connect a model.
There is no Raiker cloud account.

For Windows instructions, project-local workspaces, explicit server control,
and uninstall help, see [Getting started](docs/guide/getting-started.md).

## Documentation

- **[User guide](docs/guide/README.md)** — install, configure, and use Raiker.
- **[Documentation index](docs/README.md)** — user, technical, security, and
  project documentation.
- **[Architecture reference](docs/architecture/README.md)** — implementation,
  contracts, governance, and design specifications.
- **[Known limits](docs/guide/known-limits.md)** — important boundaries and
  unavailable features.
- **[Troubleshooting](docs/guide/troubleshooting.md)** — reason codes and fixes.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) to work on Raiker. Report
vulnerabilities according to [SECURITY.md](SECURITY.md).

## License

Raiker is licensed under the [Apache License 2.0](LICENSE). Third-party notices
are listed in [NOTICE](NOTICE).
