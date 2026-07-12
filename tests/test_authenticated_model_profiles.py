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

    remote_lm = registry.resolve_profile_id("lm-studio-remote-authenticated")
    assert remote_lm.provider == "lm-studio-remote"
    assert remote_lm.raw["endpoint_env"] == "LM_STUDIO_BASE_URL"
    assert remote_lm.raw["api_key_env"] == "LM_API_TOKEN"
    assert remote_lm.raw["requires_api_key"] is True

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


def test_remote_lm_studio_requires_endpoint_key_gate_and_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ModelProfileRegistry.load()
    profile = profile_with_model(
        registry.resolve_profile_id("lm-studio-remote-authenticated"),
        "ibm/granite-4-micro",
    )
    policy = ProviderRuntimePolicy(
        allow_policy_gated_provider=True,
        allow_private_network_provider=True,
    )

    with pytest.raises(ProviderConfigurationError, match="missing_endpoint_env:LM_STUDIO_BASE_URL"):
        ModelProviderFactory(policy=policy).create(profile)

    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://models.home.arpa:1234/v1")
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "models.home.arpa")
    with pytest.raises(ProviderConfigurationError, match="provider_api_key_missing:LM_API_TOKEN"):
        ModelProviderFactory(policy=policy).create(profile)

    monkeypatch.setenv("LM_API_TOKEN", "lm-remote-secret")
    provider = ModelProviderFactory(policy=policy).create(profile)
    assert isinstance(provider, AsyncOpenAICompatibleProvider)
    assert provider.endpoint == "http://models.home.arpa:1234/v1"
    assert provider._headers["Authorization"] == "Bearer lm-remote-secret"
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

def test_env_endpoint_profile_reports_governed_endpoint_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unset: the control surfaces must show the declared off-machine intent
    # (private network gate), never "unknown".
    monkeypatch.delenv("LM_STUDIO_BASE_URL", raising=False)
    remote = ModelProfileRegistry.load().resolve_profile_id("lm-studio-remote-authenticated")
    assert remote.raw["endpoint_kind"] == "private_network"

    # Configured: the classification follows the owner's actual URL.
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "https://lm.example.com:8443/v1")
    remote = ModelProfileRegistry.load().resolve_profile_id("lm-studio-remote-authenticated")
    assert remote.raw["endpoint_kind"] == "remote_hosted"

    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://192.168.1.20:1234/v1")
    remote = ModelProfileRegistry.load().resolve_profile_id("lm-studio-remote-authenticated")
    assert remote.raw["endpoint_kind"] == "private_network"
