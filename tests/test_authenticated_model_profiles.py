from __future__ import annotations

import asyncio

import pytest

from raiker.models.exceptions import ProviderConfigurationError, ProviderPolicyError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.registry import ModelProfileRegistry, profile_with_model


def run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def test_authenticated_provider_profiles_are_registered() -> None:
    registry = ModelProfileRegistry.load()

    ollama = registry.resolve_profile_id("ollama-cloud-openai-compatible")
    assert ollama.provider == "ollama-cloud"
    assert ollama.raw["endpoint"] == "https://ollama.com/v1"
    assert ollama.raw["api_key_env"] == "OLLAMA_API_KEY"
    assert ollama.raw["requires_api_key"] is True

    local_lm = registry.resolve_profile_id("lm-studio-local-openai-compatible")
    assert local_lm.raw["api_key_env"] == "LM_API_TOKEN"

    huggingface = registry.resolve_profile_id("huggingface-inference-providers")
    assert huggingface.provider == "huggingface"
    assert huggingface.raw["endpoint"] == "https://router.huggingface.co/v1"
    assert huggingface.raw["api_key_env"] == "HF_TOKEN"
    assert huggingface.raw["supports_embeddings"] is False


def test_local_lm_studio_sends_optional_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LM_API_TOKEN", "lm-secret")
    registry = ModelProfileRegistry.load()
    profile = profile_with_model(
        registry.resolve_profile_id("lm-studio-local-openai-compatible"),
        "ibm/granite-4-micro",
    )

    provider = ModelProviderFactory().create(profile)
    assert isinstance(provider, AsyncOpenAICompatibleProvider)
    assert provider.endpoint == "http://127.0.0.1:1234/v1"
    assert provider._headers["Authorization"] == "Bearer lm-secret"
    run(provider.aclose())



def test_ollama_cloud_requires_hosted_gate_allowlist_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ModelProfileRegistry.load()
    profile = profile_with_model(
        registry.resolve_profile_id("ollama-cloud-openai-compatible"),
        "gemma4:31b",
    )

    with pytest.raises(ProviderPolicyError, match="provider_requires_explicit_policy_approval"):
        ModelProviderFactory().create(profile)

    policy = ProviderRuntimePolicy(
        allow_policy_gated_provider=True,
        allow_hosted_provider=True,
    )
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "ollama.com")
    with pytest.raises(ProviderConfigurationError, match="provider_api_key_missing:OLLAMA_API_KEY"):
        ModelProviderFactory(policy=policy).create(profile)

    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-secret")
    provider = ModelProviderFactory(policy=policy).create(profile)
    assert isinstance(provider, AsyncOpenAICompatibleProvider)
    assert provider.endpoint == "https://ollama.com/v1"
    assert provider._headers["Authorization"] == "Bearer ollama-secret"
    run(provider.aclose())


def test_huggingface_uses_router_and_hf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ModelProfileRegistry.load()
    profile = profile_with_model(
        registry.resolve_profile_id("huggingface-inference-providers"),
        "openai/gpt-oss-120b:cheapest",
    )
    policy = ProviderRuntimePolicy(
        allow_policy_gated_provider=True,
        allow_hosted_provider=True,
    )
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "router.huggingface.co")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")

    provider = ModelProviderFactory(policy=policy).create(profile)
    assert isinstance(provider, AsyncOpenAICompatibleProvider)
    assert provider.endpoint == "https://router.huggingface.co/v1"
    assert provider.model == "openai/gpt-oss-120b:cheapest"
    assert provider._headers["Authorization"] == "Bearer hf-secret"
    run(provider.aclose())
