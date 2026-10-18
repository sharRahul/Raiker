"""A provider that will not run one model for this caller is not a rejected key.

Reported 2026-10-18: OpenRouter, with a valid key, answered the readiness check
for ``thinkingmachines/inkling:free`` with HTTP 403 *"… is only available on
agentic harnesses"*, and Raiker said the provider *rejected the saved credential
during execution*. The same key ran ``openai/gpt-4o-mini`` and ``openrouter/free``
at once. The repair is another model, never another key.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderModelNotFoundError,
    ProviderModelRefusedError,
    model_refused,
    provider_error_code,
    provider_error_sentence,
)
from raiker.models.factory import ModelProviderFactory
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.readiness import ProbeStage, classify_provider_failure
from raiker.models.registry import ModelProfileRegistry

#: The live body, 2026-10-18, request id removed.
GATED_BODY = {
    "error": {
        "message": (
            "thinkingmachines/inkling:free is only available on agentic harnesses. "
            "Try plugging it into a coding agent or productivity app listed on "
            "https://openrouter.ai/apps"
        ),
        "code": 403,
        "metadata": {
            "routing_funnel": [{"step": "Initial Endpoints", "endpoint_count": 1}],
            "failed_routing_step": "Gate Free Endpoints by Agentic Harness",
        },
    }
}


def _openrouter(handler: Any) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(
        "openrouter-policy-gated",
        "openrouter",
        "thinkingmachines/inkling:free",
        "https://openrouter.ai/api/v1",
        ModelCapabilities(supports_streaming=True, supports_tool_calls=True),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _chat() -> ModelRequest:
    return ModelRequest(
        "openrouter-policy-gated",
        "openrouter",
        "thinkingmachines/inkling:free",
        [ModelMessage("user", ".")],
        max_tokens=1,
        stream=False,
    )


def test_a_gated_model_403_is_a_model_refusal_not_an_auth_failure() -> None:
    provider = _openrouter(lambda _: httpx.Response(403, json=GATED_BODY))
    with pytest.raises(ProviderModelRefusedError) as caught:
        asyncio.run(provider.chat(_chat()))
    assert provider_error_code(caught.value) == "provider_model_refused:http_403"
    assert "only available" not in str(caught.value)  # provider prose never travels


def test_an_ordinary_403_is_still_an_authentication_failure() -> None:
    provider = _openrouter(lambda _: httpx.Response(403, json={"error": {"message": "Forbidden"}}))
    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(provider.chat(_chat()))
    assert model_refused(401, str(GATED_BODY)) is False


def test_readiness_says_choose_another_model_and_never_names_the_key() -> None:
    failure = classify_provider_failure(
        ProviderModelRefusedError("provider_model_refused:http_403"),
        stage=ProbeStage.EXECUTION,
        label="OpenRouter",
        model="thinkingmachines/inkling:free",
        local_only=False,
    )
    assert failure.reason_code == "provider_model_refused"
    assert "credential" not in failure.summary
    assert "another model" in failure.remediation
    # Still a kind of "cannot execute this model", so fallback and the model
    # picker treat it as they treat a missing model.
    assert issubclass(ProviderModelRefusedError, ProviderModelNotFoundError)


def test_the_turn_sentence_says_the_key_is_fine() -> None:
    sentence = provider_error_sentence("provider_model_refused:http_403")
    assert "key is fine" in sentence
    assert "rejected the saved credential" not in sentence


def test_openrouter_requests_carry_raikers_own_attribution() -> None:
    """Honest app attribution: Raiker names itself, never another product."""
    profile = ModelProfileRegistry.load().resolve_profile_id("openrouter-policy-gated")
    resolved = ModelProviderFactory(
        allow_hosted_provider=True,
        allow_policy_gated_provider=True,
        connection={"api_key": "sk-or-test"},
    ).resolve(profile, require_model=False)
    assert resolved.headers["X-Title"] == "Raiker"
    assert resolved.headers["HTTP-Referer"] == "https://github.com/sharRahul/Raiker"
    assert resolved.headers["Authorization"] == "Bearer sk-or-test"
