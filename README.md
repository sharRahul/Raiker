# Raiker

**Raiker** is a local-first AI agent runtime that runs as a secure, observable, and extensible agent operating layer on your own machine, where every interface talks to the same governed core — contracts, policy, append-only events, SQLite state, approvals, and checkpoints. Its core philosophy is *no privileged interface and no silent runtime*: capabilities stay disabled until their policy, storage, audit, and acceptance work is complete, so the documentation never runs ahead of the code. It is built for developers, home-lab operators, and governed-enterprise users who want an auditable agent platform instead of an opaque chatbot.

---

## Features

- **Local-first governed runtime** — A deterministic gather → act → verify loop (`raiker/runtime/orchestrator.py`) drives every turn through a 16-state machine, a static policy engine, a tool broker, and an append-only JSONL + SQLite event/state layer. Model outputs and tool calls are always untrusted proposals that must pass validation, policy, and approval.
- **Plain local terminal client only** — `raiker` launches the line-oriented terminal client. Rich/native TUI is Phase 8 deferred work; Desktop/Web/Dashboard/Mobile/IDE/Voice/Browser Extension/REST/API clients are Phase 8 deferred, not active runtime surfaces. The deterministic mock/test provider is test-only and policy-blocked in the normal CLI.
- **Policy-gated automation with approvals, review, and checkpoints** — Safe read/search/git tools run directly; file mutations become approval-gated proposals. A deterministic local code-review workflow (`/review`), a proposal lifecycle, metadata-only approval previews, and checkpoint/rewind metadata give you reviewable, reversible automation.

---

## Architecture & Tech Stack

A quick breakdown of how the system is put together:

- **Core:** Python 3.11+ (typed; `ruff` + `mypy` enforced).
- **Frameworks/Engines:** `asyncio` for the runtime; `httpx.AsyncClient` as the only runtime HTTP transport (no provider SDKs). Rich/Textual are not runtime dependencies.
- **Storage/State:** SQLite (`raiker/storage/sqlite.py`) for runtime state, tasks, sessions, approvals, checkpoints, memory candidates, and metadata records; append-only JSONL for the event log.
- **Integrations/APIs:** Local LLM runtimes via an async OpenAI-compatible adapter — **llama.cpp** server is the native local-first default (`http://127.0.0.1:8080`); Ollama, LM Studio, and vLLM are local/home-lab profiles; OpenRouter is hosted and policy/budget-gated; a deterministic provider powers offline tests.

Component-by-component responsibilities live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); design foundations are under [`docs/foundation/`](docs/foundation/).

---

## Quick Start & Installation

### Prerequisites

- **Python 3.11+** (CI covers 3.11 and 3.12).
- A POSIX shell or Windows PowerShell, plus `git`.
- *(Optional, for real local inference)* a running **llama.cpp** server (or another OpenAI-compatible local runtime) listening on `http://127.0.0.1:8080`. Not required to run the app, the tests, or the offline mock provider.

### Setup

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

This installs the package in editable mode with the dev toolchain (`pytest`, `ruff`, `mypy`) and exposes the global `raiker` command.

### Configuration

Raiker is local-first and needs **no credentials** to run. Behavior is controlled by a few environment variables and the bundled JSON config files — never by hard-coded secrets:

- `RAIKER_TUI=plain` — keep the plain line-oriented shell path (the only launchable UI).
- `RAIKER_TEST_MODE=1` — enable the deterministic test provider (test/offline only; production CLI policy blocks it with `deterministic_test_provider_requires_test_mode`).
- `--workspace <path>` — choose the workspace root that holds local runtime state (defaults to the current directory).
- Model endpoints are declared in [`config/model-profiles.json`](config/model-profiles.json) (e.g. the llama.cpp profile’s `endpoint` is `http://127.0.0.1:8080`); channel connector profiles live in [`config/channel-connectors.json`](config/channel-connectors.json).

Hosted providers (e.g. OpenRouter) require explicit network + egress + budget policy and an API key supplied through an environment variable; there is no silent fallback from local to hosted or from production to the test provider.

### Running the Application

```bash
raiker                               # interactive plain terminal client
raiker --prompt "Hello Raiker"       # submit one prompt and exit
raiker --workspace /path/to/project  # use a specific workspace root
raiker --help                        # usage
```

Inside the client, `/help` lists commands. The full CLI command surface is documented in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

---

## Project Status

The implementation control ledger is [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — read it before implementing anything. In summary:

- **All Phase 3 slices A through P are implemented, tested, and documented.** Phase 3 is `implemented_verified` only for the **safe foundation/readiness slices A-P**, and **Phase 4 memory MVP is implemented**.
- The **current launchable UI is the plain local terminal client only**. **Rich/native TUI/Desktop/Web/Dashboard/Mobile/IDE/Voice/Browser Extension/REST/API clients are Phase 8 deferred**: specified but not implemented as launchable apps.
- **Runtime execution remains disabled.** Plugin execution, graph/codemap indexing, semantic/vector memory writes, embeddings, approval execution, external channels, notifications, subagents, multi-agent teams, and remote/container/cloud execution are intentionally off; the readiness/preview surfaces for them are metadata-only and must not silently activate runtime.
- **Approval resolution is metadata-only.** `/approve` and `/deny` update one pending approval record and do not execute the approved action. Approval execution relay remains disabled/deferred.
- **Durable memory mutation is broker-governed.** `/memory-store` and `/memory-forget` are approval-required brokered requests by default; secret/credential-like content is denied before approval creation, and no CLI path bypasses policy or event logging.
- **Backend capability labels are explicit:** `implemented_read_only`, `implemented_policy_gated`, `implemented_approval_required`, `metadata_only`, `readiness_only`, `dry_run_only`, `contract_only`, `disabled_deferred`, and `test_only`.
- Phases 5–7 add governed-enterprise, channel/subagent/remote, and runtime-feature metadata/readiness foundations. Phase 8 is the planned UI/client implementation phase. Phase 9 covers advanced memory/graph foundations. Capabilities still needing implementation are tracked in [`docs/GAP_AND_TODO_ANALYSIS.md`](docs/GAP_AND_TODO_ANALYSIS.md).
- The dedicated current security architecture, trust-boundary model, and deferred-control gates are documented in [`docs/SECURITY_ARCHITECTURE.md`](docs/SECURITY_ARCHITECTURE.md).

---

## Contributing & Workflow

GitHub Actions CI runs on `pull_request` and on `push` to `main` (Python 3.11/3.12); the separate phase-status workflow is manual `workflow_dispatch`. Run the local validation gate before opening a PR:

```bash
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
raiker --help
raiker --prompt "Hello Raiker"
```

See [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md) for the full evidence checklist. Do not mark a capability `implemented_verified` without a named task, tests, and recorded validation, and never activate a disabled runtime gate through docs, tests, or code shortcuts. Open a GitHub issue for bugs, doc gaps, or scope conflicts, including the relevant phase, file path, and expected vs. actual behavior.

---

## License

Released under the MIT License. See [`LICENSE`](LICENSE).
