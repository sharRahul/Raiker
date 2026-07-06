# Connect a Model

> Getting Started › Connect a Model. Back to [Getting Started](getting-started.md).

The choice of LLM belongs to you. Local models need no key:

```bash
raiker /model use --provider ollama --model gemma4:31b-cloud
```

Hosted providers (Anthropic / OpenAI / Gemini / OpenRouter) are fail-closed until
you enable the gate, set the owner egress allowlist
(`RAIKER_MODEL_EGRESS_ALLOWLIST`), and provide the key env var. See
[Platform & Integrations › Model Backends](platform-integrations-model-backends.md).

## Next

- [Your First Governed Action](getting-started-first-action.md)
