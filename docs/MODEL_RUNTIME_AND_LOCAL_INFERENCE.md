# Model Runtime And Local Inference Specification

> Current truth (2026-06-21): the launchable local UIs are the plain local terminal client and the local web dashboard (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only; read-only governed views + governed prompt/turn/approval/runtime-mutation flows where approval resolution is metadata-only; adds no authority of its own). Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified but not implemented. Phase 3 is complete only for safe foundation/readiness slices A-P; Phase 4 memory MVP is implemented; Phase 5-7 remain metadata/readiness/contract surfaces unless code and tests explicitly prove runtime behavior. Runtime execution remains disabled for plugin execution, graph indexing, semantic/vector writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, remote/container/cloud/process/shell/network execution.


> **Code status: implemented — async OpenAI-compatible runtime.**
> `httpx>=0.27` is Raiker's runtime async HTTP transport. The OpenAI SDK and Pydantic are not used.
> FastAPI, LangChain, and LlamaIndex remain deferred unless governed API-server, adapter, or retrieval
> integrations are added. llama.cpp is the native local-first backend through the shared async
> OpenAI-compatible provider. Ollama, LM Studio, vLLM, generic OpenAI-compatible endpoints, and
> OpenRouter are profile-compatible through that same adapter. OpenRouter is hosted and policy-gated.
> The deterministic provider is test-only; production never silently falls back to deterministic or hosted
> providers. Live model listing is available for the selected provider when policy permits, model/reasoning
> state is persisted for the terminal session and the selected profile drives subsequent turns (Ollama and
> LM Studio auto-detect the served model), reasoning controls are capability-gated, and private
> chain-of-thought is never exposed.

Raiker is local-first. It must support local inference runtimes while allowing policy-controlled hosted providers.

The model router abstracts model providers, context limits, streaming, tool-call formats, safety constraints, cost controls, and explicit policy-denied fallback behaviour. Silent local-to-hosted fallback is forbidden.

### llama.cpp specifics (reference: `ggml-org/llama.cpp`)

- **Model format:** GGUF; quantization levels (e.g. `Q4_K_M`, `Q5_K_M`, `Q8_0`) trade memory/VRAM
  for quality. Profiles in `config/model-profiles.json` should record the quant + context length.
- **Server mode:** `llama-server` exposes an OpenAI-compatible `/v1/chat/completions` plus native
  `/completion`, `/embedding`, and `/health`. Raiker's `llama_cpp_server` adapter should target
  the OpenAI-compatible surface for chat and `/embedding` for future semantic memory.
- **Hardware/context:** context window (`n_ctx`), GPU offload layers, and thread count are
  launch-time settings; the launch contract must surface them and the health-check must read
  `/health` before binding a session.
- **Tool calls:** local models vary in native tool-call support; the router must support both
  native function-calling and a prompt-based tool-call mode, parsing either as **untrusted**
  structured proposals (see `docs/API_AND_CONTRACT_SCHEMAS.md`).

---

## Model Runtime Goals

Raiker must support:

1. mock provider for deterministic tests;
2. the llama.cpp server as the native default local backend, plus LM Studio;
3. OpenAI-compatible providers;
4. hosted providers when policy allows;
5. model profiles;
6. context window management;
7. streaming responses;
8. tool-call proposal parsing;
9. structured output validation;
10. explicit failure/fallback denial and retry;
11. privacy and egress policy;
12. cost and budget controls;
13. TUI-driven model launch and provider binding from the global `raiker` session.

---

## Provider Types

| Provider | Mode | Build phase | Status / default policy |
|---|---|---:|---|
| `mock` | deterministic test provider | Phase 1 | **implemented for tests only**; never a production fallback |
| `llama.cpp` | local `llama-server` (OpenAI-compatible HTTP) | Phase 2 | **implemented — native default** through async `httpx` OpenAI-compatible adapter; local allowed |
| `lm-studio` | local OpenAI-compatible API | Phase 2 | profile-compatible through shared adapter; served model auto-detected on `/model use`; disabled until provider detected/configured |
| `ollama` | local OpenAI-compatible API | Phase 2 | profile-compatible through shared adapter; served model auto-detected on `/model use`; disabled until provider detected/configured |
| `openai-compatible` | generic OpenAI-compatible endpoint | Phase 2/3 | profile only; local endpoint allowed, remote policy-gated |
| `vllm` | high-throughput GPU server (home lab / VPS) | Phase 5 | disabled until high-throughput serving + egress/budget policy approved |
| `hosted` | hosted API | Phase 3-5 | disabled until egress/budget policy configured |
| `custom_plugin` | plugin-provided provider | Phase 3 | disabled until plugin and permission review |

vLLM is positioned **after** the llama.cpp native path: same OpenAI-compatible tool-call shape,
but built for high-throughput GPU serving on a home lab or VPS. It is profile-compatible through the shared adapter and remains policy-gated for private-network/hosted use.

No provider is unspecified. A provider that is not enabled must still have a profile schema, validation path, privacy rule, event model, and failure behaviour.

---

## TUI Launch Contract

The human-facing command remains:

```bash
raiker
```

Running `raiker` opens the TUI. Model launch happens inside the TUI with `/launch`:

```text
/launch --provider <provider> --model <model>
```

Required TUI examples:

```text
/launch --provider llama.cpp --model local-gguf
/launch --provider lm-studio --model local-model
/launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
```

The native default profile is the configured llama.cpp OpenAI-compatible profile. Run a llama.cpp server
(`llama-server -m <model.gguf> --port 8080 --jinja`) at the configured endpoint before using
that profile for runtime calls. Raiker does not automatically bind based on health probing; health is
checked only through explicit health paths such as `/model health` or provider health APIs. `/launch`
is for switching profiles or pointing at a different local endpoint.

The canonical human-facing Raiker command is `raiker` and it must not depend on provider-specific shortcuts.

---

## Model Profile Schema

```json
{
  "schema_version": "1.0",
  "profile_id": "llama-cpp-local-gguf",
  "provider": "llama.cpp",
  "model": "local-gguf",
  "endpoint": "http://127.0.0.1:8080",
  "served_model_name": "local-gguf",
  "n_ctx": 8192,
  "max_tokens": 1024,
  "supports_streaming": true,
  "supports_tool_calls": true,
  "tool_call_protocol": "openai",
  "privacy": {
    "local_only": true,
    "allow_prompt_egress": false
  },
  "limits": {
    "requests_per_minute": 30,
    "max_parallel_requests": 2,
    "cost_budget_gbp": 0
  },
  "defaults": {
    "temperature": 0.2,
    "top_p": 0.9
  },
  "launch": {
    "canonical_tui_action": "/launch --provider llama.cpp --model local-gguf",
    "startup_check": "llama_server_health_check",
    "auto_start_provider": false
  }
}
```

The active runtime path is `ModelProfileRegistry -> ModelRouter -> ModelProviderFactory ->
AsyncOpenAICompatibleProvider` for llama.cpp and other OpenAI-compatible profiles. The provider
uses `httpx>=0.27` as the async HTTP transport and maps profile fields such as `endpoint`,
`served_model_name`, `temperature`, `max_tokens`, `timeout_seconds`, and `tool_call_protocol`
into OpenAI-compatible requests. A non-local `endpoint` is rejected unless the profile is explicitly
not `local_only` — model egress is a deliberate policy decision. The OpenAI SDK and Pydantic are
not used; FastAPI, LangChain, and LlamaIndex remain deferred. The deterministic provider is
test-only, and production does not fall back to it.

---

## Model Roles

Different roles may use different profiles:

| Role | Purpose |
|---|---|
| `chat` | General response generation. |
| `planner` | Structured planning. |
| `tool_selector` | Tool proposal generation. |
| `verifier` | Check whether result satisfies task. |
| `summariser` | Session/checkpoint/context summaries. |
| `memory_extractor` | Memory candidate extraction. |
| `memory_consolidator` | Consolidates episodic and project memory. |
| `skill_refiner` | Improves reusable skills after successful tasks. |
| `code_writer` | Code changes. |
| `security_reviewer` | Risk/security review. |
| `small_side_answer` | Fast side-question answers in TUI. |

Side-question answers should prefer a fast local model or deterministic runtime summary when possible.

---

## Tool Call Modes

Raiker must support multiple tool-call styles:

| Mode | Description |
|---|---|
| `native` | Provider-native function/tool calling. |
| `json_schema` | Model returns JSON matching schema. |
| `text_json` | Model writes fenced or raw JSON parsed by Raiker. |
| `plan_only` | Model proposes plan; runtime decides tools. |
| `disabled` | Model cannot propose tools. |

All tool calls must be validated before policy review.

---

## Structured Output Validation

Model output is untrusted.

Validation pipeline:

```text
raw model output
  -> parse
  -> schema validate
  -> reject unknown fields if strict
  -> risk classify
  -> policy review
  -> event log
```

Invalid structured output must not crash the runtime. It should produce a retry request or safe failure.

---

## Context Window Management

Raiker must track estimated input tokens, estimated output tokens, reserved safety margin, context source priority, truncation decisions, compaction events, and model-specific context limits.

Context priority:

1. system/security policy;
2. current user instruction;
3. active task state;
4. pending approvals;
5. current plan;
6. recent tool results;
7. relevant project files;
8. relevant memory;
9. graph context;
10. older session history.

---

## Streaming

Streaming model output must emit events:

- `model_request_started`
- `model_output_chunk`
- `model_tool_call_detected`
- `model_request_completed`
- `model_request_failed`
- `model_request_cancelled`

The TUI must be able to show streamed output while background tools/tasks continue.

---

## Privacy And Egress Policy

Hosted providers require policy approval if prompts may leave the machine.

Policy must consider provider, endpoint, model, data sensitivity, project policy, user approval, network allowlist, redaction status, and cost/budget.

Local-only profile must reject remote endpoints.

---

## Fallback Behaviour

Fallback must be explicit and logged.

Examples:

- local model unavailable -> use mock only in tests or ask user;
- tool-call model unavailable -> switch to plan-only mode;
- side-question model unavailable -> answer from event log summary;
- hosted fallback blocked by policy -> explain and stop.

No silent remote fallback is allowed.

---

## Quantisation And Hardware Profiles

Local model profiles may include quantisation type, RAM/VRAM requirement, CPU/GPU backend, context size, expected speed class, tool-call reliability notes, and recommended role.

Example:

```json
{
  "profile_id": "gemma-31b-cloud",
  "provider": "openai_compatible",
  "model": "gemma-4-31b",
  "recommended_roles": ["planner", "code_writer", "verifier"],
  "requires_network": true,
  "policy_required": true
}
```

---

## Model Events

Required events:

- `model_profile_loaded`
- `model_launch_requested`
- `model_launch_completed`
- `model_launch_failed`
- `model_request_started`
- `model_output_chunk`
- `model_structured_output_parsed`
- `model_structured_output_invalid`
- `model_tool_call_detected`
- `model_request_completed`
- `model_request_failed`
- `model_fallback_requested`
- `model_fallback_denied`
- `model_fallback_used`

---

## Testing Requirements

Tests must prove:

- global `raiker` command opens the TUI;
- TUI `/launch` selects provider and profile;
- provider shortcut command maps to the equivalent TUI launch action when adapter exists;
- mock provider deterministic output;
- unknown provider fails clearly;
- local-only profile rejects remote endpoint;
- invalid JSON tool call is rejected safely;
- model fallback is logged;
- token budget truncates low-priority context first;
- side-question role can answer from event log without interrupting task.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Status labels used by Raiker are `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Raiker now uses the real `httpx` package (`httpx.AsyncClient`) for async OpenAI-compatible provider transport. The repository-local `httpx.py` shim was removed and must not be restored. The OpenAI SDK and Pydantic are not used by this runtime.

Dependency decision: `httpx` is required and used. `fastapi` is deferred because this change does not implement a Raiker API/server surface. `langchain` is deferred because no governed adapter is implemented and it must not bypass Raiker tool, policy, approval, or event contracts. `llama-index` is deferred because no governed retrieval/indexing adapter is implemented and it must not bypass Raiker memory or provenance policy.

llama.cpp, Ollama, LM Studio, vLLM, generic OpenAI-compatible endpoints, and OpenRouter are represented through Raiker-owned async model-provider contracts. llama.cpp is the local-first native profile via the async OpenAI-compatible path. OpenRouter is hosted and policy-gated: it requires explicit hosted policy, egress and budget policy metadata, HTTPS, and a non-empty API key environment variable.

The deterministic provider is `test_only`; production gateways and normal CLI runtime do not fall back to it. If no real provider is configured or usable, runtime fails safely with a `no_real_model_provider_available`/provider-policy style error instead of silently switching to a mock or hosted backend. No silent local-to-hosted fallback is implemented. Provider support is offline-tested with `httpx.MockTransport`; real provider validation requires an operator-provided server or API key and was not performed here.

Model selection is session-scoped and persisted in the workspace SQLite store, and the selected profile is what subsequent prompts actually run on: the gateway resolves the persisted selection per turn and falls back to the native llama.cpp profile when none is set. `/model use` writes the selection, `/model current` reads it, and `/models` marks it. For local OpenAI-compatible providers that ship without a fixed model (Ollama, LM Studio), `/model use` auto-detects the served model from `/v1/models` when exactly one is available, or accepts an explicit `--provider/--model`; the resolved model is persisted (`model_session_state.model`). Reasoning controls are capability-gated. Private chain-of-thought is never exposed; any reasoning summary must be labeled as a summary, not raw reasoning. Model events use safe metadata only and must not include prompts, completions, stream chunks, Authorization headers, API keys, file contents, or tool outputs.
