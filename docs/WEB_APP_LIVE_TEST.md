# Web App Live Test — model backends

> A repeatable procedure + results matrix for exercising the Raiker web app
> against a real model backend. One round was run against **hosted Anthropic
> (Haiku 4.5)**; the same steps apply to every other backend (see the matrix).
> **Never commit an API key.** A test round either enters it through Raiker's
> encrypted Models UI or reads it from the owner's environment for that run;
> credentials never belong in a spec, command, log or screenshot.

## What this verifies

The full served web stack end to end: `raiker-web` (FastAPI + the built SPA) →
owner session mint → governed read endpoints → a **streamed prompt turn** →
the model provider → the audit event log. It also exercises the two features in
PR #106: the **user-owned fallback sequence** and **prompt caching + normalised
cache-hit metrics**.

## Result — 2026-08-21 (governed turn-based voice, preserved owner workspace)

The running built SPA was unlocked with Rahul's existing account and every
supplied hosted credential was entered through the Models reconnect dialog —
never a source file, process command or server environment. Browser speech was
driven through a deterministic Playwright recognition adapter because a
headless browser has no trustworthy physical-microphone path; the prompt itself
and the provider turn used the live FastAPI service, owner store, gateway and
configured Ollama model.

| Check | Result |
|---|---|
| Chat dictation is an editable draft | ✅ recognition produced `Reply with only: voice verified`; zero prompt requests before **Done** and zero before explicit **Send** |
| Prompt provenance crosses the real HTTP boundary | ✅ the sole prompt request carried `input_mode: dictated`; the live Ollama `gemma4:31b-cloud` turn returned exactly `voice verified` |
| Manual response playback | ✅ only the completed answer exposed **Read aloud**; activation exposed **Stop speaking**, and stopping restored the idle control |
| Build rollback | ✅ the draft changed from `keep this exact draft` while listening and **Cancel** restored that exact original text |
| Provider credentials entered through UI | ✅ Anthropic, OpenAI and OpenRouter reconnect dialogs accepted the supplied credentials into the encrypted instance vault |
| Anthropic readiness | ✅ `claude-sonnet-5` ready |
| OpenRouter readiness | ✅ `nvidia/nemotron-3.5-lightning:free` ready |
| OpenAI readiness | ⚠️ the supplied account could not execute pinned `gpt-5.4`; Raiker reported credential/access/billing guidance and did not claim readiness |
| Ollama readiness and execution | ✅ model row was ready and the real governed turn completed; a repeated readiness click exceeded the 30-second browser-control bound, while execution itself completed normally |
| Mocked browser regression | ✅ 5/5 Playwright tests, including desktop, 390×844 mobile, Settings persistence and zero Axe violations |
| Visual review | ✅ `output/playwright/voice-live-chat.png`, `voice-live-complete.png`, `voice-live-build.png`, plus the mocked desktop/mobile/Settings captures inspected at original resolution |

The OpenAI result is an external account/model-access limitation, not a Raiker
defect: the control failed closed and gave the owner an actionable reason. No
credential appears in these results or screenshots.

## Result — 2026-08-16 (first-run provider matrix, the Workbench board, both composers)

Fresh workspace, owner registered through the browser, **every credential typed
into the wizard's own field** — never given to the server as environment — so what
this round proves is the product's store-key → catalogue → pin → readiness → turn
chain from the very first screen. Spec:
[`apps/web/e2e/wizard-workbench-composer-live.spec.ts`](../../apps/web/e2e/wizard-workbench-composer-live.spec.ts)
(3 tests, 3 passed). Ollama was running locally; LM Studio was not installed, which
is a *result* the rows are required to state.

| Check | Result |
|---|---|
| One row per provider on the first-run model stage | ✅ Local GGUF, Ollama, LM Studio, OpenAI-compatible, Ollama Cloud, OpenRouter, Hugging Face, Anthropic, OpenAI, Gemini |
| Local runtimes are asked without being clicked | ✅ **9 models from Ollama**, `gemma4:31b-cloud` pre-selected |
| A runtime that is not running says so | ✅ *"LM Studio is not running on this device"*, and the same for OpenAI-compatible — no empty dropdown, no invented name |
| No GGUF in an approved root is its own state | ✅ *"No complete GGUF found"* with **Scan**; no false `Selected:` line for the slot alias (FIXED-223) |
| A key stored in the wizard produces that provider's own catalogue | ✅ Anthropic **10**, OpenRouter **413–414** (the catalogue moves), OpenAI **124** models, each read from the provider |
| A catalogue too long to scroll carries a filter | ✅ `Filter 414 models` / `Filter 124 models`; absent on Anthropic's 10 |
| No credential is rendered back into the page | ✅ asserted absent from `page.content()` after every save |
| A model pinned from a real catalogue | ✅ `Haiku 4.5` → *"Selected: Haiku 4.5"*, and `PUT /api/model-selection` recorded |
| Workbench has no composer | ✅ the prompt box, its mode tabs and its Start control are absent (FIXED-225) |
| The board's three groups | ✅ **Running now** / **Standing agents** / **Scheduled runs**, each stating its own emptiness |
| A real standing agent lands in the right group | ✅ a live daily routine reads `Runs daily · next cycle …` under **Standing agents**, and is **absent** from **Running now** — an armed cadence is not a running one |
| Safe-boundary stop from the board | ✅ **Stop** on every row, on the same governed `POST /api/interrupts` |
| Chat composer control set | ✅ `+`, `Chat | Build`, approval mode, execution environment, context capacity, model chip, context ring, Send — one bar under a full-width prompt |
| Build composer control set | ✅ the same, with the posture as one chip and a **Mode** menu offering Plan / Edit / Auto |
| The thinking budget lives in the model menu | ✅ **Effort** section with a **Thinking** switch; absent for a model that publishes no levels |
| The restructured composer still sends | ✅ a real governed turn on `claude-haiku-4-5-20251001` returned the exact marker |
| A completed turn offers **Branch** | ✅ FIXED-227, the last open row of GAP-CHAT C14 |
| Both themes | ✅ light and dark captured; dark is `#000` ground, `#ffffff` ink, `#ecd06f` accent |
| Console | ✅ 0 errors across all three tests |
| Visual review | ✅ `docs/plans/screenshots/working/r0816b-01-first-run-provider-matrix.png`, `r0816b-02-first-run-catalogues-listed.png`, `r0816b-03-first-run-model-pinned.png`, `r0816b-04-workbench-board.png`, `r0816b-05-workbench-standing-agent.png`, `r0816b-06-chat-composer.png`, `r0816b-07-chat-live-turn.png`, `r0816b-08-build-composer-mode.png`, `r0816b-09-chat-dark.png` inspected at original resolution |

**Two defects this round found and fixed, both of which a fixture could not have
found.** OpenRouter's catalogue read returned 200 OK and the row still said
"Asking OpenRouter…" forever, because the redaction layer had flattened three
41-character model ids into one identical `[REDACTED_SECRET]` and the duplicate
crashed a keyed render ([FIXED-224](plans/FIXED_ITEMS.md)). And the readiness
dialog's **Check again** reported "Check complete" having checked nothing
([FIXED-226](plans/FIXED_ITEMS.md)).

**One defect found and left open.** On Windows, a workspace nested deeper than
~170 characters cannot open its checkpoint locks, so pre-image capture fails and
the only trace is an event nothing displays —
[BUG-216](plans/TO_BE_FIXED.md). Confirmed pre-existing against a pristine
worktree.

---

## Result — 2026-08-15 (cross-provider review round, hosted Anthropic Haiku 4.5)

Fresh workspace, owner registered through the browser, every credential typed
into the Models connect dialog — never given to the server as environment — so
what this round proves is the product's connect → catalogue → readiness → turn
chain rather than a fixture. Spec:
[`apps/web/e2e/review-provider-matrix-live.spec.ts`](../../apps/web/e2e/review-provider-matrix-live.spec.ts).

| Check | Result |
|---|---|
| Owner registers and reaches the workbench | ✅ five-stage first-run wizard completed |
| Anthropic key stored through the connect dialog | ✅ card shows `Connected`; the key is asserted absent from the DOM |
| Live catalogue from the real provider | ✅ 11 models listed |
| **Test** resolves the pinned model | ✅ `Anthropic can reach claude-haiku-4-5-20251001`; chip `Ready · confirmed just now`; `POST /api/model-readiness/check` → 200 |
| Real governed turn in Chat | ✅ Raiker's own bubble returned `REVIEW CHAT OK` from Haiku 4.5 |
| Browser console errors | ✅ 0 across both scenarios |
| First-run wizard names unreachable local backends `Connected` | ❌ as found → ✅ fixed in this round as [FIXED-204](plans/FIXED_ITEMS.md#fixed-204--the-first-screen-an-owner-sees-called-five-unreachable-backends-connected); stage 02 now reads `Not checked yet` / `Choose a model first`, and the spec asserts `Connected` appears nowhere |

**Not exercisable in this environment, and not a Raiker result.** The sandbox
this round ran in answers `403` to `CONNECT` for every host except
`anthropic.com`, verified against the proxy directly
(`curl -v https://openrouter.ai/…` → `CONNECT tunnel failed, response 403`). So:

| Backend | Outcome |
|---|---|
| OpenRouter | Credential stored and accepted; catalogue unreachable. The card degraded honestly — *"Provider unreachable — type a model id if you know it"* — but simultaneously read `Connected`, the second half of BUG-198. After FIXED-204 the same state reads `Connection saved · Not checked · Provider unreachable` |
| OpenAI | Same egress denial; not reached |
| Ollama `gemma4:31b-cloud` | No Ollama binary and nothing on `11434` on this host; `ollama.com` also denied. This is what surfaced BUG-198: the wizard offered it as `Connected` |

Re-run on a host with open egress to complete the OpenRouter, OpenAI and Ollama
rows. Nothing in this round distinguishes those three backends' code paths — only
that the network they need was refused before Raiker was involved.

Evidence: `docs/plans/screenshots/working/review-01-signed-in.png`,
`review-02-anthropic-readiness.png`, `review-03-chat.png`,
`review-04-chat-answer.png`.

## Result — 2026-08-09 (BUG-69 reference-platform parity review, hosted Anthropic Haiku 4.5)

Fresh temporary workspace, owner registered through the browser, one Anthropic
key entered **only** through the Models connect dialog. The key holds no credit,
which makes it an exact fixture for the billing state added in this round: the
catalogue call succeeds and every inference call returns HTTP 400
`credit_balance_too_low`. Token generation was therefore **not** exercised; every
other link in the readiness chain was.

| Check | Result |
|---|---|
| First run routes a new owner to `#/model-setup` | ✅ `Choose how to run models`, resumable, Skip explains the consequence |
| Chat / Build / Tasks refuse to submit with no ready model | ✅ primary action disabled, draft preserved (the Workbench has no composer to gate — it is the board over work already running) |
| Connect dialog stores the key; value never rendered back | ✅ card shows `Connected`, no credential in the DOM |
| Live catalogue from the real provider | ✅ 10 Anthropic models listed, `claude-haiku-4-5-20251001` pinned |
| **Test** on the provider card runs the exact-model readiness check | ✅ FIXED-140 — was a catalogue listing that proved nothing |
| An empty account balance is its own state, not "unreachable" | ✅ FIXED-138 — card chip **No credit**, remediation names credit and quota |
| Models headline counts proven readiness | ✅ FIXED-140 — **0 models ready · 1 of 10 connected**, was "1 of 10 providers set up" |
| Chat repeats the same verdict and keeps the draft | ✅ Send stays disabled, sentence identical to the card |
| Browser console errors | ✅ 0 |

Evidence: [`plans/screenshots/working/bug69-models-quota-readiness-live.png`](plans/screenshots/working/bug69-models-quota-readiness-live.png)
and [`bug69-chat-quota-readiness-live.png`](plans/screenshots/working/bug69-chat-quota-readiness-live.png).

## Result — 2026-07-11 (Task 4: Gmail read-only connector, hosted Anthropic Haiku 4.5)

Second read connector, replicating the GitHub reference slice. Verified against
the **real** `gmail.googleapis.com` egress boundary. We hold no real Gmail OAuth
token in this environment, so the fully-governed path fails closed at the auth
boundary (`http_error:401`) — which still proves the whole gate → mode →
credential → egress chain, that the request reaches the fixed host with the
token in the header (never the URL/output), and that the tool is wired into the
real hosted-model turn. A real `RAIKER_GMAIL_TOKEN` would return the message
snippet + headers as untrusted data.

| Check | Result |
|---|---|
| Gate disabled (fresh workspace) fails closed | ✅ `connector_gate_disabled` |
| Default `ask` withholds the read (no network contact) | ✅ `connector_withheld_ask` |
| Decision mode `deny` blocks | ✅ `connector_denied_by_decision_mode` |
| Fail-closed without a credential | ✅ `connector_not_configured` (`RAIKER_GMAIL_TOKEN` unset) |
| Fail-closed without egress | ✅ `connector_egress_denied` (`gmail.googleapis.com` not allowlisted) |
| Argument validation, URL built server-side (`format=metadata`) | ✅ `unsupported_resource` / `invalid_message_id` |
| Fully governed (gate on + `allow` + token + egress): **real** GET to `gmail.googleapis.com` | ✅ reached Gmail → `connector_fetch_failed:http_error:401` (fake token); token **not** in output (`token in output: False`) |
| **End-to-end model turn**: hosted Haiku 4.5 given the `gmail_read` tool | ✅ `model_request_started → provider: anthropic, model: claude-haiku-4-5-20251001`; model called `gmail_read(message, msg_abc123)` (`tool_started`/`tool_failed gmail_read`); model reported the exact governed error type back to the user |
| Durable event log is metadata-only | ✅ owner token absent (0 hits) and fetched content absent; the non-secret `message_id` identifier retained (1 hit) |
| Browser: **Connections** view renders Gmail **Ready** | ✅ dark-theme card — capability gate / decision mode / owner credential (`***REDACTED***`) / egress (`gmail.googleapis.com`) all ✓; actions `read_message, read_thread`; shown next to a GitHub "Fail-closed" card |
| Browser: Gmail honest **Fail-closed** with remediation | ✅ light-theme card — credential + egress ✗ with per-check guidance; egress-allowlist warning banner; credential value never shown |
| Browser console errors | ✅ 0 (both states) |

The read-only Connections surface never reaches the network and never shows a
credential value (at the time of this run the response redaction layer scrubbed
even the env-var *name* to `***REDACTED***`; since `TO_BE_FIXED.md` FIXED-07 the
name is returned as-is — it is remediation guidance, not a credential — and the
value is still never read into a response). Enabling a connector stays on the
capability-gate + decision-mode control plane, gate-manager only.

## Result — 2026-07-11 (uploaded-document attachments: PDF + docx + image, hosted Anthropic Haiku 4.5)

Run with a 1-hour operator key held in the server process env only, against
three **real** user-supplied files. This round live-verifies Task 3's document
attachments (PDF + Word .docx text extraction) and re-confirms image vision,
end to end through the served stack, bound to `anthropic-hosted` /
`claude-haiku-4-5-20251001`.

| Check | Result |
|---|---|
| `POST /api/attachments` stores a real 2-page PDF (156 KB) | ✅ `att_…`, `kind: document` |
| `POST /api/attachments` stores a real .docx (202 KB) | ✅ `att_…`, `kind: document` |
| `POST /api/attachments` stores a real 1.76 MB JPEG | ✅ `att_…`, `kind: image`, metadata-only |
| Governed turn, PDF document → extracted text in context → real Haiku answer | ✅ document facts were extracted from the uploaded sample; the content remains only inside that document |
| Governed turn, .docx document → extracted text → real Haiku answer | ✅ document facts were extracted from the uploaded sample; the content remains only inside that document |
| Governed turn, JPG image (vision) → image block → real Haiku answer | ✅ correctly identified an **HAL Tejas** aircraft cutaway diagram (illustrator, publisher, maiden-flight date — all read from the image) |
| `model_request_started` bound model | ✅ `provider: anthropic, model: claude-haiku-4-5-20251001` |
| `model_request_completed` normalised usage | ✅ `{input_tokens: 2694, output_tokens: 37, cache_*: 0}` |
| `attachment_image_included` event | ✅ id + `image/jpeg` + `1761205` bytes + sha256; **no image base64 anywhere in the event log** (checked) |
| Browser (Chromium): composer "Document…" upload + image chip render; turn completes on Hosted · Anthropic | ✅ top bar "Hosted · Anthropic · egress open"; turn `completed`; **0 console errors** |

**Honest note:** in the browser round the model, given both a PDF and an image
and asked to read the CV, opened with "I'll read the CV document…" and finished
`completed` (the document text was already in context; the model's agentic
phrasing is model behaviour, not an attachment-path defect). The per-attachment
API turns above are the definitive content proof — each answer states facts that
exist only inside the uploaded file.

## Result — 2026-07-11 (uploaded-image vision turn + agentic tool loop, hosted Anthropic Haiku 4.5)

Run with a 1-hour operator key held in the server process env only. This round
verified the two changes on PR #108 live: **uploaded image attachments (vision)**
and the **effectively-unbounded tool loop**, and caught + fixed a real bug the
unit suite could not see (below).

| Check | Result |
|---|---|
| `POST /api/attachments` stores a real 2.2 MB JPEG (owner auth; metadata-only response) | ✅ `att_…`, `image/jpeg`, `2217857` bytes, sha256 returned |
| Vision turn: prompt + `{type:"image", attachment_id}` on the selected `anthropic-hosted` profile | ✅ real Haiku answer correctly describing the photographed dessert; `RAIKER_VISION_OK` |
| `attachment_image_included` event (id, media type, size, sha256) | ✅ present; **no image bytes/base64 anywhere in the event log** (checked) |
| Withheld path: same image bound to non-vision `raiker-local-llama-cpp` | ✅ `attachment_image_withheld` (`model_profile_lacks_vision_support`) before any provider contact; turn then failed honestly (`provider_connection_failed`, no local server running) |
| Agentic tool loop ("list files, read mission-brief.txt, tell me the codeword") | ✅ 3 model calls + 2 governed tool executions (`list_directory`, `read_file`); correct codeword extracted; `RAIKER_AGENT_OK`; the turn ended because the **model finished**, not a budget |
| Browser (Chromium): upload the image through the composer "+" → Image…, chip renders, streamed vision turn through the UI | ✅ `RAIKER_UI_VISION_OK`; **0 console errors** |

**Bug found live and fixed (tool round-trip):** the first agentic run failed on
the second model call with HTTP 400 → `provider_connection_failed`. Cause: the
orchestrator appended only the `role="tool"` result message — never the
assistant message carrying the model's `tool_use` — and the Anthropic Messages
API rejects a `tool_result` with no matching `tool_use` in a prior assistant
turn (strict OpenAI endpoints do the same for `tool_calls`). Earlier live
rounds were single-shot Q&A, so this had never been exercised against a hosted
provider. Fix: `ModelMessage.tool_calls` + the orchestrator now appends the
assistant tool-call message before each tool result; the Anthropic adapter
serializes `tool_use` blocks and `to_dict()` emits the OpenAI `tool_calls`
field (`test_tool_round_trip_carries_assistant_tool_call_message`,
`test_assistant_tool_calls_serialize_for_both_protocols`). Re-run: the loop
completed end-to-end (table above).

## Result — 2026-07-11 (Task 4: GitHub read-only connector, hosted Anthropic Haiku 4.5)

Reference slice for governed service connectors. Real owner GitHub token
(`RAIKER_GITHUB_TOKEN`, server env), `api.github.com` on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, `connector_github_runtime` enabled via the
control plane (threat ack + confirm), decision mode raised to `allow`.

| Check | Result |
|---|---|
| Default `ask` withholds the read (no network contact) | ✅ `connector_withheld_ask` |
| With mode `allow`: `GithubConnectorService.read` fetches a **real** PR | ✅ a configured test repository pull request was retrieved with its title, state, body, and untrusted-data framing |
| Owner token never appears in the tool output | ✅ verified (`token in output: False`) |
| **End-to-end model turn**: hosted Haiku 4.5 given the `github_read` tool | ✅ model called `github_read` for the pull request; tool action recorded `success` |
| Model answered from the fetched untrusted content | ✅ replied with the exact PR title + an accurate one-sentence summary |
| Fail-closed without a credential | ✅ `connector_not_configured` (token env unset) |
| Fail-closed without egress | ✅ `connector_egress_denied` (`api.github.com` not allowlisted) |
| Argument validation (bad repo/resource/number) fails closed, URL built server-side | ✅ `invalid_repo` / `unsupported_resource` / `invalid_number` |
| Browser: **Connections** view renders connector status | ✅ "Ready" card — capability gate / decision mode / owner credential (`***REDACTED***`) / egress allowlist all ✓; actions `read_issue, read_pull_request` |
| Browser: fresh workspace shows honest **fail-closed** with remediation | ✅ "Fail-closed" card — decision mode / credential / egress ✗ with per-check guidance; egress-allowlist warning banner |
| Browser console errors | ✅ 0 (both states) |

The read-only Connections surface never reaches the network and never shows a
credential value (at the time of this run the response redaction layer scrubbed
even the env-var *name* to `***REDACTED***`; since `TO_BE_FIXED.md` FIXED-07 the
name is returned as-is — it is remediation guidance, not a credential — and the
value is still never read into a response). Enabling a connector stays on the
capability-gate + decision-mode control plane, gate-manager only.

## Result — 2026-07-10 (hosted Anthropic, Haiku 4.5)

| Check | Result |
|---|---|
| `raiker-web` boots; `/api/health` 200 with `store: ok` | ✅ |
| Owner session mint (`POST /api/auth/session`) | ✅ |
| `GET /api/models` — `anthropic-hosted` selected, hosted gate `enabled_runtime`, fallback shows `raiker-local-llama-cpp`, cache `5m` | ✅ |
| Streamed turn (`POST /api/prompts/stream`) returns a real answer | ✅ `"The capital of Japan is Tokyo. RAIKER_WEB_OK"` |
| Turn bound to the requested model | ✅ `model_request_started → provider: anthropic, model: claude-haiku-4-5-20251001` |
| Normalised cache metrics on `model_request_completed` (streamed path) | ✅ `{input_tokens: 2013, output_tokens: 19, cache_read_tokens: 0, cache_write_tokens: 0, cache_hit: 0}` |
| Browser (Chromium): Models page renders selected card + "Cache 5m" chips + fallback editor | ✅ |
| Browser: live chat turn through the UI | ✅ `"6 times 7 is 42. RAIKER_UI_OK"` |
| Top-bar model chip | ✅ `Hosted · Anthropic · egress open` |
| Browser console errors | ✅ 0 |

**Honest note on caching:** the stable prefix (system prompt + workspace context)
was **2013 tokens** — just under Haiku's ~2048-token minimum cacheable size — so
no cache write occurred this round (`cache_write_tokens: 0`). The mechanism is
verified working: the `cache_control` breakpoint was sent, Anthropic returned the
cache accounting fields, and the streamed usage was captured and normalised into
the event. To observe a non-zero `cache_read_tokens`, use a model/prefix over the
minimum (Opus/Sonnet: ~1024; Haiku: ~2048) and send two turns in the same session.

## Result — 2026-07-10 (Task 3: path attachments, local stub backend)

The operator keys had expired by this round, so the model end of the turn ran
against a **local OpenAI-compatible stub** on the llama.cpp profile's endpoint
(`127.0.0.1:8080`) that answers based on what actually arrived in the request —
an honest end-to-end probe of the served path (raiker-web → gateway → context
gatherer → orchestrator → provider request) with no fabrication.

| Check | Result |
|---|---|
| `POST /api/prompts` with `attachments: [{type:"path", path:"mission-brief.txt"}]` | ✅ turn completed; the model's request contained the file's content (stub echoed the codeword back) |
| `context_gathered` event lists the `attachment` source | ✅ |
| Outside-workspace attachment (`/etc/passwd`) | ✅ denial note reached the model, **no file content did** (checked for distinctive passwd markers) |
| Invalid attachment shape (`type: "upload"`) | ✅ prompt rejected before a turn starts (`invalid_attachment_type`) |
| Browser: attach row adds a chip; sent bubble shows the attachment chip; input clears | ✅ |
| Browser: Models "Advisor model" section renders with the persisted advisor | ✅ `anthropic-hosted` |
| Browser console errors | ✅ 0 |

## Result — 2026-07-10 (Task 2: advisor model, hosted Anthropic)

| Check | Result |
|---|---|
| `advisor_model_runtime` gate enabled via control plane (threat ack + token) | ✅ |
| `PUT /api/model-advisor` persists `anthropic-hosted`; `GET /api/models` reflects it | ✅ |
| Decision mode default `ask` withholds the consult (no provider contact) | ✅ `advisor_withheld_ask` |
| With mode `allow`: `AdvisorService.consult` returns a real advisor answer | ✅ `claude-opus-4-8` answered; untrusted-data framing |
| Brokered `consult_advisor` tool through PolicyEngine + ToolBroker | ✅ policy `allow`, tool `success`, real answer returned to the caller |
| Durable event log is metadata-only (no question/answer text; lengths present) | ✅ verified against the session JSONL |
| Provider policy re-checked per call (hosted gate off ⇒ denied before network) | ✅ `advisor_provider_denied:provider_requires_explicit_policy_approval` |

## Result — 2026-07-10 (Task 7: provider model selection, hosted Anthropic)

| Check | Result |
|---|---|
| `GET /api/models/anthropic-hosted/provider-models` returns the provider's live catalogue | ✅ 10 models (claude-sonnet-5, claude-fable-5, claude-opus-4-8, …, claude-haiku-4-5-20251001) |
| Same endpoint with the hosted gate disabled | ✅ `status: policy_denied`, empty list, no network contact |
| Same endpoint for an unreachable local provider (llama.cpp) | ✅ `status: unavailable`, empty list — never fabricated |
| `PUT /api/model-selection` (`anthropic-hosted` + `claude-haiku-4-5-20251001`) | ✅ persisted; `GET /api/models` shows `current_model` + concrete model on the selected card |
| Streamed turn binds the selected model | ✅ `model_request_started → model: claude-haiku-4-5-20251001` |
| Per-turn override (`model_profile` + `model: claude-sonnet-4-6` on the prompt) | ✅ turn ran on `claude-sonnet-4-6`, exact answer returned |
| Browser: Models card picker lists the 10 live models; "Use model" re-selects through the UI | ✅ |
| Browser: Chat → Options → Provider populates a Model select from the live catalogue | ✅ 10 models |
| Browser: unreachable provider shows honest manual-entry fallback | ✅ "Provider unreachable — type a model id if you know it." |
| "Development preview" pill removed from the top bar | ✅ |
| Browser console errors | ✅ 0 |

## Result — 2026-07-29 (Chat / Build composer and persistence regression)

| Check | Result |
|---|---|
| Production web build | ✅ Vite build completed (242 modules) |
| Playwright Chat composer at 1440×1000 | ✅ prompt, model, effort, approval, context, and send controls visible |
| Playwright Build composer at 1440×1000 | ✅ repository, Plan/Edit/Auto, model, approval, context, and send controls visible |
| Keyboard guidance | ✅ inside both composer cards; Build and Chat share vertical rhythm |
| API-key restart regression | ✅ vault key restored from the workspace key file before model reads |
| Node 25.6.1 Storage warning | ✅ focused test passes with no warning |

Evidence: `docs/plans/screenshots/working/bug15-chat-composer.png` and
`docs/plans/screenshots/working/bug15-build-composer.png`. The Playwright test serves the
production bundle and mocks only authenticated API data, so it exercises the
real compiled Svelte UI without requiring live provider credentials.

## Result — 2026-07-29 (Settings / Models and expanded agent contracts)

| Check | Result |
|---|---|
| Vite 8 / Vitest 4 dependency audit | ✅ zero npm advisories |
| Multi-file unified patch | ✅ one preview/approval, two files changed, per-path checkpoint capture |
| Stale second file in a patch set | ✅ whole change rejected before the first write |
| Chat and Build model menus | ✅ menu opens and selection closes it on both pages |
| Settings at 1440×1000 | ✅ focused five-section rail; no redundant Storage page |
| Models at 1440×1000 | ✅ provider-backed model selector; no internal profile id visible |
| English browser checking | ✅ `spellcheck` and `en-US` active in both composers |
| Optional local LanguageTool adapter | ✅ authenticated, bounded, fail-soft when the operator-installed GPL/Java service is absent |

Evidence: `docs/plans/screenshots/working/settings-redesign.png` and
`docs/plans/screenshots/working/models-redesign.png`. The same committed Playwright suite
opens the real dropdown controls instead of checking only that their triggers
exist.

## Result — 2026-07-29 (Knowledge Map force-graph redesign)

| Check | Result |
|---|---|
| Production web build | ✅ Vite build completed with bundled `d3-force` and no external assets |
| Real force-directed layout | ✅ centre, repulsion, link, distance, collision, damping, and low-energy ambient motion |
| Graph-first surface at 1440×1000 | ✅ Raiker light-theme full-workspace canvas; no dotted dashboard grid or graph card boundary |
| Global/local graph interactions | ✅ global scope, node-centred local scope, relationship depth 1–3, hover neighbours, select/inspect, double-click centre, drag/pin, context menu, pan, zoom, and multi-select wiring |
| Floating settings | ✅ filters, search-driven colour groups, display controls, five physical-force controls, and Paused / Activity only / Always alive motion modes |
| Empty workspace guidance | ✅ instructional You → Workspace → Add first source topology replaces the single-node dead end |
| Governed live data | ✅ served `/api/brain` records and relationships remain the only persisted graph data; instructional starter nodes are explicitly virtual |
| Playwright live route and settings interaction | ✅ passed against the built SPA served by real FastAPI on `127.0.0.1:8765` |
| Application-wide theme sweep | ✅ all 23 pages/hub tabs rendered in explicit light and dark themes with distinct shared token palettes and zero console/page errors |

Evidence: `docs/plans/screenshots/working/knowledge-map-redesign-live.png`.
The first browser pass exposed and then verified the FIXED-51 reactive
simulation-loop correction; visual review then exposed and verified FIXED-52's
shared-theme integration. Both are recorded in `docs/plans/TO_BE_FIXED.md`.

## Result — 2026-08-01 (governance, execution, persistence, and attachment layout)

| Check | Result |
|---|---|
| Governed memory lifecycle | ✅ owner-scoped proposals, decisions, history, scope changes, expiry, edit, pin, forget, and purge controls exercised |
| Knowledge Map source review | ✅ bounded browse/review flow hides protected internals and persists owner graph preferences |
| Execution environments | ✅ local, container, SSH, and Daytona profiles render consistently; unavailable prerequisites fail closed |
| Local model capacity | ✅ `gemma4:31b-cloud` runtime capacity, scheduled refresh state, history, and owner override controls render |
| Reloaded approval | ✅ a parked file-write approval is restored after opening its persisted conversation and reloading the page |
| Chat and Build attachments | ✅ attached-file cards are sibling elements outside their user-message bubbles |
| Live model path | ✅ Anthropic and OpenRouter credentials connected through the UI; a real Ollama `gemma4:31b-cloud` Chat and Build turn completed |
| Browser assertions | ✅ `bug-29-34-live.spec.ts` passed in Chrome with no credential material written to the repository |

Evidence: `docs/plans/screenshots/working/173-BUG-33-capacity-admin-live.png`
through `179-BUG-34-reloaded-approval-live.png`. The source-review pass exposed
and verified protected-path filtering. Verification also identified the
cumulative Daytona billing reconciliation and accessibility diagnostics tracked
as BUG-42 and BUG-43 in `docs/plans/TO_BE_FIXED.md`.

## Result — 2026-08-08 (ADD-01 containerised tool execution)

| Check | Result |
|---|---|
| Real Docker bridge | ✅ `python:3.12-alpine` read `README.md` through the bounded JSON bridge with no network, read-only repository, read-only rootfs, dropped capabilities, and action-workspace cleanup |
| Container governance | ✅ `container_execution_cap` enabled through Permissions step-up; runtime, image, and tools selected only from server-advertised allowlists |
| Runtime settings | ✅ Docker profile persisted, showed `Docker · python:3.12-alpine`, `2 tools`, and `Read-only repository → writable output`, then became the selected Ready environment |
| Anthropic | ✅ credential entered through the password field in Models, Haiku 4.5 selected, real Chat response `ADD01 ANTHROPIC LIVE` |
| OpenRouter | ✅ credential entered through the password field in Models, provider catalogue used, real Chat response `ADD01 OPENROUTER LIVE` |
| Ollama | ✅ local `gemma4:31b-cloud` selected from the live catalogue, real Chat response `ADD01 OLLAMA LIVE` |
| Browser suite | ✅ `add-01-container-providers-live.spec.ts`; provider and Ollama response assertions plus container configuration, selection, and badge readiness |
| Visual review | ✅ five 1440×1000 screenshots inspected; no credential value visible, no clipped controls blocking the tested flow |

Evidence: `docs/plans/screenshots/working/add01-providers-connected-live.png`,
`add01-anthropic-turn-live.png`, `add01-openrouter-turn-live.png`,
`add01-ollama-turn-live.png`, and `add01-container-profile-live.png`. Live work
also exposed and closed FIXED-117 (cold import / stdin), FIXED-118 (broken Runtime
deep link), and FIXED-119 (ambient Ollama in offline tests).

## Repeatable procedure

## Result — 2026-08-08 (ADD-03 per-turn machine identity)

| Check | Result |
|---|---|
| Isolated host | ✅ fresh workspace, built SPA, real FastAPI runtime on `127.0.0.1:8765` |
| Owner/agent authority | ✅ Permissions rendered distinct Owner control and Raiker agent columns plus the Owner → Signed turn delegation rail |
| Anthropic | ✅ credential entered through Models UI; real Haiku 4.5 turn returned the exact acceptance text, proposed a governed file write as the machine actor, and recorded the human owner's denial separately |
| OpenRouter | ✅ credential entered through Models UI; real `openai/gpt-oss-20b:free` turn passed the same response, proposal, and denial contract |
| Ollama | ✅ local `gemma4:31b-cloud` passed the same response, proposal, and denial contract |
| Lifecycle evidence | ✅ `machine_identity_issued` and `machine_identity_deactivated` visible for each terminal turn; Activity shows the literal event actor separately from the contextual turn identity |
| Browser suite | ✅ Permissions plus all three provider cases passed individually in `add-03-machine-identity-providers-live.spec.ts`; a final combined retry run was provider-throttled after the already-green cases and did not replace those results |
| Visual review | ✅ seven 1440×1000 screenshots inspected at original resolution; no credential dialog/value or bearer material visible, and approval metadata remains readable without overlap |

The first screenshot pass exposed FIXED-120: full turn IDs made every machine
chip dominate the Activity actor column. A failing component regression was
added before the chip was changed to a compact visible turn ID; the complete
principal remains in the title and API. Focused component/view tests, Svelte
check, ESLint, production build, and each live provider case then passed. The
suite uses bounded page refreshes only for local API `429` responses; response,
identity, proposal, and authorization assertions are never retried away.

Evidence:
`docs/plans/screenshots/working/201-ADD-03-owner-agent-authority-live.png`
through `207-ADD-03-ollama-approval-attribution-live.png`.

The repeatable command shape is
`RAIKER_LIVE_ANTHROPIC_KEY=<ephemeral> RAIKER_LIVE_OPENROUTER_KEY=<ephemeral> npm --prefix apps/web run test:e2e:live -- e2e/add-03-machine-identity-providers-live.spec.ts`.
Values are supplied only to the Playwright process and entered into password
fields; they are never written to source, docs, screenshots, or test fixtures.

1. **Bootstrap + enable the backend's gate** (human owner). For a hosted
   provider this means: activate `local_single_user_runtime`, record the
   threat-model ack, and enable the runtime gate with a confirmation token. See
   `docs/HANDOFF.md` → "How a user turns on a hosted provider". Local backends
   (llama.cpp/Ollama/LM Studio) need no hosted gate.
2. **Set env for the server process only** (never a file):
   `RAIKER_MODEL_EGRESS_ALLOWLIST=<host>` and the provider key env (see matrix).
3. **Select the model:** `/model use …` (CLI), or persist a `ModelSessionState`
   for `TERMINAL_MODEL_SESSION_ID` with the profile id and a concrete model.
4. **Run:** `python apps/api/main.py --workspace <ws> --port 8765`, then mint a
   session and `POST /api/prompts/stream`. Confirm the answer, and read
   `GET /api/events?session_id=…` (or the store) for the
   `model_request_started` (bound model) and `model_request_completed`
   (`usage`) events.

## Per-model test matrix

`Verified` = a live governed turn has been run through the web app.
`Ready` = code path implemented; run the procedure above when a key/endpoint is
available. Egress hosts must be added to `RAIKER_MODEL_EGRESS_ALLOWLIST`.

| Provider | Profile id | Type | Egress host | Key env | Prompt caching | Status |
|---|---|---|---|---|---|---|
| Anthropic | `anthropic-hosted` | hosted | `api.anthropic.com` | `ANTHROPIC_API_KEY` | client `cache_control` breakpoint (5m/1h) | ✅ Verified (Haiku 4.5, 2026-08-08) |
| OpenAI | `openai-hosted` | hosted | `api.openai.com` | `OPENAI_API_KEY` | automatic server-side cache + `stream_options.include_usage`; no non-standard cache fields | ✅ Verified (`gpt-4o-mini` governed Build command, 2026-08-14) |
| Gemini | `gemini-hosted-openai-compatible` | hosted | `generativelanguage.googleapis.com` | `GEMINI_API_KEY` | automatic server-side | 🟡 Ready — egress blocked in this environment |
| OpenRouter | `openrouter-policy-gated` | hosted | `openrouter.ai` | `OPENROUTER_API_KEY` | automatic server-side | ✅ Verified (`openai/gpt-oss-20b:free` governed Build command, 2026-08-14) |
| llama.cpp | `raiker-local-llama-cpp` | local | `127.0.0.1:8080` | — | `cache_prompt: true` (server KV cache) | 🟡 Ready — needs a running llama.cpp server |
| Ollama | `ollama-local-openai-compatible` | local | `127.0.0.1:11434` | — | automatic server-side | ✅ Verified (`gemma4:31b-cloud` governed Build command, 2026-08-14) |
| LM Studio | `lm-studio-local-openai-compatible` | local | `127.0.0.1:1234` | — | automatic server-side | 🟡 Ready — needs LM Studio + a concrete model |
| Custom OpenAI-compatible | `generic-openai-compatible` | local or home-lab | user-selected | user vault | provider-dependent | 🟡 Ready — configure the endpoint and model in Raiker |

**Selecting a concrete model.** Profiles that ship a placeholder `<model>`
(Ollama/LM Studio/Custom OpenAI-compatible/OpenAI/Gemini/OpenRouter) take the concrete model at
selection time (`/model use --provider <p> --model <m>`). `anthropic-hosted`
also takes a concrete model at selection time; this test used
`claude-haiku-4-5-20251001`.

## Fallback sequence — how to test

Configure a sequence (Models → "Model fallback sequence", or `PUT
/api/model-fallback`), then make the primary provider fail (e.g. select a hosted
model with the gate on but no reachable key/host). The turn should emit
`model_fallback_engaged` and complete on the next reachable candidate; if every
candidate fails it fails closed with `model_unavailable`. Fallback never opens a
policy-denied provider — a denied candidate is skipped, not opened.


## Result — 2026-08-09 (BUG-69 universal model readiness)

A fresh isolated workspace was exercised through the built SPA in real Chromium.
Credentials were entered only through Models and were not persisted in evidence.

| Check | Result |
|---|---|
| First-run setup | ✅ Provider/local setup is prompted before model-backed work |
| Universal gate | ✅ Chat, Build, Tasks, and Schedule share the exact readiness gate; actions are disabled and drafts preserved |
| Ollama | ✅ Local `gemma4:31b-cloud` answered a bounded direct request and passed exact catalogue readiness |
| OpenRouter | ✅ `openai/gpt-4o-mini` passed catalogue plus execution preflight; a full governed turn parked its local action for approval without execution |
| Anthropic | ✅ Live catalogue/authentication succeeded; the account's insufficient-credit execution refusal was classified and Send remained disabled |
| Local library | ✅ An owner-approved root was scanned and GGUF name, architecture, and quantization were shown; no ambient path was scanned |
| Hugging Face | ✅ Live Hub search showed licence, immutable revision and GGUF-first choices; a tiny permissive GGUF downloaded into an approved root and reached completed managed llama.cpp deployment |
| Browser console | ✅ No application errors in the BUG-69 specs |

Specs: `bug-69-model-readiness-live.spec.ts`,
`bug-69-local-model-library-live.spec.ts`, and
`bug-69-huggingface-live.spec.ts`. Screenshots 208–213 are indexed in
`docs/plans/screenshots/README.md` (208–214).

## Result — 2026-08-10 (known-limits round, FIXED-161 to FIXED-170)

A fresh isolated workspace was exercised through the built SPA in real Chromium.
The Anthropic credential was entered only through Models and is not in evidence.

| Check | Result |
|---|---|
| Code-split routes | ✅ All eleven secondary destinations mount with content and no console error; the entry chunk is 237 kB (was 690 kB) and the build reports no size warning |
| Plugin supply chain | ✅ Extensions → Plugins states the workspace signing posture in words and names the two variables that raise it; installs are unaffected |
| Monitored capabilities | ✅ Settings → Security & sign-in lists containment for every capability family, not only MCP, and says so on an empty workspace rather than showing nothing |
| Circuit breaker | ✅ Three consecutive connector failures contained the subject as `paused` with its reason, streak and last failure code, raised a matching high-severity finding, and **Resume** cleared it in one press |
| Readiness window | ✅ The default reads 5 minutes, 30 survived Save changes and a navigation round trip, and the server resolved 30 for that owner |
| Readiness chip | ✅ `Ready · confirmed just now`, naming the exact model the provider reached |
| Model activity | ✅ Durable operations surface loads and states that failed work is never silently retried |
| Live turn | ✅ Anthropic Haiku 4.5 answered with the exact requested marker |
| Browser console | ✅ No application errors in either spec |

Specs: `bug-74-84-known-limits-live.spec.ts` and
`containment-surface-live.spec.ts`, both re-runnable against an already-driven
workspace. Screenshots `round0810-01` to `round0810-11` in
`docs/plans/screenshots/working/`.

## Result — 2026-08-14 (governed shell and provider matrix)

A disposable loopback workspace was exercised through the built SPA in real
Chromium. Each credential was entered through Models, was never placed in a
command or document, and is absent from screenshots and repository state. The
service and browser were stopped after the run.

| Check | Result |
|---|---|
| Governed terminal | ✅ A real exact-argv `git --version` command produced durable redacted output and an immutable receipt from the final rebuilt SPA; the earlier `git status --short` output/receipt also survived two app reloads |
| Authority path | ✅ Direct `POST /api/command-runs` is unavailable; approved `shell`/`process` and standing-grant `run_command` use the shared service and store their authority identity |
| Selected environment | ✅ Local host access was explicit and labelled reduced isolation; an unavailable selected backend failed closed with no host fallback |
| Build navigation recovery | ✅ Returning from Approvals refreshes both collapsed and already-open terminals; starting a new Build session replaces a stale selected run id with that session's newest run |
| Container readiness | 🟡 Docker CLI was present but its daemon named pipe was unreachable, so the digest-pinned command backend remained unavailable and no live container-execution claim is made |
| Ollama | ✅ `gemma4:31b-cloud` proposed and completed `git --version` through Build, approval, local execution, redacted output, and receipt |
| Anthropic | ✅ `claude-sonnet-4-6` completed the same governed Build command path |
| OpenAI | ✅ `gpt-4o-mini` completed the same governed Build command path after removing unsupported explicit cache fields; OpenAI caching remains automatic |
| OpenRouter | ✅ `openai/gpt-oss-20b:free` completed the same governed Build command path |
| Browser suite | ✅ `governed-shell-provider-matrix-live.spec.ts`: 4/4 provider cases passed serially in 38.5 seconds |
| Visual review | ✅ `docs/plans/screenshots/working/governed-shell-{anthropic,openrouter,openai,ollama}-live.png` were inspected at original resolution for command/provider identity, authority, isolation, output, receipt, clipping, and secret absence |

This run proves the foreground local shell, durability, governance evidence,
and the complete four-provider model-to-command path. It does not prove PTY/background input,
service-restart reattachment, filtered egress, credential quarantine, SSH,
Daytona, or live Docker execution; those remain BUG-194.

## Result — 2026-08-15 (BUG-206 tool rows, BUG-207 model reasoning)

A disposable loopback workspace was created for each run and destroyed after it.
The Anthropic credential was entered through Models by the spec, was never placed
in a command, a document or a screenshot, and is absent from repository state.
The service and browser were stopped after the run.

| Check | Result |
|---|---|
| Tool rows in Chat | ✅ A two-call turn rendered `List folder · the workspace root · done` then `Read file · README.md · done`, one line each, in the model's proposal order |
| Proposal order under concurrency | ✅ Independent reads run in parallel (B4) and settled out of order; the rows still read in the order the model asked, because they are opened from the validated proposals |
| Nothing raw reaches the row | ✅ The turn's `.tool-activity` text contained no `{`, no `read_file` and no `list_directory` — no argument JSON and no tool identifier |
| The element list BUG-206 found empty | ✅ `tool-activity`, `tool-row`, `tool-glyph`, `tool-label`, `tool-action` are now in it |
| A call waiting on a decision | ✅ `Write file · notes.md · waiting for your decision`, beside its approval card; the phrase appears exactly once, so a screen reader hears it once |
| A refused call (batching stub) | ✅ `Read file · ../escape.md` with `refused — workspace_boundary_denied, outside_workspace:path`, directly above the `List folder` row that succeeded in the same batch; the old `.refusal-card` is absent |
| Model reasoning, live | ✅ With **Thinking: adaptive**, `claude-haiku-4-5-20251001` streamed its own working for 17 × 23 into the collapsed block; it names the numbers the owner typed, which no fixed string could |
| The thinking spelling negotiated | ✅ Haiku 4.5 refuses `thinking.type.adaptive`; the provider read the alternative out of the refusal, re-issued once, and the turn thought rather than failing with a 400 |
| The three canned sentences | ✅ Absent, as is the "See what Raiker is thinking" label |
| Collapse on answer | ✅ `aria-expanded="false"` once the answer starts, still openable |
| Reasoning off | ✅ No reasoning section at all, and no tool activity for a turn that called nothing |
| Build parity | ✅ Same rows, same reasoning block, same collapse, from the same components and data path |
| A decided call settles | 🟡 **Not proven live.** The approved call is not re-brokered on resume, so the runtime settles the row from the recorded outcome and the client merges rather than replaces — asserted in `test_turn_model_binding.py`, `resumed_call_row_status` and `chatPresentation.test.ts`, but watching it settle needs the running tab to stay mounted while the decision is made elsewhere, and that step was flaky rather than evidential |
| Browser suites | ✅ `bug-206-207-tool-rows-and-reasoning-live.spec.ts` 6/6; `bug-52-first-pass-denial-live.spec.ts` 4/4 against the batching stub; `composer.spec.ts` (mocked) 4/4 |
| All-pages sweep | ✅ `all-pages-live.spec.ts` captured all 24 routes with **0 console errors**, after the sweep's own stale sign-in was fixed (FIXED-215) |
| Visual review | ✅ `docs/plans/screenshots/working/bug-206-live-tool-rows-{streaming,settled}.png`, `bug-206-live-tool-row-waiting.png`, `bug-207-live-reasoning-{streaming,settled}.png`, `bug-207-live-no-reasoning.png`, `bug-206-207-live-build-turn.png` inspected at original resolution for row order, wrapping, state colour, and secret absence |

This run proves the live transcript surface end to end on hosted Anthropic: what
a turn did, what it thought, and what it refused. It does **not** prove that
either survives a reload — neither is persisted, which is
[BUG-215](plans/TO_BE_FIXED.md#bug-215--reasoning-is-shown-live-and-then-forgotten).
