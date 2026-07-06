# Threat Model - Model Provider Runtime (Tier 3, egress-gated)

`model_provider_runtime` is the provider-backed counterpart to the local
`vector_embedding_runtime`. Where the local runtime computes a deterministic
hashing embedding entirely offline, this runtime calls a real LLM provider's
**embedding** endpoint and persists the returned *semantic* vector to the shared
`vector_records` table. Because it reaches an off-machine provider with
credentials, it is gated in layers and fails closed by default.

## What it does (honest scope)

- Only `operation: embed` is supported in this slice. It sends the input text to
  the selected provider/model's embedding endpoint (via `ModelRouter.aembed`) and
  stores the returned vector locally. No chat/generation, no streaming, no tool
  use here.
- The embedding is a genuine provider (semantic) vector — distinct from the local
  lexical hashing embedding. The stored `embedding_model` is recorded as
  `<provider>:<model>` so provider-backed and local records are distinguishable.

## Boundaries enforced (fail-closed, layered)

- **Gate defaults disabled.** Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and a
  confirmation token. AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- **Owner egress allowlist.** `RAIKER_MODEL_EGRESS_ALLOWLIST` must be non-empty or
  the executor fails closed (`model_egress_denied:no_allowlist`) before any call.
  The provider factory independently re-enforces the same allowlist per provider
  construction (`enforce_model_egress`).
- **Hosted/private gate state.** The provider policy is derived from the persisted
  gates (`provider_runtime_policy_from_gates`): an off-machine provider is only
  constructed when the owner has also enabled `hosted_model_runtime` /
  `private_network_model_runtime`. Otherwise the factory refuses
  (`provider_requires_explicit_policy_approval` / `hosted_provider_requires_explicit_policy`).
- **Credentials from owner env only.** API keys are read from the provider's
  configured env var by the factory (`hosted_api_key_missing` when absent). They
  are never taken from action arguments and never appear in events or artifacts.
- **Unsupported providers fail closed.** Providers without an embedding endpoint
  return `model_provider_denied:embeddings_unsupported`.
- **Metadata-only artifacts.** Runtime artifacts contain ids/model/dims/hash only
  (`vector_id`, `embedding_model`, `dimensions`, `content_hash`,
  `provider_backed=true`, `content_redacted=true`). The source text (a 120-char
  preview is stored in the local table only) and credentials never enter events.

## Fail-closed reason codes

`unknown_operation:<op>`, `missing_argument:text|provider|model`, `text_too_long`,
`invalid_argument:scope_or_sensitivity`, `model_egress_denied:no_allowlist`,
`model_profile_not_found`, `model_provider_denied:<safe-code>` (e.g.
`hosted_api_key_missing`, `embeddings_unsupported`),
`model_provider_error:<ExceptionType>`, `invalid_embedding_response`, and the
sandbox transport codes surfaced by egress enforcement.

## Explicit non-goals

- No generation/chat/streaming here (that stays in the gateway/provider layer).
- No credential handling in the executor beyond delegating to the factory.
- No provider selection policy of its own — it honors the persisted gates and the
  owner egress allowlist.

## Acceptance evidence

- `tests/test_phase_7_model_provider_runtime.py` proves registry membership,
  disabled-gate blocking, threat-model-ack activation, empty-allowlist
  fail-closed (before any provider call), missing-text / unknown-operation
  fail-closed, provider-error fail-closed, and the governed success path that
  persists a provider vector without leaking the source text. The provider call
  is exercised through an injected embedder, so no test performs real network I/O.
