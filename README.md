# Raiker

Raiker is a local-first, governed AI-agent runtime. It keeps model output and tool calls behind policy, approvals, audit events, SQLite state, and checkpoints, so automation stays observable and controllable.

It provides two local interfaces backed by the same runtime:

- `raiker` — a terminal client.
- `raiker-web` — a loopback web dashboard and governed API.

## Quick start

Requirements: Python 3.11+, Git, and Node 20+ for the web dashboard.

```powershell
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Start the terminal client:

```powershell
raiker
raiker --prompt "Hello Raiker"
```

Or build and run the local dashboard:

```powershell
npm --prefix apps/web install
npm --prefix apps/web run build
raiker-web --workspace .
```

Open `http://127.0.0.1:8765`.

## Connect a model

Raiker does not bundle a model. Run a supported local OpenAI-compatible server (llama.cpp is the default; Ollama and LM Studio are supported), then select a profile:

```text
/models
/model use raiker-local-llama-cpp
/model health
```

Hosted providers are available only through explicit, policy-gated configuration; Raiker never silently falls back to another model or provider.

## Development

```powershell
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
npm --prefix apps/web run check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance, [SECURITY.md](SECURITY.md) for the security model, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical detail.

## License

Apache License 2.0. See [LICENSE](LICENSE).
