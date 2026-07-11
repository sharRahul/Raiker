# Web App Live Test — model backends

> A repeatable procedure + results matrix for exercising the Raiker web app
> against a real model backend. One round was run against **hosted Anthropic
> (Haiku 4.5)**; the same steps apply to every other backend (see the matrix).
> **Never commit an API key.** Keys are read from the owner's environment only,
> for the duration of the test.

## What this verifies

The full served web stack end to end: `raiker-web` (FastAPI + the built SPA) →
owner session mint → governed read endpoints → a **streamed prompt turn** →
the model provider → the audit event log. It also exercises the two features in
PR #106: the **user-owned fallback sequence** and **prompt caching + normalised
cache-hit metrics**.

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

## Result — 2026-07-10 (hosted Anthropic, Haiku 4.5)

| Check | Result |
|---|---|
| `raiker-web` boots; `/api/health` 200 | ✅ |
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

## Repeatable procedure

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
| Anthropic | `anthropic-hosted` | hosted | `api.anthropic.com` | `ANTHROPIC_API_KEY` | client `cache_control` breakpoint (5m/1h) | ✅ Verified (Haiku 4.5, 2026-07-10) |
| OpenAI | `openai-hosted` | hosted | `api.openai.com` | `OPENAI_API_KEY` | `prompt_cache_key` + `stream_options.include_usage` (server-side cache) | 🟡 Ready — cloud egress proxy blocks this host; run on a machine that can reach it |
| Gemini | `gemini-hosted-openai-compatible` | hosted | `generativelanguage.googleapis.com` | `GEMINI_API_KEY` | automatic server-side | 🟡 Ready — egress blocked in this environment |
| OpenRouter | `openrouter-policy-gated` | hosted | `openrouter.ai` | `OPENROUTER_API_KEY` | automatic server-side | 🟡 Ready — egress blocked in this environment |
| llama.cpp | `raiker-local-llama-cpp` | local | `127.0.0.1:8080` | — | `cache_prompt: true` (server KV cache) | 🟡 Ready — needs a running llama.cpp server |
| Ollama | `ollama-local-openai-compatible` | local | `127.0.0.1:11434` | — | automatic server-side | 🟡 Ready — needs Ollama + a concrete model |
| LM Studio | `lm-studio-local-openai-compatible` | local | `127.0.0.1:1234` | — | automatic server-side | 🟡 Ready — needs LM Studio + a concrete model |
| vLLM | `vllm-homelab-openai-compatible` | home-lab | `192.168.1.50:8000` | — | automatic prefix caching | 🟡 Ready — needs a reachable vLLM endpoint (egress-gated) |

**Selecting a concrete model.** Profiles that ship a placeholder `<model>`
(Ollama/LM Studio/vLLM/OpenAI/Gemini/OpenRouter) take the concrete model at
selection time (`/model use --provider <p> --model <m>`). `anthropic-hosted`
ships a concrete model (`claude-opus-4-8`); to run a different Anthropic model
(e.g. Haiku), select it with an explicit model override — this test used
`claude-haiku-4-5-20251001`.

## Fallback sequence — how to test

Configure a sequence (Models → "Model fallback sequence", or `PUT
/api/model-fallback`), then make the primary provider fail (e.g. select a hosted
model with the gate on but no reachable key/host). The turn should emit
`model_fallback_engaged` and complete on the next reachable candidate; if every
candidate fails it fails closed with `model_unavailable`. Fallback never opens a
policy-denied provider — a denied candidate is skipped, not opened.
