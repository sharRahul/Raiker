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

## State as of 2026-07-10 (this session) — web-app feature tasks 1 & 6

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

**Session gate (both tasks):** full backend suite **1265 passed**; `ruff check .`
clean; `mypy` clean on changed sources (remaining output is the documented
environmental missing-stub noise for pytest/fastapi/httpx); web `lint` +
`svelte-check` + **70 vitest** + `build` green; all five `scripts/validate_*.py`
pass.

## Remaining web-app tasks (2–5) — build plan for the next session

Follow the slice discipline at the bottom. Each is a governed vertical slice;
do them one at a time, commit + push after each.

**Task 2 — advisor model for local-model turns.** Let a user running a *local*
model attach a hosted "advisor" that the local model can consult (ref:
Anthropic advisor tool, https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool).
- Model it as a governed capability `advisor_model_runtime` (new gate, defaults
  disabled; enabling needs the hosted/private egress path since the advisor is
  typically a hosted provider). Persist the advisor profile id like the fallback
  sequence (single-row settings table or reuse `model_session_state` shape).
- Expose the advisor to the local model as a **tool** (`consult_advisor`)
  registered in `ToolBroker` + PolicyEngine read allowlist, default decision
  mode `ask`. The tool calls the advisor profile through `ModelRouter.achat`
  (which re-checks egress/gate/key), returns the advisor's answer as an
  untrusted-data block. Metadata-only events; advisor prompt/answer never leak
  into event payloads.
- Threat model `docs/threat-models/advisor-model.md`; API read on `GET /api/models`
  (`advisor_profile_id`) + a `PUT /api/model-advisor` setter (gate-manager only);
  web selector on the Models view. Tests: tool executes when allowed, fails
  closed when the gate/egress/key is missing, decision-mode `ask` withholds.

**Task 3 — chat attachments (images, docs, file/folder paths).** Let a prompt
carry attachments: images, documents (docx/xlsx/csv/markdown/txt/pptx/pdf), and
a file or folder *path*.
- **Path attachments are the governed-cheap win:** they reuse the existing
  read tools (`read_file`, `list_directory`, `glob`) through the broker/policy —
  no new upload storage, workspace-scoped, already fail-closed on escape. Start
  here: add an attachment list to `PromptPayload`/`PromptOptions`, and have the
  context gatherer include the referenced path(s) as bounded, trust-labelled
  context items (never as instructions).
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
