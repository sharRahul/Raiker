# Session Handoff — pick up here

> Purpose: let any builder (Claude, Codex, or human) resume the Raiker goal
> without re-deriving state. Read this + `docs/IMPLEMENTATION_STATUS.md` first.
> Update this file at the end of every working session, and prune stale
> session logs so this stays a short, current pick-up point (deep history lives
> in git and `docs/IMPLEMENTATION_STATUS.md`).

## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and communicate through a polished conversational experience. As an agent, Raiker should be able to plan tasks, gather context, use tools, execute approved actions, verify outcomes, and explain what it did. As a platform, Raiker should provide the governed runtime foundation for models, tools, plugins, interfaces, memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM; private-network providers; and hosted API providers such as Anthropic, OpenAI, Gemini, and OpenRouter. No model, interface, plugin, or capability should bypass governance. Every action must remain policy-aware, observable, auditable, approval-driven where required, human-governed, user-controlled, and fail-closed by design.

Be mindful of token usage — if needed, work in batches. Commit after every phase, update HANDOFF.md and other relevant docs, then push before the session's token budget ends. Structure the work so anyone can pick it up mid-goal. In the next session, review where things are, then start from the next phase.

## Invariants that must never regress (read before touching code)

- **Fail-closed everywhere.** Missing config/gate/key/executor → deny, never fabricate. The runtime never emits model output it didn't get from a real provider.
- **Governance is not bypassable.** Every model call, tool call, and capability flows through gates + decision modes + PolicyEngine + (where required) approvals. New features re-use these surfaces; they do not add side-doors.
- **Events are typed.** New event types must be added to `EVENT_TYPES` in `raiker/contracts/models.py` (enforced by `AgentEvent.__post_init__`) — otherwise `make_event` raises.
- **Web reads are read-only + rate-limit-aware** (120 req/min/IP). Prefer folding new read data into an existing endpoint over adding a fan-out.
- **Secrets never surface.** API keys/allowlist values come from owner env, are never displayed, logged, or committed.

## State as of 2026-07-10 (later session, continued) — Task 3: path attachments

**Task 3, paths-first sub-slice (DONE): chat attachments for file/folder paths.**
A prompt can carry `attachments: [{type: "path", path: "<workspace path>"}]`
(max 8). The context gatherer includes each as a bounded, trust-labelled
context item — files become capped text, directories become listings — with
`trust_level: untrusted_external` (data, never instructions) and priority just
below the current prompt.
- Fail-closed: paths resolve through the same workspace-scoped filesystem
  layer as the read tools — outside the workspace yields an honest denial item
  with **no content**; missing paths and unsupported attachment types are
  reported honestly; invalid attachment shapes reject the prompt before a turn
  starts (`_validated_attachments` in `routes_prompts.py`).
- Web: the Chat composer was redesigned as a single clean card (user request,
  modelled on claude.ai): a "+" button reveals the attach-path input (chips
  shown in-card, max 8, cleared on send; sent turns keep their chips), and the
  per-turn Provider / Model / Planning / tool-budget controls sit as compact
  selects at the bottom of the card — the separate "Options" panel is gone.
- Tests: `tests/test_chat_attachments.py` (15) + 1 web vitest.
- **Remaining Task 3 sub-slices (not started):** uploaded images (needs a
  governed attachment store + `supports_vision` capability) and office/pdf
  text extraction — see the original scoping under "Remaining web-app tasks".

## State as of 2026-07-10 (later session, continued) — Task 2: advisor model

Implemented on the same branch (`claude/provider-model-selection-5ufga4`, PR
#107) as a governed vertical slice, following the slice discipline.

**Task 2 — advisor model for local-model turns (DONE).** A user running a local
model can attach one advisor profile (typically hosted) that the local model
consults through the brokered tool `consult_advisor(question)`.
- **Capability `advisor_model_runtime`** (threat model
  `docs/threat-models/advisor-model.md`): real executor
  (`AdvisorModelRuntimeExecutor`, operation `consult`, metadata-only
  artifacts), activation requires human gate-manager + threat-model ack +
  confirmation token + `local_single_user_runtime`. In
  `REAL_EXECUTOR_CAPABILITIES` / phase-gates tier 5 / `CAPABILITY_GATE_MAP` /
  activation registry / policy `approval_required_actions`.
- **Governance layering** (`raiker/runtime/advisor.py::AdvisorService`,
  mirrors `RetrievalAugmentor`): gate disabled → fail closed; decision mode
  default **`ask` withholds** (`auto` withholds too — off-machine prompt
  content is never low-risk; `deny` blocks; only `allow` runs); no/unknown/
  test-only/placeholder advisor → fail closed; then the consult goes through
  `ModelRouter.achat` so the provider factory re-checks the hosted/private
  gate + owner egress allowlist + env-only key per call.
- **Tool**: `consult_advisor` in the ToolBroker + PolicyEngine read allowlist +
  `_MODEL_EXPOSED_TOOLS` (advertised to the model; question required). Answer
  returns as an untrusted-data block, capped 16k; question capped 8k. Broker
  events/stored actions are scrubbed to metadata (`_METADATA_ONLY_TOOLS`) —
  the question/answer never enter event payloads (lengths only).
- **Persistence**: `model_advisor` table (migration `RAIKER-1005`) +
  `save/load_model_advisor`.
- **API**: `advisor_profile_id` + `advisor_model_gate_state` on
  `GET /api/models`; `PUT /api/model-advisor` (gate-manager only; null clears;
  unknown/test/placeholder profiles fail closed). Web: "Advisor model"
  selector on Models (concrete-model profiles only) + governance copy.
- Tests: `tests/test_advisor_model.py` (29: service governance matrix,
  executor fail-closed + activation, broker metadata-only audit, API), +3 web
  vitest. Suite: **1327 passed**; ruff/mypy clean; web lint/check/**78
  vitest**/build green; all five validators pass.
- **Live-verified (hosted Anthropic, operator key in process env only):** with
  the advisor gate enabled (ack + token), decision mode `allow`, and
  `anthropic-hosted` set as advisor, `AdvisorService.consult` returned a real
  answer from `claude-opus-4-8`, and the **brokered `consult_advisor` path**
  ran the same consult through PolicyEngine + ToolBroker — the durable event
  log contained `question_length` but neither the question nor the answer
  text (metadata-only audit verified live). This run also caught and fixed a
  circular import (`broker → advisor_tools → runtime.authority → … → broker`)
  that test-import ordering had masked: `advisor_tools` now imports the
  service lazily at call time.

## State as of 2026-07-10 (later session) — Task 7: provider model selection

Implemented on branch `claude/provider-model-selection-5ufga4` as a full
vertical slice (backend + API + web + tests + live verification).

**Task 7 — select the provider's available models in Chat and Models (DONE).**
- **Provider catalogue, on demand:** `GET /api/models/{profile_id}/provider-models`
  calls the provider's own model-listing endpoint (reuses
  `ModelRouter.alist_models_for_profile`, so gates/egress/key are enforced by the
  provider factory *before* any network contact). Honest statuses: `available` |
  `policy_denied` | `unsupported` | `unavailable` — failures return an empty
  list, never fabricated names. This is the only web read that touches the
  network, and only on explicit user demand (unknown/test profiles 404).
- **Selection:** `PUT /api/model-selection` (`{profile_id, model?}`) persists the
  same `ModelSessionState` the CLI `/model use` writes — human gate-manager only,
  unknown/test profiles fail closed, placeholder profiles require a concrete
  model, and the provider factory validates policy fail-closed before saving
  (emits `model_profile_selected`). `GET /api/models` now returns `current_model`
  and shows the concrete model on the selected profile card.
- **Per-turn model:** `PromptOptions.model` (+ `PromptRequest.model`) lets a chat
  turn pin a concrete model for the chosen profile; the gateway resolver
  registers the concrete choice so the router resolves it (idempotent), and
  provider policy is still enforced downstream.
- **Web:** Models cards get Select / "Choose model…" (picker fetches the live
  catalogue; manual model-id entry when the catalogue is unavailable). Chat →
  Options gets a Provider select + a Model select populated from the catalogue.
  The "Development preview" runtime-mode pill was removed from the top bar
  (only an explicitly activated mode shows a badge).
- Tests: `tests/test_api_model_selection.py` (14), +5 in
  `tests/test_turn_model_binding.py`, +4 web vitest (ModelsView picker/select,
  ChatView per-turn model). Suite: **1298 passed**; ruff/mypy clean; web
  lint/check/**75 vitest**/build green; all five validators pass.
- **Live-verified (hosted Anthropic, real key in server env only):** catalogue
  listed 10 real models; selection via the new endpoint bound a streamed turn to
  `claude-haiku-4-5-20251001`; a per-turn override ran `claude-sonnet-4-6`;
  Chromium pass on both views with 0 console errors. Details in
  `docs/WEB_APP_LIVE_TEST.md`.

## State as of 2026-07-10 — web-app feature tasks 1 & 6

Two of a six-task batch were implemented as full vertical slices (backend + API +
web + tests) on branch `claude/raiker-web-app-features-8g8k5q`. Tasks 2–5 are
scoped below with a concrete build plan but **not yet started**.

**Task 1 — user-owned model fallback sequence (DONE).** When the selected
provider is unavailable (no network, timeout, non-responsive host, or a policy
denial), the turn walks a user-owned ordered list of profile ids and tries the
next backend — typically a local runtime. Each candidate is still resolved and
gated by the model router, so a hosted candidate that policy denies is *skipped*,
never opened; when all fail the turn fails closed as before.
- Storage `model_fallback_sequence` table (migration `RAIKER-1004`) +
  `save/load_model_fallback_sequence`.
- `RuntimeOrchestrator._provider_chain` / `_acall_model` / `_astream_model_call`
  iterate the chain and emit `model_fallback_engaged`. Streaming uses fresh
  per-attempt buffers (nothing is yielded live until the call returns), so a
  failed attempt's partial deltas are discarded — no duplicated output.
- Gateway `_resolve_fallback_chain` (reuses `_resolve_profile_for_turn`, so
  test/placeholder profiles drop out).
- API `PUT /api/model-fallback` (human gate-manager only, unknown/test profiles
  fail closed, de-duplicated) + `fallback_sequence` on `GET /api/models`.
- Web: Models view fallback-sequence editor (add / remove / reorder / save).
- Tests: `tests/test_turn_model_fallback.py` (12), `tests/test_api_model_fallback.py`
  (8), `apps/web/.../ModelsView.test.ts` (4).
- **Honest limit:** a fallback candidate needs a *concrete* model. The llama.cpp
  profile (`local-gguf`) and hosted profiles ship concrete models and work
  out-of-box; placeholder-`<model>` profiles (Ollama/LM Studio/vLLM) resolve only
  if the owner has a persisted concrete-model selection for that profile
  (same rule as per-turn selection). A per-profile "fallback model" field is the
  natural follow-up.

**Task 6 — prompt caching, unified control across providers (DONE, incl. Option A).**
`ModelRequest.cache_ttl` (None | `"5m"` | `"1h"`), threaded from each profile by
the router (`_cache_ttl`). The KV cache is model-specific and lives inside each
provider, so Raiker cannot share one cache across models; instead it drives each
backend's own lever and normalises the metrics:
- **Anthropic:** system prompt emitted as a content-block list with a
  `cache_control` breakpoint (reuses tools + system within the TTL); `"1h"` adds
  `ttl:"1h"` + the `extended-cache-ttl-2025-04-11` beta header.
- **OpenAI-compatible (Option A):** hints sent only where the backend documents
  one — OpenAI gets `prompt_cache_key` (keyed by profile_id, so same-prefix turns
  share a cache) + `stream_options.include_usage`; llama.cpp gets
  `cache_prompt: true`. vLLM/Ollama/LM Studio/Gemini/OpenRouter cache
  automatically server-side, so no field is sent (a strict server would 400 on an
  unknown field).
- **Provider-agnostic cache-hit metrics:** `summarize_model_usage()`
  (`raiker/models/contracts.py`) flattens Anthropic (`cache_read_input_tokens`)
  and OpenAI (`prompt_tokens_details.cached_tokens`) usage into one shape; the
  orchestrator emits it on `model_request_completed` (both buffered and streamed
  paths — streaming usage is captured from Anthropic `message_start`/
  `message_delta` and the OpenAI final usage chunk via `ModelStreamEvent.metadata`).
- Profiles opting in: `anthropic-hosted`, `openai-hosted`, `raiker-local-llama-cpp`
  (`prompt_cache_ttl: "5m"`). Web: a "Cache 5m/1h" chip per profile on Models,
  and a per-turn "Cache hit · N tok / Cache miss" chip in Chat.
- Tests: `tests/test_phase_4_provider_breadth.py` (+5 Anthropic),
  `tests/test_prompt_cache_metrics.py` (14: summarizer, OpenAI-compatible hints,
  streamed usage both providers, orchestrator emission), +1 web chip test.
- **Option B (deferred, opt-in for later): a Raiker-level *response* cache.**
  Store `(exact prompt + model) → response` and short-circuit identical repeated
  prompts without calling the model. Provider-agnostic and fully Raiker-owned,
  but note: (1) must be keyed by model (serving one model's answer for another is
  wrong), so it's still not "cache irrespective of model"; (2) only helps on
  *identical* prompts, and Raiker gathers fresh context each turn, so hits are
  rare; (3) it changes a core invariant — a cache hit means the model did not run
  this turn — so it needs deliberate governance (staleness, is a cached answer
  still policy-valid, audit). Build only if short-circuiting repeats is
  explicitly wanted; design the governance first.

**Live web-app test (2026-07-10, hosted Anthropic Haiku 4.5) — PASSED.** Ran one
round against a real operator key: `raiker-web` booted, owner session minted,
`GET /api/models` showed `anthropic-hosted` selected + hosted gate
`enabled_runtime` + the fallback sequence + cache `5m`, and a **streamed turn**
returned a real Haiku answer bound to `claude-haiku-4-5-20251001`
(`model_request_started` confirms the model; `model_request_completed` carried
normalised usage `{input:2013, output:19, cache_read:0, cache_write:0}`). A
Chromium pass rendered the Models cards (Anthropic "selected" + "Cache 5m" chips,
fallback editor) and drove a live chat turn through the UI with **zero console
errors**; the top-bar chip showed `Hosted · Anthropic · egress open`. Full
procedure + a per-model test matrix (OpenAI/Gemini/OpenRouter/llama.cpp/Ollama/
LM Studio/vLLM, all `Ready`) is in **`docs/WEB_APP_LIVE_TEST.md`**. Honest note:
the cached prefix was 2013 tokens — just under Haiku's ~2048 minimum — so no cache
*write* happened this round; the caching path (breakpoint sent, usage captured +
normalised) is verified, and a >2048-token prefix on two same-session turns will
show a non-zero `cache_read`. Keys were used in the server env only, never
persisted or committed.

**Session gate (both tasks):** full backend suite **1265 passed**; `ruff check .`
clean; `mypy` clean on changed sources (remaining output is the documented
environmental missing-stub noise for pytest/fastapi/httpx); web `lint` +
`svelte-check` + **70 vitest** + `build` green; all five `scripts/validate_*.py`
pass.

## Remaining web-app tasks (3-remainder, 4, 5) — build plan for the next session

Follow the slice discipline at the bottom. Each is a governed vertical slice;
do them one at a time, commit + push after each. (Tasks 1, 2, 6, 7 and the
paths-first sub-slice of Task 3 are DONE — see the state sections above.)

**Task 3 remainder — uploaded attachments (images, docs).** Path attachments
are done; what remains:
- **Uploaded files (images/docs):** need a governed local attachment store
  (new table + size/type allowlist + redaction), text extraction for docs
  (local-only libs; PDFs/office are heavier — scope carefully), and image blocks
  only for vision-capable profiles (`supports_vision` capability — add it).
  Treat every attachment as untrusted data. This is the biggest sub-slice; do
  paths first, images next, office/pdf extraction last.
- Web: attachment picker in the Chat composer; API multipart or base64 on
  `/api/prompts`. Tests for path inclusion, type/size fail-closed, trust labels.

**Task 4 — connect plugins/connectors in chat (github, gmail, gcal, slack).**
There is already a `ConnectorRegistry` (`config/channel-connectors.json`) and a
`routes_channels.py` surface — build on them, don't reinvent.
- Each connector = a governed capability + egress allowlist + owner credential
  from env (never args/UI). Model connector actions as governed tools routed
  through the broker/policy/approval path with default decision mode `ask`
  (send/modify actions must require approval; reads are `ask`).
- Start with **one read-only connector end-to-end** (e.g. GitHub issue/PR read)
  as the reference slice, then replicate. Do NOT ship a connector whose executor
  isn't real — fail closed until it is.
- Web: a "Connections" surface showing connector status (configured / gated /
  egress) read-only, and a per-connector enable flow through the existing gate
  control plane. Tests: tool executes when configured+allowed, fails closed
  otherwise, approval required for write actions.

**Task 5 — project folders (like Claude Cowork).** A named "project" that scopes
an ongoing piece of work: its own workspace subpath, sessions, checkpoints, and
(later) memory/attachments.
- Storage: `projects` table (id, name, root_subpath, created_at) +
  `project_id` FK on sessions. Service to create/list/select a project;
  workspace-scoped root so a project can never escape the workspace.
- API: `GET/POST /api/projects`, `GET /api/projects/{id}` (sessions/checkpoints
  filtered by project). Web: a Projects surface + a project switcher in the top
  bar; Chat/Sessions/Checkpoints filter by the active project.
- Keep it governance-neutral (a project is an organizing scope, not a new
  authority). Tests: create/list/select, session association, path containment.

## Reference: how a user turns on a hosted provider

1. `/runtime-mode activate local_single_user_runtime` (human owner).
2. Record a threat-model ack for `hosted_model_runtime`
   (`docs/threat-models/hosted-models.md`) and enable the gate with a
   confirmation token.
3. Set `RAIKER_MODEL_EGRESS_ALLOWLIST` to the provider host
   (`api.anthropic.com` / `api.openai.com` / `openrouter.ai` /
   `generativelanguage.googleapis.com`) and the provider key env
   (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `GEMINI_API_KEY`).
4. Select a concrete model: `/model use anthropic-hosted`, or
   `/model use --provider openai --model gpt-4o-mini`, etc. Placeholder-`<model>`
   providers take the concrete model at selection time;
   `ModelProfileRegistry.resolve` falls back to the provider's placeholder
   profile. Provider policy (gate + egress + key) is enforced by the factory
   regardless of how the model was selected.

## Standing next-work (independent of the task batch)

1. **Open hosted-provider live verification (evidence only).** `anthropic-hosted`
   is `implemented_verified`. `openai-hosted` / `gemini-hosted-openai-compatible`
   remain to verify with a governed live turn when operator keys are available
   (this cloud session's egress proxy blocks those hosts).
2. **Plugin runtime remainder (Tier 4).** In-process import isolation; image
   build/pull management for the sandboxed runtime + per-plugin network egress
   for the bare-subprocess runtime; plugin hooks/MCP/LSP/monitors/panels
   activation (each its own threat-model → executor → validator/guard-test →
   tests slice).

## Environment setup (this cloud runner)

Dev deps must be installed before tests: `pip install -e ".[dev]"` then
`pip install cffi` (the `_cffi_backend` module is needed by `cryptography`).
The web app: `cd apps/web && npm install`, then `npm run lint`, `npm run check`,
`npm run test`, `npm run build`. Python 3.11 at `/usr/local/bin/python3`.

## Slice discipline (repeat every slice)

Threat-model doc → real executor (fail closed on every missing precondition)
→ activation requirements → validator + guard-test updated in lockstep →
acceptance tests (executes-when-governed AND fails-closed-when-disabled) →
update `docs/IMPLEMENTATION_STATUS.md` + `docs/RUNTIME_EXECUTORS_SPEC.md` →
run `pytest`, `ruff check .`, `mypy raiker apps tests`, the web gate
(lint/check/test/build), and all five `scripts/validate_*.py` → commit →
push to the working branch → open/refresh the PR.
