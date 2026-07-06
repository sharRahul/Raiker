# Model Backends

> Platform & Integrations › Model Backends. Back to [Platform & Integrations](platform-integrations.md).

Raiker is backend-agnostic:

- **Local** — llama.cpp, Ollama, LM Studio. No key; nothing leaves the machine.
- **Home-lab** — vLLM and private-network endpoints via
  `private_network_model_runtime`.
- **Hosted** — Anthropic, OpenAI, Gemini, OpenRouter via `hosted_model_runtime`.

## Turning on a hosted provider (governed)

1. `/runtime-mode activate local_single_user_runtime`.
2. Record the threat-model ack for `hosted_model_runtime` and enable the gate
   with a confirmation token.
3. Set `RAIKER_MODEL_EGRESS_ALLOWLIST` (empty = fail closed) and the provider key
   env var.
4. `/model use anthropic-hosted` (or another profile).

Every off-machine provider construction re-checks the same egress allowlist, so a
model-proposed endpoint can never bypass it. Keys and allowlist values are never
displayed.
