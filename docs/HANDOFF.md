# Session Handoff — pick up here

> Purpose: let any builder (Claude, Codex, or human) resume the Raiker goal
> without re-deriving state. Read this + `docs/IMPLEMENTATION_STATUS.md` first.
> Update this file at the end of every working session.

## Goal (unchanged)

Make Raiker a full-fledged, secure AI agent that can connect to **any**
backend LLM — local (llama.cpp/Ollama/LM Studio), home-lab (vLLM), or hosted
API provider (Anthropic/OpenAI/Gemini/OpenRouter) — with the choice belonging
to the user, and every capability governed, default-disabled, and fail-closed.

## State as of 2026-07-04 (session end)

All committed and pushed to `origin/main` (latest: slice 8 `c8ce3d5`, slice 7
`c571c9c`). Full suite green (1060 passed, 2 skipped); ruff/mypy/all
validators pass.

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

1. **Config path resolution bug (small, high value).**
   `ModelProfileRegistry.load()` / `ConnectorRegistry.load()` read
   `config/*.json` relative to cwd — installed `raiker` fails outside the
   repo root (`FileNotFoundError`). Add a package-relative fallback
   (`importlib.resources` or anchored on `raiker.__file__`), ship the JSON as
   package data, and add a test that loads the registry from a foreign cwd.
2. **Live hosted-provider verification.** With an operator key, run one
   governed turn on `anthropic-hosted` and flip its status note from
   `implemented_unverified` to verified. No code expected — evidence only.
3. **Tool calls on Ollama models.** `ollama-local-openai-compatible` ships
   `supports_tool_calls: false` / `text_json`. Modern Ollama models (qwen3,
   gemma4) support native OpenAI tool calls — test against the live server,
   then flip the profile (or add per-model detection) so the agentic loop can
   act with local models, not just llama.cpp.
4. **Plugin runtime promotion (Tier 4)** — the biggest remaining fail-closed
   area (`plugin_install`, `plugin_execution_cap`): sandboxed execution +
   signature verification + threat model, following the slice pattern
   (threat-model doc → executor → validator/guard-test lockstep → tests).
5. **Web dashboard parity for slice 7/8:** surface hosted-model gate state,
   egress allowlist status, and hosted profiles in the Security Settings /
   models views of `apps/web`.

## Slice discipline (repeat every slice)

Threat-model doc → real executor (fail closed on every missing precondition)
→ activation requirements → validator + guard-test updated in lockstep →
acceptance tests (executes-when-governed AND fails-closed-when-disabled) →
update `docs/IMPLEMENTATION_STATUS.md` + `docs/RUNTIME_EXECUTORS_SPEC.md` →
run `pytest`, `ruff check .`, `mypy raiker apps tests`, and all four
`scripts/validate_*.py` → commit → push to `origin/main`.
