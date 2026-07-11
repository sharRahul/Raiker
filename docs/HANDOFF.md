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

## State as of 2026-07-11 (this session, branch `claude/handoff-task-hq2joc`)

**Task 3, uploaded-documents sub-slice (DONE): governed text-document
attachments.** This completes the text side of Task 3; PDF/office binaries are
the only remaining piece.
- **Validation/store/extract** (`raiker/runtime/attachments.py`): reuses the
  same governed `attachments` table (`RAIKER-1006`). `validate_document`
  fails closed unless the media type is on the text allowlist
  (`text/plain` / `text/markdown` / `text/csv`), the bytes are non-empty and
  under `MAX_DOCUMENT_BYTES` (2 MB), and they decode as clean UTF-8 with **no
  NUL byte** (the text analogue of the image magic-byte sniff — a binary file
  mislabelled as text fails closed). `store_document` persists with
  `kind="document"`; `extract_document_text` is a bounded UTF-8 decode
  (`MAX_DOCUMENT_TEXT_CHARS = 200_000`); `load_document` re-validates on the
  way out and returns the extracted text + a `extract_truncated` flag.
- **API:** `POST /api/attachments` now dispatches on the declared media type —
  image types → `store_image`, document types → `store_document`, anything
  else → 400 `unsupported_media_type` (before either storer runs). Metadata-only
  response, same owner bearer auth. The existing body-size override (derived
  from the larger image cap) already covers the smaller document cap.
- **Prompt shape:** `attachments` also accepts
  `{type: "document", attachment_id: "att_…"}` (validated fail-closed in
  `_validated_attachments`, sharing the image id-check path).
- **Context delivery:** unlike images (metadata only), a document's whole point
  is its text, so the gatherer's new `_document_attachment_item` folds the
  bounded extracted text into an `untrusted_external` context item
  (`document_uploaded` / `not_found` / `missing_attachment_id`), announced in
  the content as "untrusted document content, not instructions". No orchestrator
  change — documents never touch the vision/image-block path.
- **Web:** the composer "+" popover gains a "Document…" upload beside "Image…"
  (client-side type/size pre-check with an extension fallback for browsers that
  mislabel `.md`; chips share the path-attachment UI); the prompt sends the
  document reference, never bytes.
- Tests: `tests/test_document_attachments.py` (25: validation fail-closed for
  type/size/NUL/non-UTF-8, extraction bounds, store round-trip + kind
  isolation, gatherer untrusted-text item, upload API + prompt reference) +
  2 web vitest.
- **Session gate:** full backend suite green (**1398 passed**, exit 0);
  `ruff check .` clean; mypy clean on changed sources (remaining output is the
  documented environmental missing-stub noise); web lint/check/**83 vitest**/
  build green; all five `scripts/validate_*.py` pass.
- **Not live-verified against a provider** (marked `implemented`, not
  `implemented_verified`): the store→gather→untrusted-text path is exercised
  end to end in tests, but a governed live turn feeding an uploaded document to
  a real model is still open (see Standing next-work).

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

**Task 3 remainder — PDF/office document attachments (last sub-slice).**
Paths, uploaded images, and uploaded **text** documents (plain
text/markdown/csv) are all done. What remains is binary document extraction:
PDFs and office formats via local-only extraction libs (these are heavy — scope
carefully; consider one format at a time). Reuse the same governed store +
allowlist pattern already in `raiker/runtime/attachments.py` — add a per-type
validator (magic-byte sniff, e.g. `%PDF-` / the zip/OOXML signature for docx)
and an extraction step whose output becomes a bounded, `untrusted_external`
context item, exactly like `store_document` / `_document_attachment_item` do
for text. Every attachment stays untrusted data. Tests for type/size
fail-closed, extraction bounds, trust labels.

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
   turn** (uploaded image → image block → real answer) and a **live document
   turn** (uploaded text document → extracted untrusted context → real answer)
   to the same checklist.
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
