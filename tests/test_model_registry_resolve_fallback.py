"""`ModelProfileRegistry.resolve` placeholder-model fallback.

Hosted / OpenAI-compatible providers (openrouter, openai, gemini, ollama, vllm,
lm-studio, openai-compatible) ship a placeholder `<model>` and pick the concrete
model at selection time. `resolve(provider, concrete_model)` must return the
provider's profile with that concrete model filled in — so the direct
`ModelRouter.achat`/`aembed` path is consistent with the CLI `/model use` +
gateway path (which already substitute the model). Exact matches still win, and
unknown providers still fail closed. Provider *policy* is enforced later by the
factory, not here.
"""

from __future__ import annotations

import pytest

from raiker.models.registry import ModelProfileRegistry, RegistryError


@pytest.fixture
def registry() -> ModelProfileRegistry:
    return ModelProfileRegistry.load()


@pytest.mark.parametrize(
    ("provider", "model", "expected_profile_id"),
    [
        ("openrouter", "openai/gpt-4o-mini", "openrouter-policy-gated"),
        ("openai", "gpt-4o-mini", "openai-hosted"),
        ("gemini", "gemini-2.0-flash", "gemini-hosted-openai-compatible"),
    ],
)
def test_placeholder_provider_resolves_concrete_model(
    registry: ModelProfileRegistry, provider: str, model: str, expected_profile_id: str
) -> None:
    resolved = registry.resolve(provider, model)
    assert resolved.provider.replace("_", "-") == provider
    assert resolved.model == model
    assert resolved.profile_id == expected_profile_id


def test_exact_match_still_wins(registry: ModelProfileRegistry) -> None:
    # Anthropic ships a concrete model; exact resolution is unchanged.
    resolved = registry.resolve("anthropic", "claude-opus-4-8")
    assert resolved.profile_id == "anthropic-hosted"
    assert resolved.model == "claude-opus-4-8"


def test_unknown_provider_still_fails_closed(registry: ModelProfileRegistry) -> None:
    with pytest.raises(RegistryError, match="unknown_model_profile"):
        registry.resolve("no_such_provider", "whatever")


def test_underscore_provider_alias_resolves(registry: ModelProfileRegistry) -> None:
    # `llama_cpp` normalizes to `llama.cpp` (its concrete profile model).
    resolved = registry.resolve("llama_cpp", "local-gguf")
    assert resolved.provider == "llama.cpp"
    assert resolved.model == "local-gguf"
