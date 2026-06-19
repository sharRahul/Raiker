# Model Runtime And Local Inference Specification

> **Code status: implemented — llama.cpp server is the native default backend.**
> `raiker/models/providers/llama_cpp_server.py` is a real provider that talks to a running
> `llama-server` over its OpenAI-compatible HTTP API using only the Python standard library
> (`http.client`), so Raiker keeps zero runtime dependencies. `raiker/models/router.py` routes
> the `mock` and `llama.cpp` providers; other providers (`lm-studio`, `openai-compatible`,
> `vllm`, `hosted`) remain gated and raise `provider_not_wired`. At startup the router probes
> the llama.cpp `/health` endpoint (`ModelRouter.default_provider`): if a server is reachable it
> becomes the default backend; otherwise Raiker falls back to the deterministic `mock` provider,
> which keeps tests and offline runs hermetic. Model output (text and tool calls) is validated by
> `raiker/models/tool_call_validation.py` before any tool runs (OWASP LLM05).
>
> **Not Ollama.** Raiker's native local backend is the llama.cpp server. Ollama is intentionally
> not supported. The later high-throughput option is **vLLM** (see "Provider Types"), enabled only
> after the llama.cpp path is solid and egress/budget policy is configured.

Raiker is local-first. It must support local inference runtimes while allowing policy-controlled hosted providers.

The model router abstracts model providers, context limits, streaming, tool-call formats, safety constraints, cost controls, and fallback behaviour.

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
10. fallback and retry;
11. privacy and egress policy;
12. cost and budget controls;
13. TUI-driven model launch and provider binding from the global `raiker` session.

---

## Provider Types

| Provider | Mode | Build phase | Status / default policy |
|---|---|---:|---|
| `mock` | deterministic local test/offline provider | Phase 1 | **implemented**; default fallback when no server is reachable |
| `llama.cpp` | local `llama-server` (OpenAI-compatible HTTP) | Phase 2 | **implemented — native default** when `/health` is reachable; local allowed |
| `lm-studio` | local OpenAI-compatible API | Phase 2 | profile only; `provider_not_wired` |
| `openai-compatible` | generic OpenAI-compatible endpoint | Phase 2/3 | profile only; local endpoint allowed, remote policy-gated |
| `vllm` | high-throughput GPU server (home lab / VPS) | Phase 5 | disabled until high-throughput serving + egress/budget policy approved |
| `hosted` | hosted API | Phase 3-5 | disabled until egress/budget policy configured |
| `custom_plugin` | plugin-provided provider | Phase 3 | disabled until plugin and permission review |

vLLM is positioned **after** the llama.cpp native path: same OpenAI-compatible tool-call shape,
but built for high-throughput GPU serving on a home lab or VPS. It is not wired today.

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

The native default backend needs no explicit launch: run a llama.cpp server
(`llama-server -m <model.gguf> --port 8080 --jinja`) and Raiker binds to it automatically when
its `/health` endpoint is reachable. `/launch` is for switching profiles or pointing at a
different local endpoint.

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

The runtime maps these fields to `raiker/models/providers/llama_cpp_server.LlamaCppServerProvider`
(`endpoint`, `served_model_name`, `n_ctx`, `temperature`, `max_tokens`, `timeout_seconds`,
`tool_call_protocol`). A non-local `endpoint` is rejected unless the profile is explicitly not
`local_only` — model egress is a deliberate policy decision.

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
