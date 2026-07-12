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

## State as of 2026-07-12 (this session, local, pushed to `main`)

**Manifest-driven bi-directional Connector Store COMPLETE (generic governed runtime).**
- Added migrations `RAIKER-1008`/`1009`: principal-scoped installations,
  encrypted credentials, stored manifests, action-bound write intents, and
  metadata-only invocation lifecycle records.
- Catalog contains every service named in the request (**26 actual names**, not
  the request's conflicting count of 23): the prior GitHub/Gmail/Calendar/Slack
  plus Hugging Face, NVIDIA, Vercel, Wolfram, Drive, YouTube, Signal, ten travel
  services, and five on-demand/local services.
- Store API supports browse/install/uninstall, encrypted API-key/OAuth token
  setup, enable/disable, manifest registration, and operation invocation. Vault
  requires owner `RAIKER_CONNECTOR_VAULT_KEY`; no fallback key; values never echo.
- OpenAPI 2/3 manifests compile to a bounded operation index; `ai-plugin.json`
  API metadata is recognized. URLs are manifest-built, HTTPS-only, catalog-host
  pinned, path-encoded, redirect-disabled, and owner-egress-allowlisted.
- Model surface: authenticated prompt principal is server-bound; generic
  `connector_read` (GET only) and `connector_write` (mutations only) tools are
  exposed. Enabled connector/invocation state is included as bounded local model
  context (`idle`/`processing`/`completed`/`failed`), never credentials/content.
- Writes default to approval. The broker persists the exact immutable intent;
  approval atomically claims and executes it once. Denied/failed/executed intents
  cannot replay. Existing non-connector approvals remain metadata-only.
- OAuth refresh: expired credentials refresh silently using the manifest-declared
  HTTPS token URL plus encrypted refresh/client credentials; the token host must
  be owner-egress-allowlisted and rotated tokens are re-encrypted.
- UI is a responsive categorized marketplace with search, installed filter,
  Install/Manage, encrypted API-key/OAuth-token setup, enable/disable, uninstall,
  Connected/Re-authentication/Disabled/Invoking states, and server-side manifest
  registration.
- Honest provider boundary: catalog presence does not invent access. Partner-only
  services execute only after the owner supplies an authorized manifest and
  credentials. Provider-specific OAuth consent popups require issued client IDs
  and redirect configuration; the generic UI currently accepts encrypted OAuth
  token material instead of fabricating unsupported authorization URLs.
- Threat model: `docs/threat-models/connector-ecosystem.md`.
- Verification: full backend **1519 passed, 2 skipped**; ruff clean; full web
  **95 passed**, Svelte check/lint/build green. Manifest compilation performance
  acceptance test is under 200 ms.

**Connectors window UX refresh COMPLETE (ChatGPT Plugins-style discovery and management).**
- Replaced the read-only diagnostic list with a searchable connector directory:
  category tabs (All/Developer/Productivity/Communication), enabled-only filter,
  responsive connector cards, clear Active/Setup required/Not enabled session
  state, refresh, empty states, and mobile layout.
- Each connector now has a focused management dialog with authentication state,
  owner env guidance (secret values remain server-only), egress state, exposed
  read actions, session availability, and enable/disable-for-chat controls. The
  controls reuse the existing governed capability decision-mode API; they grant
  no new authority and remain disabled until the capability gate is enabled.
- Added an OpenAPI/Swagger JSON manifest inspector. It validates the document
  shape and dynamically discovers GET/POST/PUT/PATCH/DELETE operations and
  operation IDs for review. Inspection is deliberately non-executing: imported
  endpoints do not receive network access, credentials, installation, or runtime
  authority without a real governed executor and the existing policy gates.
- Authentication boundary remains intentional: OAuth/API tokens are configured
  in the owner-controlled server environment and the UI only reports presence.
  Raiker does not persist, render, or transmit secret values from this window.
- Verification: web `check` and `lint` clean; focused `ConnectionsView` suite
  **4 passed** (including manifest discovery); production build green. Full web
  run: connector/application tests green, but the pre-existing 5
  `theme.test.ts` cases fail in this Windows Node invocation because
  `--localstorage-file` supplies an invalid path and jsdom exposes a nonfunctional
  `window.localStorage`. No browser connector was callable in this session, so
  interactive screenshot QA was not available.

**Task 5 COMPLETE: project folders (governance-neutral organizing scope).**
- **Storage:** `projects` table (project_id `proj_…`, unique name, `root_subpath`,
  created_at) + `active_project` (single-scope row) + `project_id` column on
  `sessions` (migration `RAIKER-1007-projects`). `SQLiteStore.create_session`
  stamps new sessions with the active project — no caller changes needed.
  `list_sessions` / `list_checkpoints` take an optional `project_id` filter
  (checkpoints scope through their session).
- **Service (`DashboardService`):** `create_project` (human gate-manager only;
  root subpath derived server-side as a slug under `projects/`, verified inside
  the workspace — fail closed on escape/empty/duplicate), `select_project`
  (set/clear active), `list_projects`, `get_project` (detail bundles scoped
  sessions + checkpoints). A project grants nothing — no gate/mode/policy change.
- **API:** `GET/POST /api/projects`, `PUT /api/projects/selection`,
  `GET /api/projects/{id}`; `project_id` query filter on `GET /api/sessions` +
  `GET /api/checkpoints`. Same Bearer auth as every governed read; mutations 403
  with honest reason codes.
- **Web:** Projects view (create/list/set-active/detail; nav "Work" group) +
  topbar active-project switcher (App owns one `ProjectsList` snapshot);
  Sessions/Checkpoints views filter by the active project and reload when it
  changes.
- Tests: `tests/test_projects.py` (14: create/list/select, traversal-shaped
  names contained, empty/dup fail closed, session stamping, checkpoint scoping,
  API auth + roundtrip + filters) + `ProjectsView.test.ts` (5).
- **Also this session (model-selection UI truth fix):** the Chat provider
  dropdown's default option now names the persisted selection (e.g. "Selected
  model — Ollama · gemma4:31b-cloud") and the topbar model chip refreshes after
  a selection on the Models view (`onchanged` → App re-reads `/api/models`).
  3 regression tests (ChatView label, ModelsView callback, App chip refresh).
- Deferred (spec'd "later" in the task): per-project memory/attachments; Chat
  does not yet show the active project inline (sessions are stamped server-side).

### Prior state — 2026-07-11 (branch `claude/handoff-task-implementation-9fapmw`)

**Task 4 read connectors COMPLETE: GitHub + Gmail + Google Calendar + Slack, all
governed read-only.** Four connectors now share the identical fail-closed pattern
(gate + default-`ask` decision mode + owner env-only credential + owner egress
allowlist + server-built request URL + untrusted-data framing + metadata-only
audit; reads only). GitHub and Gmail are **live-verified end-to-end on hosted
Anthropic**; Calendar and Slack are code-complete + fully unit-tested (live
verification deferred — no operator tokens for those services this run).
- **`connector_gcal_runtime`** — `gcal_read(resource, calendar_id, event_id)`;
  resource ∈ event/calendar; env `RAIKER_GCAL_TOKEN`; host `www.googleapis.com`;
  URL built server-side and **path-encoded** from validated components. Threat
  model `docs/threat-models/connectors-gcal.md`; `tests/test_gcal_connector.py`
  (19).
- **`connector_slack_runtime`** — `slack_read(resource, channel)`; resource ∈
  channel_info/channel_history; env `RAIKER_SLACK_TOKEN`; host `slack.com`; URL
  built server-side against a fixed Web API method (`conversations.info`/
  `conversations.history`) from a validated channel id; a Slack `ok:false` body
  is treated as `connector_bad_response`, never surfaced as content. Threat model
  `docs/threat-models/connectors-slack.md`; `tests/test_slack_connector.py` (19).
- Both wired exactly like GitHub/Gmail (phase_gates RUNTIME_DOMAIN + tier-5,
  executor registry + `REAL_EXECUTOR_CAPABILITIES`, activation, router, policy
  config, tool_call_validation, broker content-scrub set) with `ConnectorView`
  rows in `get_connections()` (the generic `ConnectionsView` renders all four).

### Prior state — Task 4 second read connector (Gmail, done + live-verified this branch)

**Task 4 second read connector COMPLETE: governed Gmail read-only connector,
live-verified end-to-end on hosted Anthropic.** Replicates the GitHub reference
slice exactly — different host + credential + resource, identical governance.
- **Capability `connector_gmail_runtime`** (in `RUNTIME_DOMAIN_CAPABILITIES` +
  tier-5 executed caps + `REAL_EXECUTOR_CAPABILITIES`; router map + activation
  requirement + policy config all wired). Mirrors the GitHub connector exactly.
- **Brokered tool `gmail_read(resource, message_id)`**
  (`raiker/runtime/connectors.py::GmailConnectorService`, wrapped by
  `raiker/tools/connector_tools.py::gmail_read`, registered in the broker + model-
  exposed in `tool_call_validation.py`). Governance, in order: gate → decision
  mode (**default `ask`/`auto` withhold**; `deny` blocks; only `allow` runs) →
  owner credential `RAIKER_GMAIL_TOKEN` (env only) → owner egress allowlist must
  contain `gmail.googleapis.com` → validated components (`resource` ∈
  message/thread, URL-safe id; the request URL is **built server-side** with
  `format=metadata` — Gmail's own snippet + Subject/From/To/Date headers, never
  raw MIME body, no SSRF). Fetched summary returned as **untrusted data, not
  instructions**. Reads only.
- **route_action executor** `GmailConnectorExecutor` (operation `read`,
  `enforce_modes=False`, metadata-only artifacts: resource/message_id/subject/
  length) is the activation anchor.
- **Audit is metadata-only:** the fetched `content` is dropped from broker
  events/results (`gmail_read` added to `_CONTENT_RESULT_TOOLS`); the token never
  appears in args/URLs/events.
- **Web "Connections" surface:** a second `ConnectorView` row for Gmail in
  `DashboardService.get_connections()`; the generic `ConnectionsView` renders it.
- **Threat model:** `docs/threat-models/connectors-gmail.md`.
- Tests: `tests/test_gmail_connector.py` (18, mirrors the GitHub suite: gate/mode
  withhold+deny, missing credential/egress fail-closed, arg validation, message +
  thread success via injected fetch, executor metadata-only, broker metadata-only
  event scrub, model exposure/validation) + a second-connector web vitest in
  `ConnectionsView.test.ts`.
- **Session gate:** full backend suite green (**1447 passed**, exit 0);
  `ruff check .` clean; mypy clean on changed sources; web lint/check/**86
  vitest**/build green; all five `scripts/validate_*.py` pass.
- **Live-verified.** 2026-07-11, hosted Anthropic Haiku 4.5 with a 1-hour
  operator key: all fail-closed paths confirmed; the fully-governed path made a
  **real** GET to `gmail.googleapis.com` (401 with a fake token — no real Gmail
  OAuth token in this env; token absent from output); and an **end-to-end model
  turn** where Haiku called `gmail_read(message, msg_abc123)` and reported the
  exact governed error (event log metadata-only: no token, `message_id` kept).
  Connections web view screenshotted in Gmail "Ready" and honest "Fail-closed"
  states (0 console errors). Full table in `docs/WEB_APP_LIVE_TEST.md`
  (2026-07-11 Gmail section).

### Prior state — Task 4 reference slice (done, this branch's base)

**Task 4 reference slice COMPLETE: governed GitHub read-only connector,
live-verified end-to-end on hosted Anthropic.** This is the reference pattern
for all Task 4 connectors (Gmail done above; Calendar / Slack replicate it).
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

**Next for Task 4:** all four read connectors are done (GitHub, Gmail, Calendar,
Slack). The remaining Task-4 work is the first **write** action end-to-end (must
require **approval**, not just `ask`; the write executor must be real). Two
follow-ons for the read connectors: (a) **live-verify Calendar + Slack** when
operator tokens for those services are available (repeat the Gmail live
procedure — governance fail-closed paths + real egress boundary + an end-to-end
model turn); (b) optional broadening (more resources per connector). Do NOT ship
a connector whose executor isn't real.

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
- **DONE** — all four read-only connectors: **GitHub**, **Gmail**, **Google
  Calendar** (`connector_gcal_runtime`, `gcal_read`), and **Slack**
  (`connector_slack_runtime`, `slack_read`), each reusing the reference template
  with a `ConnectorView` row in `get_connections()`. GitHub + Gmail are
  live-verified; Calendar + Slack are code-complete + unit-tested (live
  verification pending operator tokens). Do NOT ship a connector whose executor
  isn't real — fail closed until it is.
- Then add the first **write** action end-to-end (requires approval through the
  broker/policy/approval path — the write executor must be real). Tests: tool
  executes when configured+allowed, fails closed otherwise, approval required
  for write actions.
- Note: `config/channel-connectors.json` / `routes_channels.py` are the inbound
  *channel* surface (interfaces into Raiker), a different concept from these
  outbound service connectors — the connector pattern above is the one to grow.

**Task 5 — DONE** (project folders; see the state section at the top). Optional
follow-ons: per-project memory/attachments, and surfacing the active project
inline in Chat.

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
