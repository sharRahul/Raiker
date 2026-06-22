# Raiker

**Raiker** is an AI agent runtime that runs as a secure, observable, and extensible agent operating layer on your own machine, where every interface talks to the same governed core — contracts, policy, append-only events, SQLite state, approvals, and checkpoints. Its core philosophy is *no privileged interface and no silent runtime*: capabilities stay disabled until their policy, storage, audit, and acceptance work is complete, so the documentation never runs ahead of the code. It is built for developers, home-lab operators, and governed-enterprise users who want an auditable agent platform instead of an opaque chatbot.

---

## Features

- **Governed runtime** — A deterministic gather → act → verify loop (`raiker/runtime/orchestrator.py`) drives every turn through a 16-state machine, a static policy engine, a tool broker, and an append-only JSONL + SQLite event/state layer. Model outputs and tool calls are always untrusted proposals that must pass validation, policy, and approval.
- **Two launchable local surfaces** — `raiker` launches the line-oriented terminal client, and `raiker-web` serves the local web dashboard (`apps/web`) + governed API from one loopback origin (single-user, `127.0.0.1` only). Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST clients are Phase 8 deferred, not active runtime surfaces. The deterministic mock/test provider is test-only and policy-blocked in the normal CLI.
- **Policy-gated automation with approvals, review, and checkpoints** — Safe read/search/git tools run directly; file mutations become approval-gated proposals. A deterministic local code-review workflow (`/review`), a proposal lifecycle, metadata-only approval previews, and checkpoint/rewind metadata give you reviewable, reversible automation.

---

## Architecture & Tech Stack

A quick breakdown of how the system is put together:

- **Core:** Python 3.11+ (typed; `ruff` + `mypy` enforced).
- **Frameworks/Engines:** `asyncio` for the runtime; `httpx.AsyncClient` as the only runtime HTTP transport (no provider SDKs). Rich/Textual are not runtime dependencies.
- **Storage/State:** SQLite (`raiker/storage/sqlite.py`) for runtime state, tasks, sessions, approvals, checkpoints, memory candidates, and metadata records; append-only JSONL for the event log.
- **Integrations/APIs:** Local LLM runtimes via an async OpenAI-compatible adapter — **llama.cpp** server is the native local default (`http://127.0.0.1:8080`); Ollama, LM Studio, and vLLM are local/home-lab profiles; OpenRouter is hosted and policy/budget-gated; a deterministic provider powers offline tests.

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

Raiker is local and needs **no credentials** to run. Behavior is controlled by a few environment variables and the bundled JSON config files — never by hard-coded secrets:

- `RAIKER_TUI=plain` — keep the plain line-oriented shell path (the launchable terminal client; the local web dashboard is the other launchable surface).
- `RAIKER_TEST_MODE=1` — enable the deterministic test provider (test/offline only; production CLI policy blocks it with `deterministic_test_provider_requires_test_mode`).
- `--workspace <path>` — choose the workspace root that holds local runtime state (defaults to the current directory).
- Model endpoints are declared in [`config/model-profiles.json`](config/model-profiles.json) (e.g. the llama.cpp profile’s `endpoint` is `http://127.0.0.1:8080`); channel connector profiles live in [`config/channel-connectors.json`](config/channel-connectors.json).

There is no silent fallback from local to hosted, or from production to the test provider.

### Choosing and adding a model (required to use Raiker as an agent)

Raiker does **not** ship with a model — it talks to an OpenAI-compatible inference server you run
locally. Until you point it at a reachable model, prompts return `model_unavailable:
provider_connection_failed` (by design — it never fabricates output). Model profiles live in
[`config/model-profiles.json`](config/model-profiles.json) and are inspected/selected from the CLI.

**1. Run a local model server**, e.g. one of:

- **llama.cpp** (native default): serve a GGUF as model name `local-gguf` on `http://127.0.0.1:8080`.
- **Ollama**: `ollama serve` (OpenAI-compatible endpoint `http://127.0.0.1:11434/v1`).
- **LM Studio**: start its local server on `http://127.0.0.1:1234/v1`.

**2. Select the profile in the terminal client:**

```text
/providers                              # list providers and profiles
/models                                 # list model profiles
/model use raiker-local-llama-cpp       # select the built-in llama.cpp profile
/model use ollama-local-openai-compatible   # Ollama (auto-detects the served model)
/model use lm-studio-local-openai-compatible # LM Studio (auto-detects the served model)
/model health                           # confirm the server is reachable
/model current                          # show the active profile
```

**llama.cpp, Ollama, and LM Studio work out of the box.** The built-in `raiker-local-llama-cpp`
profile expects a llama.cpp server serving `local-gguf` at `:8080`. For **Ollama** and **LM Studio**,
selecting the profile **auto-detects the served model** from the server's `/v1/models` endpoint when
exactly one model is loaded. If several models are loaded, pick one explicitly:

```text
/model use --provider ollama --model llama3.1
```

The selected model is remembered and is what subsequent prompts actually run on. If the server isn't
reachable, the command says so and leaves the native llama.cpp default active (it never fabricates a
model).

**3. (Optional) Add or edit a model profile** by editing `config/model-profiles.json`: copy an entry
and set the `endpoint` and capability flags. Supported `provider` values are `llama.cpp`, `ollama`,
`lm-studio`, `vllm`, and `openai-compatible` (the `mock`/`test` providers are test-only and
policy-blocked in the normal CLI). Re-launch `raiker` to pick up file changes.

**Hosted / cloud models are not enabled in the current build.** The OpenRouter (hosted) and vLLM
(home-lab / private-network) profiles exist as configuration/contract only: the runtime policy that
would permit hosted, policy-gated, or private-network providers is not turned on anywhere, so
selecting them fails closed (e.g. `hosted_provider_requires_explicit_policy`,
`provider_requires_explicit_policy_approval`). A governed enablement path and secret storage for
API keys are deferred work — until then, run Raiker against a **local** model. (Hosted profiles
declare `requires_network` + `requires_egress_policy` + `requires_budget_policy` and read their key
from an environment variable such as `OPENROUTER_API_KEY`; the key is never stored by Raiker and is
redacted from logs.)

### Running the Application

```bash
raiker                               # interactive plain terminal client
raiker --prompt "Hello Raiker"       # submit one prompt and exit
raiker --workspace /path/to/project  # use a specific workspace root
raiker --help                        # usage
```

#### Local web dashboard (one command)

The local web dashboard is the second launchable surface (single-user, `127.0.0.1` only). Build the
SPA once, then `raiker-web` serves both the governed API and the dashboard from the same origin:

```bash
npm --prefix apps/web install        # first time only
npm --prefix apps/web run build      # produce apps/web/dist
raiker-web --workspace .             # serves API + dashboard on http://127.0.0.1:8765
```

Open `http://127.0.0.1:8765`. The dashboard adds no authority of its own — every read and mutation
goes through the same governed gateway/RuntimeAuthority/broker path as the CLI, and approval
resolution stays metadata-only. If the SPA is not built, `raiker-web` serves the API only. For
hot-reload development, run `npm --prefix apps/web run dev` (it proxies `/api` to `raiker-web`).

Inside the client, `/help` lists commands. The full CLI command surface is documented in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

---

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

## Project Status

Raiker now has a **production-ready local single-user runtime foundation** with persisted owner bootstrap, acting-principal resolution, governed runtime mode activation, governed capability gate transitions, strict RuntimeAuthority enforcement, audit events, validators, and end-to-end tests.

The implementation control ledger is [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — read it before implementing anything. In summary:

### Readiness table

| Area | Status | Scope |
|---|---|---|
| Runtime enablement candidate | Completed | Strict non-allow blocking, role revoke governed, capability gate per action, risk acceptance, validator coverage |
| Controlled runtime mode activation | Implemented | Runtime mode state and capability gate state are persisted, governed, auditable, and reversible |
| Local single-user production hardening | Implemented | First-run owner bootstrap, persisted owner principal, acting-principal resolution, runtime-gate-manager authorization, recovery flow |
| `production_ready_local_single_user_runtime` | Ready | Local single-user terminal/runtime foundation |
| Control plane + API | Implemented | `RuntimeControlService` (typed DTOs) and a FastAPI surface with session→principal auth let an out-of-process UI view and govern-flip gates |
| Real local executors | Implemented (governed-flippable) | Tier 1 (approval relay, file write, patch apply, memory write/forget), Tier 2 (shell/process/web-fetch/network, sandboxed + egress-allowlisted), Tier 3 (graph indexing, semantic memory). See [`docs/RUNTIME_EXECUTORS_SPEC.md`](docs/RUNTIME_EXECUTORS_SPEC.md) |
| Plugins / vector+embedding / hosted-model runtime | Fail-closed (not implemented) | Activation blocked (`no_executor`); flipping does not fake success |
| Shell/network executors flippable but require confirm | Implemented (Tier 2) | Sandbox + egress allowlist + threat-model ack + human confirmation token to enable |
| Remote/container/cloud + external channels | Fail-closed (not implemented) | No real executor; fails closed until isolation/egress/budget work lands |
| Email/calendar/finance/medical/CCTV runtime | Fail-closed (not implemented) | No real integration; fails closed (never fabricates success) pending per-domain threat models |
| Hosted/multi-user/cloud runtime | Future phase | Local single-user readiness does not cover hosted or multi-user deployment |

### Production-ready local runtime criteria (completed)

1. First-run owner bootstrap exists.
2. Owner bootstrap creates persisted user, principal, and roles.
3. Runtime/capability gate changes require persisted owner or `runtime_gate_manager` authority.
4. Synthetic CLI runtime-gate-manager authority is removed from production paths.
5. Acting principal resolution is implemented.
6. Owner recovery/break-glass flow is implemented and audited.
7. AI principals cannot activate runtime modes or capability gates.
8. `admin_mutation` and `role_mutation` remain disabled by default and require explicit owner/gate-manager activation.
9. Deferred dangerous runtimes remain disabled.
10. Runtime/capability transitions are reversible.
11. Runtime-readiness command reports local production readiness accurately.
12. Validators prevent production-readiness overclaims.
13. End-to-end local runtime workflow is tested.
14. Broad runtime execution remains deferred capability work.

### Current limitations

- Real executors exist only for the local Tier 1–3 set in `REAL_EXECUTOR_CAPABILITIES`; everything else fails closed (`not_implemented`) and cannot be flipped to a working state.
- Plugins, vector/embedding and hosted/private model runtime, external channels, remote/container/cloud execution, scheduled routines, and all sensitive personal/physical domains (email/calendar/finance/medical/cctv/home-security/hardware) are not implemented yet — flipping them is blocked at activation.
- Tier 2 executors (shell/process/network/web-fetch) require a threat-model ack and a human confirmation token to enable.
- Email/calendar/finance/medical/CCTV runtime remains disabled/deferred.
- Hosted/multi-user/cloud runtime is future implementation work.
- Current production readiness applies only to local single-user runtime.

### Detailed status

- **All Phase 3 slices A through P are implemented, tested, and documented.** Phase 3 is `implemented_verified` only for the **safe foundation/readiness slices A-P**, and **Phase 4 memory MVP is implemented**.
- The **launchable local UIs are the plain local terminal client and the local web dashboard** (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only). The web dashboard surfaces read-only governed views, the same governed prompt/turn/approval/runtime-mutation flows as the CLI (approval resolution stays metadata-only), and a step-up-gated Security Settings; it adds no authority of its own and talks only to the local governed API. **Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser-Extension, and hosted/multi-user REST clients remain Phase 8 deferred**: specified but not implemented as launchable apps.
- **Approval resolution is metadata-only.** `/approve` and `/deny` update one pending approval record and do not execute the approved action. Approval execution relay remains disabled/deferred.
- **Durable memory mutation is broker-governed.** `/memory-store` and `/memory-forget` are approval-required brokered requests by default; secret/credential-like content is denied before approval creation, and no CLI path bypasses policy or event logging.
- **Backend capability labels are explicit:** `implemented_read_only`, `implemented_policy_gated`, `implemented_approval_required`, `metadata_only`, `readiness_only`, `dry_run_only`, `contract_only`, `disabled_deferred`, and `test_only`.
- **Runtime Authority / Action Router** (`raiker/runtime/authority/`) governs all mutation actions through capability gates, policy engine, risk classification, approval/risk acceptance, and event logging. It enforces four AI-executable roles (`assistant`, `automation`, `operator`, `developer`), seven human-only roles, 16 domain scopes, and risk acceptance with expiry.
- **Capability registry** is expanded to 47 capabilities across all domain runtimes, all default-disabled. The `ALL_CAPABILITIES` and `RUNTIME_DOMAIN_CAPABILITIES` sets are defined in `raiker/phase_gates.py`.
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
