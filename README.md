# Raiker

Raiker is a local-first, governed AI-agent runtime. It keeps model output and tool calls behind policy, approvals, audit events, SQLite state, and checkpoints, so automation stays observable and controllable.

It provides two local interfaces backed by the same runtime:

- `raiker` — a terminal client.
- `raiker-web` — a loopback web dashboard and governed API.

## Current runtime posture

The launchable local UIs are the plain local terminal client and the local web dashboard. Rich/native desktop, mobile, IDE, voice, browser-extension, and hosted multi-user clients are Phase 8 deferred.

Runtime status: `runtime_enablement_candidate`; strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

The dashboard is a presentation layer over the governed backend; it has no
direct tool authority. Durable memory mutation is broker-governed. Approval
resolution is metadata-only unless a separately documented, action-specific
executor explicitly records its single execution; unsupported capabilities
remain disabled or fail-closed.

In the default approval flow, approval resolution is metadata-only.

The chat surface presents a normal conversation. Governance evidence belongs in
Sessions and Checkpoints rather than in the transcript. The shipped composer
lists configured model profiles only, offers a read-only estimated context view
when capacity is configured, and exposes the existing global permission modes.
Provider token accounting, price/quota reporting, automatic 90% compaction,
view-only attachment inspection, conversational task clarification, and
approved task/project-action resumption remain planned work; they are not
claimed as available by this README.

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
