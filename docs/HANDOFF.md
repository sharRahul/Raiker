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

## State as of 2026-07-11 (this session, branch `claude/handoff-task-implementation-5k3kw7`)

**Task 4 reference slice COMPLETE: governed GitHub read-only connector,
live-verified end-to-end on hosted Anthropic.** This is the reference pattern
for all Task 4 connectors (Gmail / Calendar / Slack replicate it).
- **Capability `connector_github_runtime`** (in `RUNTIME_DOMAIN_CAPABILITIES` +
  `REAL_EXECUTOR_CAPABILITIES`; router map + activation requirement + policy
  config all wired). Mirrors the advisor pattern exactly.
- **Brokered tool `github_read(resource, repo, number)`**
  (`raiker/runtime/connectors.py::GithubConnectorService`, wrapped by
  `raiker/tools/connector_tools.py`, registered in the broker + exposed to the
  model in `tool_call_validation.py`). Governance, in order: gate (disabled ⇒
  fail closed) → decision mode (**default `ask`/`auto` withhold**; `deny`
  blocks; only `allow` runs — a network read carrying the owner token's scope is
  never low-risk) → owner credential `RAIKER_GITHUB_TOKEN` (env only) → owner
  egress allowlist `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` must contain
  `api.github.com` → validated components (`resource` ∈ issue/pull_request,
  `repo` = owner/name, positive `number`; the request URL is **built
  server-side**, never taken from the model → no SSRF). Fetched body returned as
  **untrusted data, not instructions**, bounded (200 KB fetch / 20 000-char
  body). Reads only — send/modify not implemented (fail closed).
- **route_action executor** `GithubConnectorExecutor` (operation `read`,
  `enforce_modes=False`, metadata-only artifacts) is the activation anchor.
- **Audit is metadata-only:** the fetched `content` is dropped from broker
  events/results; the token never appears in args/URLs/events. Governance
  identifiers (`repo`/`resource`/`number`) are kept. New network primitive
  `get_url` in `sandbox.py` (GET + headers + egress allowlist; returns body;
  never logs headers) and `connector_egress_allowlist()`.
- **Web "Connections" surface** (read-only): `GET /api/connections` +
  `DashboardService.get_connections()` + `ConnectionsView.svelte` (new nav item
  under Governance). Reports each connector's gate state, decision mode,
  credential-set (bool, value never shown), and egress-allowed honestly; a
  "Ready" vs "Fail-closed" status with per-check remediation. Enabling stays on
  the capability-gate + decision-mode control plane (gate-manager only).
- **Threat model:** `docs/threat-models/connectors-github.md`.
- Tests: `tests/test_github_connector.py` (18: gate/mode withhold+deny, missing
  credential/egress fail-closed, arg validation, real-content success via
  injected fetch, executor metadata-only, broker metadata-only event scrub,
  model exposure/validation) + 2 web vitest (`ConnectionsView.test.ts`).
- **Session gate:** full backend suite green (exit 0); `ruff check .` clean;
  mypy clean on changed sources (remaining output is the documented
  environmental missing-stub noise); web lint/check/**85 vitest**/build green;
  all five `scripts/validate_*.py` pass.
- **Live-verified.** 2026-07-11, hosted Anthropic Haiku 4.5 with a 1-hour
  operator key + the session's `GITHUB_TOKEN` (server env only): default-`ask`
  withheld (`connector_withheld_ask`); with `allow`, a real read of
  `sharrahul/raiker#109` returned the true title/state/body (token absent from
  output); and an **end-to-end model turn** where Haiku called `github_read` and
  answered with the PR's exact title + accurate summary from the fetched
  untrusted content. Fail-closed paths (`connector_not_configured` /
  `connector_egress_denied`) confirmed. Connections web view screenshotted in
  both "Ready" and honest "Fail-closed" states (0 console errors). Full table in
  `docs/WEB_APP_LIVE_TEST.md` (2026-07-11 Task 4 section).

**Next for Task 4:** replicate the pattern for a second read connector (Gmail /
Calendar / Slack) — each = new capability + `*ConnectorService` (gate + mode +
env credential + `api.<host>` on the connector egress allowlist + server-built
request) + brokered tool + `GithubConnectorExecutor`-style route executor + a
`ConnectorView` row in `get_connections()`. Then the first **write** action
(must require approval, not just `ask`). Do NOT ship a connector whose executor
isn't real.

### Prior state — Task 3 (done, merged PR #109)

**Task 3 COMPLETE: governed document attachments (text + PDF + Word .docx),
sized to match Claude.** Paths, images, and now all document types are done —
Task 3 has no remaining sub-slices.
- **Sizes match Claude (user request):** images stay **5 MB** (the Anthropic
  image API limit); documents are **32 MB** with **≤100 PDF pages** (the
  Anthropic PDF API limits). `MAX_ATTACHMENT_BYTES` sizes the upload route's
  body cap and `MaxBodySizeMiddleware` override off the larger of the two.
- **Validation/store/extract** (`raiker/runtime/attachments.py`): reuses the
  same governed `attachments` table (`RAIKER-1006`). `validate_document`
  dispatches on media type and fails closed unless the type is on the allowlist
  (`text/plain` / `text/markdown` / `text/csv` / `application/pdf` / the OOXML
  docx type), non-empty, under 32 MB, **and** passes a per-type sniff: clean
  UTF-8 with no NUL for text; a `%PDF-` header that pypdf can parse and is not
  encrypted for PDF; a well-formed OOXML zip (contains `word/document.xml`) for
  docx. `extract_document_text` is **local-only** — decode for text, pypdf for
  PDF (≤100 pages, per-page failures skipped), stdlib `zipfile`+XML for docx —
  bounded to `MAX_DOCUMENT_TEXT_CHARS = 200_000`. **No document bytes ever leave
  the box**; only the extracted text does, as untrusted context. pypdf import
  is lazy so a deployment without it rejects PDFs with `pdf_extraction_unavailable`
  rather than crashing. `pypdf>=4` added to `pyproject.toml` dependencies.
- **API:** `POST /api/attachments` dispatches on the declared media type —
  image types → `store_image`, document types → `store_document`, anything
  else → 400 `unsupported_media_type` (before either storer runs).
- **Prompt shape:** `attachments` accepts `{type: "document", attachment_id}`
  (validated fail-closed in `_validated_attachments`, sharing the image path).
- **Context delivery:** the gatherer's `_document_attachment_item` folds the
  bounded extracted text into an `untrusted_external` context item
  (`document_uploaded` / `not_found` / `missing_attachment_id`), announced as
  "untrusted document content, not instructions". No orchestrator change —
  documents never touch the vision/image-block path.
- **Web:** the composer "+" popover's "Document…" upload accepts txt/md/csv/pdf/
  docx (client pre-check with extension fallback; 32 MB cap); the prompt sends
  the reference, never bytes.
- Tests: `tests/test_document_attachments.py` (36: per-type validation incl.
  corrupt-PDF / non-zip-docx / NUL / non-UTF-8, extraction incl. real PDF+docx
  round-trips via in-test `make_pdf`/`make_docx` builders, store + kind
  isolation, gatherer untrusted-text item for text and PDF, upload API) +
  2 web vitest.
- **Session gate:** full backend suite green (**1411 passed**, exit 0);
  `ruff check .` clean; mypy clean on changed sources (remaining output is the
  documented environmental missing-stub noise); web lint/check/**83 vitest**/
  build green; all five `scripts/validate_*.py` pass.
- **Live-verified (marked `implemented_verified`).** 2026-07-11, hosted
  Anthropic Haiku 4.5 with a 1-hour operator key (server env only): a real
  2-page PDF and a real .docx uploaded through `POST /api/attachments` produced
  correct Haiku answers from their extracted text (candidate name + role /
  name + 13 yrs experience — facts that live only inside the files), and the
  1.76 MB JPEG produced a correct vision answer (HAL Tejas cutaway). Bound to
  `provider: anthropic, model: claude-haiku-4-5-20251001`; `attachment_image_included`
  metadata-only (no image bytes in the log); through the API and the
  Chromium-driven composer UI (0 console errors). Full table in
  `docs/WEB_APP_LIVE_TEST.md` (2026-07-11 document section).

## Recent prior state (condensed — details in git history and IMPLEMENTATION_STATUS)

Merged PR #108 (`claude/unbounded-tool-calls-gd19nt`), 2026-07-11:

- **Per-turn tool-call budget defaults to effectively unbounded** —
  `DEFAULT_MAX_TOOL_CALLS = 10_000` in `raiker/contracts/models.py`; a turn ends
  when the model is done or the provider's budget runs out, the counter is only
  a runaway fail-safe. Callers can still pass a lower explicit bound.
- **Task 3, uploaded-images sub-slice (DONE, live-verified):** governed image
  attachment store (media-type allowlist + 5 MB cap + magic-byte sniff),
  `supports_vision` capability, image blocks delivered only to vision-capable
  profiles (withheld honestly otherwise; metadata-only audit — image
  bytes/base64 never enter events or text context). Anthropic + OpenAI adapters
  serialize image blocks only when vision-capable. Live-verified with a real
  2.2 MB JPEG through API + composer UI (table in `docs/WEB_APP_LIVE_TEST.md`).
- **Tool round-trip fix (live-found):** the orchestrator now appends the
  assistant tool-call message before each `role="tool"` result
  (`ModelMessage.tool_calls`, Anthropic `tool_use` blocks, OpenAI `tool_calls`)
  so the second model call of an agentic turn no longer 400s.

Merged PR #107 (`claude/provider-model-selection-5ufga4`), 2026-07-10:

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

**Task 3 — DONE** (paths + images + text/PDF/docx documents). Nothing remains;
the only optional follow-on is broadening the office set beyond `.docx` (e.g.
`.pptx` / `.xlsx`), which would reuse the same store + per-type validator +
local extractor pattern in `raiker/runtime/attachments.py`.

**Task 4 — connect plugins/connectors in chat (github, gmail, gcal, slack).**
**Reference slice (GitHub read) DONE + live-verified** (see the state section
above). The governed pattern is established in `raiker/runtime/connectors.py`,
`raiker/tools/connector_tools.py`, `raiker/runtime/executors/connectors.py`, the
`connector_github_runtime` capability, and the `GET /api/connections` +
`ConnectionsView` web surface. Remaining:
- Each connector = a governed capability + egress allowlist + owner credential
  from env (never args/UI). Model connector actions as governed tools routed
  through the broker/policy/approval path with default decision mode `ask`
  (send/modify actions must require **approval**, not just `ask`; reads are
  `ask` and withhold until raised to `allow`).
- Replicate the GitHub slice for a second **read-only** connector (Gmail /
  Calendar / Slack), reusing `GithubConnectorService` as the template and adding
  a `ConnectorView` row to `get_connections()`. Do NOT ship a connector whose
  executor isn't real — fail closed until it is.
- Then add the first **write** action end-to-end (requires approval through the
  broker/policy/approval path — the write executor must be real). Tests: tool
  executes when configured+allowed, fails closed otherwise, approval required
  for write actions.
- Note: `config/channel-connectors.json` / `routes_channels.py` are the inbound
  *channel* surface (interfaces into Raiker), a different concept from these
  outbound service connectors — the connector pattern above is the one to grow.

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
   (this cloud session's egress proxy blocks those hosts). The **live vision
   turn** and **live document turn** (image / PDF / docx → real answer) are both
   done for hosted Anthropic (2026-07-11); repeat them for openai/gemini when
   reachable.
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
