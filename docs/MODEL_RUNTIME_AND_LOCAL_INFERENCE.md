# Model Runtime And Local Inference Specification

Raiker is local-first. It must support local inference runtimes while allowing policy-controlled hosted providers.

The model router abstracts model providers, context limits, streaming, tool-call formats, safety constraints, cost controls, and fallback behaviour.

---

## Model Runtime Goals

Raiker must support:

1. mock provider for deterministic tests;
2. local providers such as llama.cpp, Ollama, and LM Studio;
3. OpenAI-compatible providers;
4. cloud providers when policy allows;
5. model profiles;
6. context window management;
7. streaming responses;
8. tool-call proposal parsing;
9. structured output validation;
10. fallback and retry;
11. privacy and egress policy;
12. cost and budget controls.

---

## Provider Types

| Provider | Mode | Phase |
|---|---|---:|
| `mock` | deterministic local test provider | Phase 1 |
| `llama_cpp_server` | local llama.cpp HTTP server | Phase 2 |
| `ollama` | local Ollama API | Phase 2 |
| `lm_studio` | local OpenAI-compatible API | Phase 2 |
| `openai_compatible` | generic OpenAI-compatible endpoint | Phase 2/3 |
| `openrouter` | hosted router | policy-controlled future |
| `anthropic` | hosted API | policy-controlled future |
| `modal` | hosted GPU inference | policy-controlled future |
| `custom_plugin` | plugin-provided provider | future |

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

Raiker must track:

- estimated input tokens;
- estimated output tokens;
- reserved safety margin;
- context source priority;
- truncation decisions;
- compaction events;
- model-specific context limits.

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

Policy must consider:

- provider;
- endpoint;
- model;
- data sensitivity;
- project policy;
- user approval;
- network allowlist;
- redaction status;
- cost/budget.

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

Local model profiles may include:

- quantisation type;
- RAM/VRAM requirement;
- CPU/GPU backend;
- context size;
- expected speed class;
- tool-call reliability notes;
- recommended role.

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

- mock provider deterministic output;
- unknown provider fails clearly;
- local-only profile rejects remote endpoint;
- invalid JSON tool call is rejected safely;
- model fallback is logged;
- token budget truncates low-priority context first;
- side-question role can answer from event log without interrupting task.
