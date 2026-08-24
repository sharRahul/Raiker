# Model Provider Contract

This document defines the implementation contract for model providers. `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` defines model runtime behaviour; this file defines the interface a provider adapter must implement.

**Implemented adapters (re-checked 2026-08-23).** `raiker/models/providers/`
ships **three**, over the `AsyncModelProvider` protocol in `base.py`:
`anthropic_messages.py`, `openai_compatible.py` (which serves OpenAI, Gemini,
OpenRouter, Hugging Face Inference Providers, Ollama, Ollama Cloud, LM Studio,
vLLM and any owner-supplied OpenAI-compatible endpoint) and
`llama_cpp_server.py`. A provider is reachable only once the owner configures
it, its exact model passes readiness, and its endpoint satisfies
`raiker/models/endpoint_policy.py`; an unconfigured provider still fails closed.
See [Models and local inference](MODEL_RUNTIME_AND_LOCAL_INFERENCE.md).

> **There is no `mock` provider, and there must not be one.** This document said
> four adapters shipped, counting a deterministic `mock`. No such adapter exists.
> `AsyncProviderFactory.create` refuses a `provider` of `mock` or `test`, and any
> profile carrying `test_only`, with `test_provider_not_available`; a profile
> whose `default_state` is `enabled_for_tests_only` is refused with
> `test_only_profile_not_runnable`. The reason is governance rather than tidiness:
> readiness exists to prove that an **exact** model at an **exact** endpoint can
> really answer, and a provider that answers without a model would let every
> readiness gate pass over an endpoint that proves nothing. **A conforming
> implementation of this contract must not be a stub.** Test doubles belong in a
> test's own fixtures, never in the shipped provider registry, and the Phase 1
> mock sections below are kept only as the historical record described there.

---

## Provider Interface

Every provider adapter must expose these operations:

The "Phase 1 requirement" column is the **historical** build order and is not
the current bar. Today every shipped adapter implements the whole interface
against a real endpoint.

| Operation | Purpose | Phase 1 requirement (historical) |
|---|---|---|
| `load_profile(profile)` | Validate and bind a model profile. | Required. |
| `health_check()` | Report availability without sending user prompt. | Required; local providers later. |
| `generate(request)` | Produce non-streaming output. | Required. |
| `stream(request)` | Yield output chunks. | Optional in Phase 1; required for streaming providers later. |
| `cancel(request_id)` | Cancel in-flight request when supported. | Stub allowed in Phase 1. |
| `estimate_tokens(input)` | Estimate context size. | Stub allowed in Phase 1. |
| `parse_tool_calls(output)` | Parse provider/tool-call output into ToolAction proposals. | Must treat output as untrusted. |

A provider must never execute tools. It may only return text or structured tool-action proposals for runtime validation and policy review.

---

## ModelRequest Schema

```json
{
  "schema_version": "1.0",
  "model_request_id": "modelreq_01H...",
  "session_id": "sess_01H...",
  "turn_id": "turn_01H...",
  "role": "chat",
  "profile_id": "raiker-local-llama-cpp",
  "messages": [
    {"role": "user", "content": "Hello Raiker"}
  ],
  "context": {
    "context_bundle_id": "ctx_01H...",
    "sources": []
  },
  "options": {
    "temperature": 0.0,
    "max_output_tokens": 512,
    "tool_call_mode": "disabled"
  },
  "privacy": {
    "local_only": true,
    "allow_prompt_egress": false
  }
}
```

---

## ModelResponse Schema

```json
{
  "schema_version": "1.0",
  "model_request_id": "modelreq_01H...",
  "profile_id": "raiker-local-llama-cpp",
  "status": "completed",
  "text": "Hello. I am the configured local model.",
  "tool_call_proposals": [],
  "usage": {
    "input_tokens_estimated": 5,
    "output_tokens_estimated": 8
  },
  "finish_reason": "stop",
  "error": null
}
```

Allowed statuses: `completed`, `failed`, `cancelled`, `blocked_by_policy`, `unavailable`.

---

## Provider Policy Requirements

| Provider class | Default policy | Required controls |
|---|---|---|
| `mock` / `test` / `test_only` | **Refused** — `test_provider_not_available` | Not a provider class Raiker serves. See the banner at the top. |
| local HTTP provider | Disabled until Phase 2 profile enabled | Endpoint validation, local-only policy, health check. |
| OpenAI-compatible local endpoint | Disabled until Phase 2/3 | Endpoint must be localhost/local network unless policy allows egress. |
| hosted provider | Disabled by default | Egress approval, redaction, budget, audit event. |
| plugin provider | Disabled by default | Plugin trust, permission diff, broker/gateway isolation. |

No silent remote fallback is allowed.

---

## Reasoning

A provider declares reasoning as an **effort** (`supports_reasoning_effort` with
`reasoning_effort_values`) or as a **mode** (`reasoning_modes`), and the runtime
accepts either. A profile that declares neither offers no reasoning control at
all rather than one that does nothing.

**A provider adapter must keep reasoning apart from the answer.** Reasoning
streams as `ModelStreamEvent(event_type="reasoning_delta")` carrying its own
`reasoning_delta` field, and arrives on a non-streamed response as
`ModelResponse.reasoning`. It is never appended to `text` or `text_delta`: the
answer is what the owner asked for and the reasoning is how the model got there,
and a runtime that cannot tell them apart cannot honestly label either. The
contract rejects a `reasoning_delta` payload on any other event type.

**An adapter may negotiate the request's *shape*, and only its shape.** Where a
provider accepts more than one spelling of the same capability and which one a
*model* takes is not knowable from the profile, the adapter may use the declared
spelling, read the alternative out of the provider's own refusal, record it for
that model, and re-issue once. This is not the remote fallback forbidden above:
no capability is substituted, nothing is downgraded, and a refusal that names no
alternative stays a real error. `AsyncAnthropicMessagesProvider` does this for
`thinking.type.adaptive` versus `thinking.type.enabled`, which no single
`reasoning_modes` declaration can be right about across one provider's catalogue.

Where the profile declares `supports_reasoning_summary`, the runtime asks for the
provider's **summary** of its reasoning rather than its raw notes. What reaches a
surface is what the provider returned; integrity markers that accompany a
reasoning block (Anthropic's `signature_delta`) are not text and must not.

---

## Required Events

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
- `model_request_cancelled`
- `model_fallback_requested`
- `model_fallback_denied`
- `model_fallback_used`

---

## Phase 1 Mock Provider Acceptance *(historical — superseded)*

> **Superseded 2026-08-23.** Items 1–3 describe a `mock` provider that does not
> exist and is now refused fail-closed. What replaced them is the assertion that
> a test provider **cannot be constructed**: `AsyncProviderFactory.create` raises
> `test_provider_not_available`. Items 4–8 still stand and are still asserted.

Tests must prove:

1. ~~`mock` provider loads from registry profile~~ → a `mock`/`test`/`test_only`
   profile is **refused** with `test_provider_not_available`;
2. ~~`mock` provider produces deterministic output~~ → an
   `enabled_for_tests_only` profile is refused with
   `test_only_profile_not_runnable`;
3. ~~`mock` provider does not use network~~ → superseded by the endpoint policy in
   `raiker/models/endpoint_policy.py`, which every real adapter passes;
4. unknown provider fails clearly (`unknown_provider:<name>`);
5. hosted providers are not called in tests;
6. provider output cannot execute tools directly;
7. invalid structured tool proposals are rejected before policy;
8. model request/response events are emitted where model routing is exercised.
