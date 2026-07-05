# Session Handoff — pick up here

> Purpose: let any builder (Claude, Codex, or human) resume the Raiker goal
> without re-deriving state. Read this + `docs/IMPLEMENTATION_STATUS.md` first.
> Update this file at the end of every working session.

## Goal (unchanged)

Make Raiker a full-fledged, secure AI agent that can connect to **any**
backend LLM — local (llama.cpp/Ollama/LM Studio), home-lab (vLLM), or hosted
API provider (Anthropic/OpenAI/Gemini/OpenRouter) — with the choice belonging
to the user, and every capability governed, default-disabled, and fail-closed.

Be mind full of token usage if needed do it in batches. Keep committing after every phase and then push to origin main before the token limit is ended for the session. Plan and implement it in such a way that anyone can pick it up after your session token are over even though the goal is not complete. In next session review where you are and then start from next phase.

## State as of 2026-07-05 (session end)

> **Where this session's work lives (read first):** Phase 4 **slice 14**
> (plugin **code runtime** — `plugin_runtime_cap`) is on branch
> `claude/handoff-document-review-jusao0`, started from `origin/main` after PR #94
> (slice 13, Ed25519) merged (merge commit `deaab72`). Slice 13 and everything
> before it are merged — do **not** re-do them.
>
> **Environment unblock (still relevant):** the "Ed25519/cffi bindings panic on
> import" blocker is a **missing `cffi`** (`ModuleNotFoundError: No module named
> '_cffi_backend'`). Fix locally with `pip install cffi` after
> `pip install -e ".[dev]"`. CI's fresh-runner install pulls `cffi` transitively.
> This session's runtime uses `/usr/local/bin/python3` (3.11); `pip install -e
> ".[dev]"` then `pip install cffi` gives a green full suite.

Previous pushed anchors (earlier sessions): slice 13 merge `deaab72`, slice 8
`c8ce3d5`, slice 7 `c571c9c`; config cwd fallback `29ec83a`.

Full suite green after slice 14: **1142 passed, 1 warning**; ruff clean, mypy
clean on changed sources (remaining mypy output is environmental missing-stub
noise for `pytest`/`fastapi`/`httpx`/`cryptography` plus one pre-existing
`test_runtime_authority.py` item), and all five `scripts/validate_*.py`
validators passed.

- **Phase 4 slices 1–8 done.** Real governed executors now include
  `hosted_model_runtime` + `private_network_model_runtime` (slice 7): the
  production `ModelRouter` derives provider policy from the persisted
  capability gates, and every off-machine provider construction re-checks the
  owner egress allowlist `RAIKER_MODEL_EGRESS_ALLOWLIST` (empty = fail
  closed). See `docs/threat-models/hosted-models.md`.
- **Provider breadth (slice 8):** native Anthropic Messages adapter
  (`raiker/models/providers/anthropic_messages.py`, raw httpx, no SDK),
  hosted profiles `anthropic-hosted` (claude-opus-4-8), `openai-hosted`,
  `gemini-hosted-openai-compatible`; generic `hosted_api_key_missing`
  fail-closed check for all remote-hosted profiles.
- **E2E verified on a real local model:** `/model use --provider ollama
  --model gemma4:31b-cloud` + `raiker --prompt` completed a live gateway turn
  (events + checkpoint persisted). Use `gemma4:31b-cloud` for future manual
  Ollama testing (owner preference — faster).
- Hosted profiles are offline/mock-verified only (`implemented_unverified`
  against live keys).
- **Config packaging follow-up complete:** `ModelProfileRegistry.load()` and
  `ConnectorRegistry.load()` keep workspace-local `config/` overrides, then
  fall back to bundled `raiker.config` JSON resources. The wheel now includes
  `raiker/config/model-profiles.json` and
  `raiker/config/channel-connectors.json`; focused tests cover foreign cwd,
  packaged-resource fallback, and resource drift.
- **Ollama tool calls enabled and live-verified:** `ollama-local-openai-compatible`
  now advertises native OpenAI tool calls with text-JSON fallback
  (`supports_tool_calls=true`, `tool_call_mode=native_or_text_json`). Live
  localhost validation against `qwen3.5:9b` returned a native `list_directory`
  tool call, and Raiker's provider factory parsed the arguments as
  `{"path": "."}`.
- **Web dashboard parity for hosted models complete:** `/api/models`,
  `apps/web` Models, and Security Settings now surface hosted/private model
  gate state, off-machine profile count, and whether
  `RAIKER_MODEL_EGRESS_ALLOWLIST` is configured. The UI remains read-only for
  this status and never displays allowlist values or API keys.
- **Plugin manifest install slice complete:** `plugin_install` is now a real
  governed executor for local manifest validation + install-record creation
  only. It requires the default-disabled gate, `local_single_user_runtime`, a
  human `runtime_gate_manager`, confirmation token, and
  `docs/threat-models/plugins.md` ack. It verifies checksum, requires a
  signature presence marker, allows only safe read-only permissions, and writes
  `plugin_install_records`.
- **Plugin brokered read-only execution slice complete:** `plugin_execution_cap`
  is now a real governed executor only for installed plugins invoking
  `read_file`, `list_directory`, `glob`, or `grep` through `ToolBroker` and
  `PolicyEngine`. It requires `docs/threat-models/plugin-execution.md` ack and
  records `plugin_execution_records`. It does not import plugin code, run
  scripts, start processes, open network connections, write files, or activate
  hooks/MCP/LSP/monitors/panels.
- **Plugin revocation slice complete (slice 10):** `plugin_revocation_cap` is now
  a real governed executor and the fail-closed off-switch for the install/
  execution slices. A HUMAN `runtime_gate_manager` revokes an installed plugin
  (requires the default-disabled gate, `local_single_user_runtime`, a
  `docs/threat-models/plugin-revocation.md` ack, and a confirmation token). It
  flips the latest install record's status `installed` → `revoked` via
  `SQLiteStore.revoke_plugin_install_record` (never deletes records, edits
  permissions, or runs plugin code). After revocation, `plugin_execution_cap`
  fails closed with `plugin_revoked` before any broker call. Second revocation
  is an idempotent no-op (`plugin_already_revoked`). Runtime artifacts stay
  metadata-only (no reason label or permission payload leaked). Evidence:
  `tests/test_phase_4_plugin_revocation_runtime.py`.
- **Plugin dependency controls slice complete (slice 11):** the governed
  `plugin_install` path now validates declared manifest `dependencies` statically
  and fails closed before writing an install record. Each dependency must be an
  exact `(plugin_id, version)` pin (ranges/wildcards/`latest` → `dependency_unpinned`)
  and each dependency plugin id must be on the owner allowlist
  `RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST` (comma-separated; empty = fail closed for
  any declared dependency → `dependency_not_allowlisted`). A dependency-free
  manifest is unaffected. Pure static validation in `raiker/plugins/dependencies.py`
  wired through `plan_plugin_registration`; no download, transitive resolution, or
  install. Evidence: `tests/test_phase_4_plugin_dependency_controls.py`.
- **Plugin signature verification slice complete (slice 12):** the governed
  `plugin_install` path now cryptographically verifies the manifest `signature`
  when the owner sets `RAIKER_PLUGIN_SIGNING_KEY` — the `signature` must be a
  valid HMAC-SHA256 over the canonical manifest body (same body the checksum
  covers) or the install fails closed (`signature_invalid` /
  `no_signature_in_manifest`, no record written). With no key set, the presence
  marker remains for local dev (unchanged, existing tests green). Trust-model
  limit: symmetric owner-held key (integrity + authenticity), complemented by the
  asymmetric Ed25519 scheme in slice 13.
  `raiker/plugins/verify.py` (`plugin_signing_key`, `expected_plugin_signature`,
  upgraded `verify_plugin_signature`). Evidence:
  `tests/test_phase_4_plugin_signature_verification.py`.
- **Ed25519 asymmetric signature verification slice complete (slice 13):** the
  governed `plugin_install` path now also verifies an asymmetric supply-chain
  signature when the owner sets `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (hex 32-byte
  public key) — the manifest `supply_chain.ed25519_signature` must be a valid
  Ed25519 signature (hex) over the same canonical body the checksum/HMAC cover,
  verified against that owner-trusted public key, or the install fails closed
  (`asymmetric_signature_invalid` / `no_asymmetric_signature_in_manifest` /
  `asymmetric_public_key_invalid` / `asymmetric_backend_unavailable` — never fails
  open) and writes no record. Unset → skipped (`asymmetric_not_configured`), so
  existing manifests are unaffected. Author signs off-machine with a private key
  Raiker never holds; owner configures only the trusted public key. HMAC and
  Ed25519 are enforced independently. `raiker/plugins/verify.py`
  (`plugin_ed25519_public_key`, `ed25519_signature_hex`,
  `verify_plugin_asymmetric_signature`, wired into `validate_supply_chain`);
  `cryptography>=41` added to `pyproject.toml` dependencies. Evidence:
  `tests/test_phase_4_plugin_asymmetric_signature.py`.
- **Plugin code runtime slice complete (slice 14, done this session):** the first
  capability that runs **arbitrary plugin code**. `plugin_runtime_cap` is a real
  governed executor (`PluginRuntimeExecutor` in
  `raiker/runtime/executors/tier4_plugins.py`) that runs an installed plugin's
  declared entrypoint as a **bounded subprocess** through the shared sandbox
  (`run_command`): interpreter allowlist (`python3`/`python`/`node`),
  workspace-scoped script path, default 30s / max 120s timeout, 200 KB output
  caps, argv-only (no shell). It fails closed unless the plugin has a non-revoked
  `installed` record **and** the owner names it in `RAIKER_PLUGIN_RUNTIME_ALLOWLIST`
  (empty = fail closed) — the owner grant, not the manifest, authorizes code
  execution (install still only records safe read-only perms). Fail-closed reason
  codes: `plugin_not_installed`, `plugin_revoked`,
  `plugin_runtime_not_allowlisted`, `interpreter_not_allowed:*`,
  `outside_workspace:entrypoint`, `entrypoint_not_found`, `too_many_args`,
  `plugin_runtime_sandbox:*`, `plugin_runtime_exit:<code>`. Artifacts are
  metadata-only (`output_redacted=true`); stdout/stderr never leak into events.
  Every attempt writes a `plugin_execution_records` row (new id prefix `plgrt_`).
  **Isolation limit (honest):** posture equals `shell_execution`/`process_execution`
  — separate process + resource/timeout bounds, but **no** in-process import
  isolation and **no** network-namespace jail (ambient host network); the
  `container_execution_cap` path is the stronger-isolation option. Threat model:
  `docs/threat-models/plugin-runtime.md`. Evidence:
  `tests/test_phase_4_plugin_runtime.py`.

## How a user turns on a hosted provider (for reference / docs work)

1. `/runtime-mode activate local_single_user_runtime` (human owner).
2. Record a threat-model ack for `hosted_model_runtime`
   (`docs/threat-models/hosted-models.md`) and enable the gate with a
   confirmation token.
3. Set `RAIKER_MODEL_EGRESS_ALLOWLIST=api.anthropic.com` (or provider host)
   and the provider key env (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
   `GEMINI_API_KEY` / `OPENROUTER_API_KEY`).
4. `/model use anthropic-hosted` (or `--provider openai --model gpt-4o`, …).

## Next work, in priority order

1. **Config path resolution bug - completed in this session.**
   `ModelProfileRegistry.load()` / `ConnectorRegistry.load()` read
   `config/*.json` relative to cwd — installed `raiker` fails outside the
   repo root (`FileNotFoundError`). Add a package-relative fallback
   (`importlib.resources` or anchored on `raiker.__file__`), ship the JSON as
   package data, and add a test that loads the registry from a foreign cwd.
   Implemented with bundled `raiker.config` resources, drift tests, and a
   wheel-content check; do not redo this item unless it regresses.
2. **Live hosted-provider verification.** With an operator key, run one
   governed turn on `anthropic-hosted` and flip its status note from
   `implemented_unverified` to verified. No code expected — evidence only.
3. **Tool calls on Ollama models - completed in this session.** `ollama-local-openai-compatible` shipped
   `supports_tool_calls: false` / `text_json`. Modern Ollama models (qwen3,
   gemma4) support native OpenAI tool calls — test against the live server,
   then flip the profile (or add per-model detection) so the agentic loop can
   act with local models, not just llama.cpp.
   Implemented as `supports_tool_calls=true`, `tool_call_mode=native_or_text_json`,
   with focused tests and live localhost evidence against `qwen3.5:9b`.
4. **Plugin runtime promotion (Tier 4).** Completed so far: `plugin_install`,
   brokered read-only `plugin_execution_cap`, `plugin_revocation_cap` (the
   off-switch, slice 10), install-time dependency controls (slice 11), HMAC
   manifest signature verification (slice 12), asymmetric Ed25519 signature
   verification (slice 13), and **bounded-subprocess plugin code runtime
   `plugin_runtime_cap` (slice 14, done this session)** — the first capability
   that actually runs plugin code, gated on an owner plugin allowlist +
   interpreter allowlist + workspace-scoped entrypoint. Still deferred, in
   likely-next order: (a) **in-process import isolation** and a
   **network-namespace jail** for plugin code (today `plugin_runtime_cap` shares
   `shell_execution`'s posture — ambient host network; the
   `container_execution_cap` path is the stronger option and a natural home for
   a "run plugin entrypoint inside a no-network container image" slice);
   (b) **runtime permission enforcement** finer than the owner allowlist (e.g.
   per-plugin filesystem/network scopes checked around the subprocess);
   (c) plugin **hooks/MCP/LSP/monitors/panels** activation (each its own
   threat-model → executor → validator/guard-test → tests slice). Follow the
   slice discipline below for each.
5. **Web dashboard parity for slice 7/8 - completed in this session:** surface hosted-model gate state,
   egress allowlist status, and hosted profiles in the Security Settings /
   models views of `apps/web`.
   Implemented as read-only API/UI metadata with contract, backend, and Svelte
   tests. Allowlist values and provider keys are intentionally not displayed.

## Slice discipline (repeat every slice)

Threat-model doc → real executor (fail closed on every missing precondition)
→ activation requirements → validator + guard-test updated in lockstep →
acceptance tests (executes-when-governed AND fails-closed-when-disabled) →
update `docs/IMPLEMENTATION_STATUS.md` + `docs/RUNTIME_EXECUTORS_SPEC.md` →
run `pytest`, `ruff check .`, `mypy raiker apps tests`, and all four
`scripts/validate_*.py` → commit → push to `origin/main`.
