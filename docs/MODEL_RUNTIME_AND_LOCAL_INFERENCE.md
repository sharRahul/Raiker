# Model Runtime And Local Inference Specification

> **Code status: partial — mock provider only.** The provider *contract* and the model-profile
> registry exist, but `raiker/models/router.py` raises `provider_not_wired_in_phase_1` for every
> provider except `mock`. **No local-inference client (llama.cpp/Ollama/LM Studio) is wired**;
> `raiker/models/health.py` only *detects* a local binary, it does not run inference. The
> implemented `mock` provider returns deterministic placeholder text. Note: the IMPLEMENTATION
> ledger lists "Local provider health-check" as Phase 2 `implemented_verified` — that refers to
> the **health-check only**, not to working inference. Until a real adapter lands, treat local
> inference as `specified_not_implemented`.
>
> **First implementation target (recommended):** a `raiker/models/providers/` package with one
> real adapter — `llama_cpp_server` (HTTP `/completion` + `/v1/chat/completions`, GGUF model,
> streaming) or `ollama` (`/api/chat`) — behind the existing provider contract, selected by
> profile, and still routed through policy/egress gates.

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
2. local providers such as llama.cpp, Ollama, and LM Studio;
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

| Provider | Mode | Build phase | Default policy |
|---|---|---:|---|
| `mock` | deterministic local test provider | Phase 1 | enabled for tests |
| `llama_cpp_server` | local llama.cpp HTTP server | Phase 2 | local allowed |
| `ollama` | local Ollama API | Phase 2 | local allowed |
| `lm_studio` | local OpenAI-compatible API | Phase 2 | local allowed |
| `openai_compatible` | generic OpenAI-compatible endpoint | Phase 2/3 | local endpoint allowed, remote endpoint policy-gated |
| `openrouter` | hosted router | Phase 3 | disabled until user/provider policy configured |
| `anthropic` | hosted API | Phase 3 | disabled until user/provider policy configured |
| `modal` | hosted GPU inference | Phase 5 | disabled until budget and data policy configured |
| `custom_plugin` | plugin-provided provider | Phase 3 | disabled until plugin and permission review |

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
/launch --provider ollama --model qwen3.5-coder:9b
/launch --provider llama.cpp --model /models/qwen.gguf --ctx 32768
/launch --provider lm-studio --model local-model
/launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
```

Provider-specific shortcut commands may exist when a provider supports extension commands. A shortcut shaped like this:

```bash
ollama launch raiker --model <model>
```

must resolve to the equivalent Raiker TUI launch action:

```text
/launch --provider ollama --model <model>
```

The canonical human-facing Raiker command is `raiker` and it must not depend on provider-specific shortcuts.

---

## Model Profile Schema

```json
{
  "schema_version": "1.0",
  "profile_id": "qwen-local-coder",
  "provider": "ollama",
  "model": "qwen3.5-coder:9b",
  "endpoint": "http://localhost:11434",
  "context_window_tokens": 32768,
  "max_output_tokens": 4096,
  "supports_streaming": true,
  "supports_tool_calls": false,
  "supports_json_schema": false,
  "tool_call_mode": "text_json",
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
    "canonical_tui_action": "/launch --provider ollama --model qwen3.5-coder:9b",
    "startup_check": "provider_health_check",
    "auto_start_provider": false
  }
}
```

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
