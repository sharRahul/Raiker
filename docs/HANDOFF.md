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

## State as of 2026-07-04 (session end)

Previous pushed anchors: slice 8 `c8ce3d5`, slice 7 `c571c9c`; config cwd
fallback `29ec83a`. Full suite was green before the config packaging follow-up
(1060 passed, 2 skipped); ruff/mypy/all validators passed.

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
  `plugin_install_records`. `plugin_execution_cap` remains fail-closed with no
  executor.

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
4. **Plugin runtime promotion (Tier 4)** — the biggest remaining fail-closed
   area (`plugin_execution_cap`): sandboxed execution +
   signature verification + threat model, following the slice pattern.
   `plugin_install` itself is already completed as manifest validation +
   install-record creation only; do not reintroduce code execution there.
   (threat-model doc → executor → validator/guard-test lockstep → tests).
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
