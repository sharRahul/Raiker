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

## State as of 2026-07-11 (this session, branch `claude/unbounded-tool-calls-gd19nt`)

**1. Per-turn tool-call budget now defaults to effectively unbounded (user
decision).** `PromptOptions.max_tool_calls` and the `/api/prompts` default both
use `DEFAULT_MAX_TOOL_CALLS = 10_000` (`raiker/contracts/models.py`): a turn
ends when the model finishes its task or the provider's context/token budget
runs out — never because of the counter, which remains only as a hard
runaway-loop fail-safe. Callers can still pass a lower explicit bound per turn.
Docs updated (CONTRACTS, API_AND_CONTRACT_SCHEMAS, OWASP LLM06/LLM10 rows);
`test_default_tool_call_budget_is_effectively_unbounded` pins the contract.

**2. Task 3, uploaded-images sub-slice (DONE): governed image attachments.**
- **Store:** `attachments` table (migration `RAIKER-1006`) +
  `save_attachment` / `load_attachment` / `load_attachment_metadata`.
  Validation is fail-closed in `raiker/runtime/attachments.py`: media-type
  allowlist (png/jpeg/webp/gif), 5 MB cap, magic-byte sniff that the bytes
  really are the declared type (webp also checks the RIFF/WEBP tag);
  `load_image` re-validates on the way out.
- **API:** `POST /api/attachments` (owner bearer auth; base64 body;
  metadata-only response — bytes are never echoed). Only this route gets a
  larger body cap via the new `MaxBodySizeMiddleware.path_overrides`; every
  other route keeps the tight 1 MB default.
- **Prompt shape:** `attachments` now also accepts
  `{type: "image", attachment_id: "att_…"}` (validated fail-closed in
  `_validated_attachments`; `att_` added to id prefixes).
- **Vision capability:** `supports_vision` on `ModelCapabilities`, parsed from
  profile config; set for `anthropic-hosted`, `openai-hosted`,
  `gemini-hosted-openai-compatible` (both copies of `model-profiles.json`).
  `ModelRouter.supports_vision(provider, model)` fails closed on unresolvable
  profiles.
- **Delivery:** the orchestrator attaches stored images to the user
  `ModelMessage` (`ModelMessage.images: tuple[ModelImage, ...]`) only when the
  turn's bound profile supports vision; otherwise it withholds honestly. New
  metadata-only audit events `attachment_image_included` /
  `attachment_image_withheld` (id, media type, size, sha256, reason — image
  bytes/base64 never enter event payloads or text context). The gatherer adds
  a metadata-only `attachment` context item (`image_uploaded` / `not_found` /
  `missing_attachment_id`), trust `untrusted_external`.
- **Providers:** Anthropic serializes base64 `image` blocks, OpenAI-compatible
  serializes `image_url` data-URL parts — both only when
  `capabilities.supports_vision`; non-vision profiles get plain text
  (fail-closed drop, no provider 400s).
- **Web:** the composer "+" popover gains an image upload (client-side
  type/size pre-check, chips share the path-attachment UI, honest upload
  errors); the prompt sends the attachment reference, never bytes.
- Tests: `tests/test_uploaded_image_attachments.py` (28: validation, store
  round-trip, capability parse, both providers, gatherer, orchestrator
  deliver/withhold/fail-closed, upload API) + 2 web vitest.
- **Session gate:** full backend suite green (~1373 passed, exit 0);
  `ruff check .` clean; mypy clean on changed sources (remaining output is the
  documented environmental missing-stub noise); web lint/check/**81 vitest**/
  build green; all five `scripts/validate_*.py` pass.
- **Live-verified (hosted Anthropic Haiku 4.5, 1-hour operator key in server
  env only):** a real 2.2 MB JPEG uploaded through `POST /api/attachments`
  produced a correct vision answer through both the API and the Chromium-driven
  composer UI (0 console errors); the withheld path fired
  `attachment_image_withheld` before any provider contact on a non-vision
  profile; the event log contained metadata only (no bytes/base64 — checked).
  Full table in `docs/WEB_APP_LIVE_TEST.md` (2026-07-11 section).

**3. Tool round-trip fix (found live, would break any hosted multi-step turn).**
The orchestrator appended only the `role="tool"` result message after a tool
run — never the assistant message carrying the model's tool call — so the
*second* model call of an agentic turn got HTTP 400 from Anthropic
(`tool_result` with no matching `tool_use`); strict OpenAI endpoints reject the
same shape. Fixed contract-level: `ModelMessage.tool_calls`
(`tuple[ToolCallProposal, ...]`), the orchestrator appends the assistant
tool-call message before each tool result, the Anthropic adapter serializes
`tool_use` blocks, and `to_dict()` emits the OpenAI `tool_calls` field. Two new
tests in `tests/test_model_tool_call_loop.py`. **Live-verified:** a governed
agentic turn (list files → read file → report codeword) ran 3 model calls +
2 governed tool executions on hosted Haiku 4.5 and finished because the model
was done — the Claude-style loop end to end.

## Recent prior state (condensed — details in git history and IMPLEMENTATION_STATUS)

All on merged PR #107 (`claude/provider-model-selection-5ufga4`), 2026-07-10:

- **Task 3, paths-first sub-slice (DONE):** prompts carry
  `{type: "path", path}` attachments (max 8); the gatherer includes each as a
  bounded, `untrusted_external` context item via the workspace-scoped
  filesystem layer (outside-workspace fails closed with no content). Composer
  redesigned as a single card ("+" attach, name-only chips, right-side
  planning/provider/model selects, disabled mic placeholder; tool-budget input
  removed from the UI). `tests/test_chat_attachments.py`.
- **Task 2 (DONE): advisor model** for local-model turns via the brokered
  `consult_advisor` tool — capability `advisor_model_runtime`, default-`ask`
  withholds, provider policy re-checked per call, metadata-only audit
  (`raiker/runtime/advisor.py`; threat model
  `docs/threat-models/advisor-model.md`). Live-verified against hosted
  Anthropic. `tests/test_advisor_model.py` (29).
- **Task 7 (DONE): provider model selection** —
  `GET /api/models/{id}/provider-models` (honest statuses, gates enforced
  before network), `PUT /api/model-selection`, per-turn
  `PromptOptions.model`, web pickers. Live-verified (10 real models listed;
  streamed turns bound to chosen models).
- **Task 1 (DONE): user-owned model fallback sequence** — ordered profile-id
  chain walked on provider failure, each candidate still router-gated;
  `PUT /api/model-fallback`; web editor. Honest limit: candidates need a
  concrete model (placeholder profiles resolve only with a persisted
  selection).
- **Task 6 (DONE): prompt caching** — `ModelRequest.cache_ttl` (5m/1h) drives
  Anthropic `cache_control` (+1h beta header), OpenAI `prompt_cache_key`,
  llama.cpp `cache_prompt`; provider-agnostic usage normalisation
  (`summarize_model_usage`) emitted on `model_request_completed` (buffered +
  streamed); web cache chips. Option B (Raiker-level response cache) remains
  deliberately deferred — see git history for the governance notes.
- **Live web-app test (hosted Anthropic) PASSED** — procedure + per-model
  matrix in `docs/WEB_APP_LIVE_TEST.md`.

## Remaining web-app tasks — build plan for the next session

Follow the slice discipline at the bottom. Each is a governed vertical slice;
do them one at a time, commit + push after each.

**Task 3 remainder — office/pdf document attachments (last sub-slice).**
Paths and uploaded images are done; what remains is text extraction for
uploaded documents: local-only extraction libs (PDFs/office are heavy — scope
carefully; prefer starting with plain-text/markdown/csv before pdf/docx),
reuse the same governed attachment store + allowlist pattern
(`raiker/runtime/attachments.py` — add per-type validators + an extraction
step whose output becomes a bounded, `untrusted_external` context item, like
path attachments). Every attachment stays untrusted data. Tests for
type/size fail-closed, extraction bounds, trust labels.

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
   (this cloud session's egress proxy blocks those hosts). Add a **live vision
   turn** (uploaded image → image block → real answer) to the same checklist.
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
