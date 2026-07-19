# Raiker

**Raiker** is an AI agent runtime that runs as a secure, observable, and extensible agent operating layer on your own machine, where every interface talks to the same governed core — contracts, policy, append-only events, SQLite state, approvals, and checkpoints. Its core philosophy is *no privileged interface and no silent runtime*: a capability only becomes usable once its policy, storage, audit, and acceptance work is complete (a real executor exists) — integrated capabilities are then enabled by default and governed per action (default-ask), while anything not integrated yet stays disabled and fails closed, so the documentation never runs ahead of the code. It is built for developers, home-lab operators, and governed-enterprise users who want an auditable agent platform instead of an opaque chatbot.

---

## Features

- **Governed runtime** — A deterministic gather → plan → act → verify loop (`raiker/runtime/orchestrator.py`) drives every turn through a 16-state machine, a static policy engine, a tool broker, RuntimeAuthority, and an append-only JSONL + SQLite event/state layer. Model outputs and tool calls are always untrusted proposals that must pass validation, policy, and approval.
- **Two launchable local surfaces** — `raiker` launches the line-oriented terminal client, and `raiker-web` serves the local web dashboard (`apps/web`) **and** the governed API from one loopback origin. The login screen can create separate same-server user instances; each mounts under its own path with an independent workspace, SQLite state, vault key, models, connectors, files, folders, accounts, and administrator. The dashboard adds no authority of its own: every read and mutation routes through the same governed gateway/RuntimeAuthority/broker path as the CLI. Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted REST clients are Phase 8 deferred, not active runtime surfaces. The deterministic mock/test provider is test-only and policy-blocked in the normal CLI.
- **Policy-gated automation with approvals, review, and checkpoints** — Safe read/search/git tools run directly; file mutations become approval-gated proposals. A deterministic local code-review workflow (`/review`), a proposal lifecycle, metadata-only approval previews, and checkpoint/rewind metadata give you reviewable, reversible automation.
- **Strict authority model** — RuntimeAuthority governs every mutation through capability gates, the policy engine, risk classification, and approval/risk acceptance, with four AI-executable roles, human-only roles, domain scopes, and an auditable owner-bootstrap → acting-principal → `runtime_gate_manager` chain.

- **Device-local lock screen (multi-account)** — The web dashboard is gated by local accounts (username + Argon2id/scrypt password, optional TOTP MFA) so several people can share one machine while each account's connector credentials and chat/task history stay isolated. A server-authoritative login state machine blocks governed APIs until MFA is verified; sessions are CSPRNG tokens with absolute expiry and are revoked on password/MFA change. Connector secrets are encrypted with a user-managed **Vault Key** (fail-closed if missing); MFA seeds use a separate internal key so MFA and the vault are independent. See [`docs/guide/auth.md`](docs/guide/auth.md) and [`docs/threat-models/local-lock-screen.md`](docs/threat-models/local-lock-screen.md).

---

## Architecture & Tech Stack

- **Core:** Python 3.11+ (typed; `ruff` + `mypy` enforced).
- **Runtime:** `asyncio` for the agent loop; `httpx.AsyncClient` as the only runtime HTTP transport (no provider SDKs). Rich/Textual are not runtime dependencies.
- **API + web:** FastAPI (`raiker/api/`) exposes the governed control/read/prompt/approval routes on loopback; the dashboard (`apps/web`) is a Vite + Svelte + TypeScript SPA that talks only to that local API.
- **Storage/State:** SQLite (`raiker/storage/sqlite.py`) for runtime state, tasks, sessions, approvals, checkpoints, memory candidates, and metadata records; append-only JSONL for the event log.
- **Inference:** Local runtimes use Raiker's async OpenAI-compatible adapter — **llama.cpp** is the native local default (`http://127.0.0.1:8080`), with Ollama, LM Studio, and vLLM profiles. OpenRouter, OpenAI, Gemini, and native Anthropic Messages profiles are implemented as governed hosted options. Off-machine providers remain fail-closed behind capability gates, owner egress allowlists, budget-policy metadata, and environment-only credentials. A deterministic provider powers offline tests only.

Component-by-component responsibilities live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the design foundations are under [`docs/foundation/`](docs/foundation/); the web app's design system, surfaces, and security UX are described in [`apps/web/README.md`](apps/web/README.md).

---

## Quick Start & Installation

### Prerequisites

- **Python 3.11+** (CI covers 3.11 and 3.12).
- A POSIX shell or Windows PowerShell, plus `git`.
- **Node 20+** *(only to build/develop the web dashboard; CI covers Node 20 and 22)*.
- *(Optional, for real local inference)* a running **llama.cpp** server (or another OpenAI-compatible local runtime) on `http://127.0.0.1:8080`. Not required to run the app, the tests, or the offline mock provider.

### Setup

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

This installs the package in editable mode with the dev toolchain (`pytest`, `ruff`, `mypy`) and exposes the global `raiker` and `raiker-web` commands.

### Configuration

Raiker is local and needs **no credentials** to run. Behavior is controlled by a few environment variables and the bundled JSON config files — never by hard-coded secrets:

- `RAIKER_TUI=plain` — keep the plain line-oriented shell path (the launchable terminal client; the local web dashboard is the other launchable surface).
- `RAIKER_WEB_UI_DIR=<path>` — override the built web dashboard directory `raiker-web` serves (default `apps/web/dist`).
- `--workspace <path>` — choose the workspace root that holds local runtime state (defaults to the current directory).
- Model endpoints are declared in [`config/model-profiles.json`](config/model-profiles.json); channel connector profiles live in [`config/channel-connectors.json`](config/channel-connectors.json).

There is no silent fallback from local to hosted, or from production to the test provider.

### Choosing and adding a model (required to use Raiker as an agent)

Raiker does **not** ship with a model — it talks to a model server or API selected by the owner. Until you point it at a reachable model, prompts return `model_unavailable: provider_connection_failed` (by design — it never fabricates output). Model profiles live in [`config/model-profiles.json`](config/model-profiles.json) and are inspected/selected from the CLI or web dashboard.

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

**llama.cpp, Ollama, and LM Studio work out of the box.** The built-in `raiker-local-llama-cpp` profile expects a llama.cpp server serving `local-gguf` at `:8080`. For **Ollama** and **LM Studio**, selecting the profile **auto-detects the served model** from the server's `/v1/models` endpoint when exactly one model is loaded. If several are loaded, pick one explicitly:

```text
/model use --provider ollama --model llama3.1
```

The selected model is remembered and is what subsequent prompts run on. If the server is not reachable, the command reports the failure and leaves the existing selection unchanged; it never fabricates a model.

**3. (Optional) Add or edit a model profile** by editing `config/model-profiles.json`: copy an entry and set the endpoint, model identifiers, and capability flags. Supported providers include `llama.cpp`, `ollama`, `lm-studio`, `vllm`, `openai-compatible`, `openrouter`, `anthropic`, `openai`, and `gemini` (the `mock`/`test` providers are test-only and policy-blocked in normal operation). Re-launch Raiker to pick up file changes.

**Hosted and private-network model inference is implemented but fail-closed.** Before Raiker contacts an off-machine model, the owner must enable the corresponding `hosted_model_runtime` or `private_network_model_runtime` capability through the governed control plane, add the endpoint hostname to `RAIKER_MODEL_EGRESS_ALLOWLIST`, and provide the profile's API key environment variable where required (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`). Keys are never stored in model profiles or event logs. Raiker currently has no built-in secret store, and enabling model inference does not turn Raiker itself into a hosted or multi-user service.

### Running the terminal client

```bash
raiker                               # interactive plain terminal client
raiker --prompt "Hello Raiker"       # submit one prompt and exit
raiker --workspace /path/to/project  # use a specific workspace root
raiker --help                        # usage
```

Inside the client, `/help` lists commands. The full CLI command surface is documented in [`docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

### Running the local web dashboard (one command)

The local web dashboard is the second launchable surface (single-user, `127.0.0.1` only). Build the SPA once, then `raiker-web` serves **both** the governed API and the dashboard from the same origin (no second process, no CORS):

```bash
npm --prefix apps/web install        # first time only
npm --prefix apps/web run build      # produce apps/web/dist
raiker-web --workspace .             # serves API + dashboard on http://127.0.0.1:8765
```

Open `http://127.0.0.1:8765`. The dashboard surfaces governed views (sessions, turns, events, checkpoints, tasks, capabilities, runtime mode, models, diagnostics), the live gather → plan → act → verify prompt/turn stream, the approval queue, Connector Store, task creation with stored-only scheduling, step-up-gated Security Settings, and a STOP switch. It adds no authority of its own — every read and mutation goes through the same governed path as the CLI, and **approval resolution is metadata-only** (recording a decision never executes the action). If the SPA is not built, `raiker-web` serves the API only and prints a build hint. For hot-reload development, run `npm --prefix apps/web run dev` (it proxies `/api` to `raiker-web`).

---

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

## Project Status

Raiker has a **production-ready local single-user runtime foundation** with persisted owner bootstrap, acting-principal resolution, governed runtime mode activation, governed capability gate transitions, strict RuntimeAuthority enforcement, audit events, validators, and end-to-end tests — surfaced by both the terminal client and the local web dashboard.

The implementation control ledger is [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) — read it before implementing anything. In summary:

### Readiness table

| Area | Status | Scope |
|---|---|---|
| Runtime enablement candidate | Completed | Strict non-allow blocking, role revoke governed, capability gate per action, risk acceptance, validator coverage |
| Controlled runtime mode activation | Implemented | Runtime mode state and capability gate state are persisted, governed, auditable, and reversible |
| Local single-user production hardening | Implemented | First-run owner bootstrap, persisted owner principal, acting-principal resolution, runtime-gate-manager authorization, recovery flow |
| `production_ready_local_single_user_runtime` | Ready | Local single-user terminal/runtime foundation |
| Control plane + governed API | Implemented | `RuntimeControlService` (typed DTOs) and a FastAPI surface with session→principal auth let an out-of-process UI view and govern-flip gates |
| Local web dashboard (`apps/web`) | Implemented | Launchable single-user dashboard over the governed API: read-only views, prompt/turn stream, approval queue (metadata-only), step-up-gated Security Settings, diagnostics, STOP |
| Real local executors | Implemented (integrated + governed) | Exactly `REAL_EXECUTOR_CAPABILITIES`: Tier 1, Tier 2, Tier 3 graph/semantic/vector/model-provider, orchestration/channel/container/scheduled/model/plugin slices, and local email/calendar/reminder stores. Integrated gates default `enabled_runtime` but AI-proposed actions default to `ask` and independent allowlists/threat-acks remain fail-closed. See [`docs/RUNTIME_EXECUTORS_SPEC.md`](docs/RUNTIME_EXECUTORS_SPEC.md) |
| Plugins / vector+embedding / hosted/private model runtime | Implemented (bounded/governed slices) | Real executors exist for the documented bounded slices; no unrestricted plugin import/network, no secret store, and provider egress/API-key controls fail closed. |
| Shell/network executors flippable but require confirm | Implemented (Tier 2) | Sandbox + egress allowlist + threat-model ack + human confirmation token to enable |
| Container + external channels | Implemented (bounded/governed slices) | Local container execution and one webhook channel/approval relay are real governed executors with independent allowlists. |
| Remote/cloud command execution | Fail-closed (not implemented) | No real executor; activation blocked (`no_executor`). |
| Email/calendar/reminder stores | Implemented (local-only) | Local stores/drafts only; no external send/sync/invites. |
| Finance/investment/medical/pregnancy/CCTV/home-security/hardware runtime | Fail-closed (not implemented) | No real executor; fails closed pending per-domain threat models. |
| Hosted/multi-user/cloud runtime | Future phase | Local single-user readiness does not cover hosted or multi-user deployment |

### Production-ready local runtime criteria (completed)

1. First-run owner bootstrap exists.
2. Owner bootstrap creates persisted user, principal, and roles.
3. Runtime/capability gate changes require persisted owner or `runtime_gate_manager` authority.
4. Synthetic CLI runtime-gate-manager authority is removed from production paths.
5. Acting principal resolution is implemented.
6. Owner recovery/break-glass flow is implemented and audited.
7. AI principals cannot activate runtime modes or capability gates (nor interrupt tasks or resolve approvals).
8. `admin_mutation` and `role_mutation` remain disabled by default and require explicit owner/gate-manager activation.
9. Deferred dangerous runtimes remain disabled.
10. Runtime/capability transitions are reversible.
11. Runtime-readiness command and `/api/diagnostics` report local production readiness accurately.
12. Validators prevent production-readiness overclaims.
13. End-to-end local runtime workflow is tested (CLI and governed API).
14. Broad runtime execution remains deferred capability work.

### Current limitations

- Real executors are exactly the capabilities in `REAL_EXECUTOR_CAPABILITIES`; those integrated gates default `enabled_runtime` and are governed per action (decision mode default `ask`).
- No-executor capabilities fail closed (`not_implemented` / `activation_blocked:no_executor`) and cannot be flipped to a working state; this includes finance/investment/medical/pregnancy/CCTV/home-security/hardware and remote/cloud command execution.
- Email/calendar/reminder capabilities are local-only stores/drafts; they do not send email, sync external calendars, create invites, or call external reminder services.
- Tier 2 executors (shell/process/network/web-fetch) require a threat-model ack and a human confirmation token to enable.
- Finance/investment/medical/pregnancy/CCTV/home-security/hardware runtime remains disabled/deferred; email/calendar/reminder are local-only stores/drafts.
- The web dashboard is single-user and loopback-only; there is no secret/credential store (secret storage is deferred).
- Hosted/private **model inference** is available only through its bounded governed gates and owner configuration. Hosted/multi-user deployment of the Raiker application itself remains future work; current production readiness applies only to the local single-user runtime.

### Detailed status

- **All Phase 3 slices A through P are implemented, tested, and documented.** Phase 3 is `implemented_verified` only for the **safe foundation/readiness slices A-P**, and **Phase 4 memory MVP is implemented**.
- The **launchable local UIs are the plain local terminal client and the local web dashboard** (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only). The web dashboard surfaces read-only governed views, the same governed prompt/turn/approval/runtime-mutation flows as the CLI (approval resolution stays metadata-only), and a step-up-gated Security Settings; it adds no authority of its own and talks only to the local governed API. **Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser-Extension, and hosted/multi-user REST clients remain Phase 8 deferred**: specified but not implemented as launchable apps.
- **Approval resolution is metadata-only.** `/approve`, `/deny`, and the dashboard's approval queue update one pending approval record and do not execute the approved action. Approval execution relay remains disabled/deferred.
- **Durable memory mutation is broker-governed.** `/memory-store` and `/memory-forget` are approval-required brokered requests by default; secret/credential-like content is denied before approval creation, and no CLI or API path bypasses policy or event logging.
- **Backend capability labels are explicit:** `implemented_read_only`, `implemented_policy_gated`, `implemented_approval_required`, `metadata_only`, `readiness_only`, `dry_run_only`, `contract_only`, `disabled_deferred`, and `test_only`.
- **Runtime Authority / Action Router** (`raiker/runtime/authority/`) governs all mutation actions through capability gates, policy engine, risk classification, approval/risk acceptance, and event logging. It enforces four AI-executable roles (`assistant`, `automation`, `operator`, `developer`), seven human-only roles, 16 domain scopes, and risk acceptance with expiry.
- **Capability registry** is expanded to 53 capabilities across all domain runtimes. Integrated capabilities (those with a real executor, `REAL_EXECUTOR_CAPABILITIES`) default to `enabled_runtime` and are governed per action (decision mode, default `ask`); capabilities that are not integrated yet default to `disabled` and fail closed. The `ALL_CAPABILITIES` and `RUNTIME_DOMAIN_CAPABILITIES` sets are defined in `raiker/phase_gates.py`.
- Phases 5–7 add governed-enterprise, channel/subagent/remote, and runtime-feature metadata/readiness foundations. Phase 8 is the planned UI/client implementation phase. Phase 9 covers advanced memory/graph foundations. Capabilities still needing implementation are tracked in [`docs/GAP_AND_TODO_ANALYSIS.md`](docs/GAP_AND_TODO_ANALYSIS.md).
- The dedicated current security architecture, trust-boundary model (including the web dashboard), and deferred-control gates are documented in [`SECURITY.md`](SECURITY.md) and [`docs/SECURITY_ARCHITECTURE.md`](docs/SECURITY_ARCHITECTURE.md).

---

## Contributing & Workflow

GitHub Actions CI runs on `pull_request` and on `push` to `main` (Python 3.11/3.12 and Node 20/22); the separate phase-status workflow is manual `workflow_dispatch`. Run the local validation gate before opening a PR:

```bash
# Python
python -m ruff check .
python -m mypy raiker apps tests
python -m pytest
python scripts/validate_phase_status.py
python scripts/validate_repo_truthfulness.py
python scripts/licensing_check.py --sbom artifacts/licensing/raiker.spdx.json
raiker --help
raiker --prompt "Hello Raiker"

# Web dashboard (apps/web)
npm --prefix apps/web run lint
npm --prefix apps/web run check       # svelte-check / tsc
npm --prefix apps/web run test        # vitest
npm --prefix apps/web run build
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for submission and DCO terms and [`docs/LOCAL_VALIDATION_GATE.md`](docs/LOCAL_VALIDATION_GATE.md) for the full evidence checklist. Do not mark a capability `implemented_verified` without a named task, tests, and recorded validation, and never activate a disabled runtime gate through docs, tests, or code shortcuts. Open a GitHub issue for bugs, doc gaps, or scope conflicts, including the relevant phase, file path, and expected vs. actual behavior.

---

## License

Current Raiker versions are released under the [Apache License 2.0](LICENSE).
See [NOTICE](NOTICE), [CONTRIBUTING.md](CONTRIBUTING.md), and the
[licensing policy](docs/licensing/LICENSING_POLICY.md). Earlier MIT releases
remain available under their original licence terms.
