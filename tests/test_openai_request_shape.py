"""OpenAI's current models accept Raiker's request (found with the owner's key).

GPT-5 refused `max_tokens` and `temperature: 0.2` with a 400, and a one-token
readiness probe with another, so every GPT-5 model read as "cannot execute".
"""

from __future__ import annotations

from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.router import PROBE_OUTPUT_TOKENS


def _payload(provider: str, model: str) -> dict[str, object]:
    runtime = AsyncOpenAICompatibleProvider(
        "p", provider, model, "https://api.example.test/v1", ModelCapabilities(supports_streaming=True)
    )
    request = ModelRequest("p", provider, model, [ModelMessage("user", "hi")], max_tokens=4096, stream=False)
    return runtime._payload(request, stream=False)


def test_openai_reasoning_models_get_completion_tokens_and_no_temperature() -> None:
    for model in ("gpt-5-nano", "gpt-5", "gpt-5.4-mini", "o3", "o4-mini"):
        payload = _payload("openai", model)
        assert payload["max_completion_tokens"] == 4096, model
        assert "max_tokens" not in payload and "temperature" not in payload, model


def test_older_openai_models_keep_their_temperature() -> None:
    payload = _payload("openai", "gpt-4.1-mini")
    assert payload["max_completion_tokens"] == 4096
    assert "temperature" in payload


def test_other_openai_compatible_servers_keep_max_tokens() -> None:
    for provider in ("openrouter", "ollama", "lm-studio", "llama.cpp"):
        payload = _payload(provider, "gpt-5-nano")
        assert payload["max_tokens"] == 4096 and "temperature" in payload, provider


def test_the_readiness_probe_leaves_a_reasoning_model_room_to_answer() -> None:
    assert PROBE_OUTPUT_TOKENS >= 16
