"""Hermes-parity provider breadth: eight OpenAI-compatible hosted APIs.

Each is an ordinary profile, so the connect dialog, the vault, the catalogue,
readiness, the hosted-model gate and the egress rule apply to it unchanged.
What has to be true of every one: it is off until the owner opens the gate,
it needs a key, the key travels as a bearer token to that provider's own host
and nowhere else, and its catalogue is read like any OpenAI-compatible one.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx
import pytest

from raiker.models.exceptions import ProviderConfigurationError, ProviderPolicyError
from raiker.models.factory import ModelProviderFactory
from raiker.models.registry import ModelProfileRegistry

#: profile id → the host its key may be sent to (verified live 2026-10-18).
PRESETS = {
    "deepseek-hosted": "api.deepseek.com",
    "groq-hosted": "api.groq.com",
    "mistral-hosted": "api.mistral.ai",
    "xai-hosted": "api.x.ai",
    "together-hosted": "api.together.xyz",
    "fireworks-hosted": "api.fireworks.ai",
    "nvidia-nim-hosted": "integrate.api.nvidia.com",
    "cerebras-hosted": "api.cerebras.ai",
}


def _profile(profile_id: str):  # type: ignore[no-untyped-def]
    return ModelProfileRegistry.load().resolve_profile_id(profile_id)


@pytest.mark.parametrize("profile_id", sorted(PRESETS))
def test_each_preset_is_off_and_keyed_until_the_owner_connects_it(profile_id: str) -> None:
    profile = _profile(profile_id)
    assert profile.raw["default_state"] == "disabled_until_policy_approved"
    assert profile.raw["requires_api_key"] is True
    assert profile.local_only is False
    with pytest.raises(ProviderPolicyError):
        ModelProviderFactory(connection={"api_key": "k"}).resolve(profile, require_model=False)
    # Gate open and host authorised, but no key: refused for the key.
    with pytest.raises(ProviderConfigurationError):
        ModelProviderFactory(
            allow_hosted_provider=True,
            allow_policy_gated_provider=True,
            connection={"endpoint": str(profile.raw["endpoint"])},
        ).resolve(profile, require_model=False)


@pytest.mark.parametrize(("profile_id", "host"), sorted(PRESETS.items()))
def test_the_key_goes_as_a_bearer_token_to_that_providers_host_only(
    profile_id: str, host: str
) -> None:
    resolved = ModelProviderFactory(
        allow_hosted_provider=True,
        allow_policy_gated_provider=True,
        connection={"api_key": "sk-test"},
    ).resolve(_profile(profile_id), require_model=False)
    assert resolved.headers["Authorization"] == "Bearer sk-test"
    assert urlparse(resolved.endpoint).scheme == "https"
    assert urlparse(resolved.endpoint).hostname == host
    assert resolved.endpoint_kind == "remote_hosted"


@pytest.mark.parametrize("profile_id", sorted(PRESETS))
def test_each_preset_lists_its_catalogue_like_any_openai_compatible_api(profile_id: str) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"object": "list", "data": [{"id": "model-a"}, {"id": "model-b"}]})

    factory = ModelProviderFactory(
        allow_hosted_provider=True,
        allow_policy_gated_provider=True,
        connection={"api_key": "sk-test"},
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    provider = factory.create(_profile(profile_id), require_model=False)
    models = asyncio.run(provider.list_models())
    assert [model.id for model in models] == ["model-a", "model-b"]
    assert seen[0].url.host == PRESETS[profile_id]
    assert seen[0].url.path.endswith("/models")
    assert seen[0].headers["Authorization"] == "Bearer sk-test"
