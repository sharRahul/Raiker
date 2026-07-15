# Model Configuration

## Supported Providers
Raiker uses an async OpenAI-compatible adapter.

### Local Runtimes
- **llama.cpp**: `raiker-local-llama-cpp` profile (port 8080, model `local-gguf`).
- **Ollama**: `ollama-local-openai-compatible` (auto-detects model).
- **LM Studio**: `lm-studio-local-openai-compatible` (auto-detects model).

### Hosted Runtimes (Fail-Closed)
Require `RAIKER_MODEL_EGRESS_ALLOWLIST` and API keys:
- OpenRouter, OpenAI, Gemini, Anthropic.

## Managing Profiles
Profiles are defined in `config/model-profiles.json`.

### CLI Commands
- `/providers`: List providers.
- `/models`: List profiles.
- `/model use <profile>`: Switch active model.
- `/model health`: Verify connectivity.
