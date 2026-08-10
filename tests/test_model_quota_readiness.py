"""Billing/quota exhaustion is its own readiness answer, not "unreachable".

A provider that answers the catalogue call and then refuses to run the model
because the account has no credit is reachable, correctly credentialled, and
completely unusable. Reporting that as ``unreachable`` sends the owner to debug
their network; reporting it as an authentication failure sends them to rotate a
key that is perfectly valid. Both are the wrong repair, so the state is exact.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.exceptions import (
    ProviderQuotaExhaustedError,
    ProviderRateLimitError,
)
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.readiness import (
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
)
from raiker.storage.sqlite import SQLiteStore

CREDIT_BALANCE_TOO_LOW = {
    "type": "error",
    "error": {
        "type": "invalid_request_error",
        "message": (
            "Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits."
        ),
    },
}

INSUFFICIENT_QUOTA = {
    "error": {
        "type": "insufficient_quota",
        "code": "insufficient_quota",
        "message": "You exceeded your current quota, please check your plan and billing details.",
    }
}


def _caps() -> ModelCapabilities:
    return ModelCapabilities(supports_streaming=True, supports_tool_calls=True)


def _anthropic(handler: Any) -> AsyncAnthropicMessagesProvider:
    return AsyncAnthropicMessagesProvider(
        "anthropic-hosted",
        "anthropic",
        "claude-haiku-4-5-20251001",
        "https://api.anthropic.com",
        _caps(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _openai(handler: Any) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(
        "openai-hosted",
        "openai",
        "gpt-4o-mini",
        "https://api.openai.com/v1",
        _caps(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _chat(model: str) -> ModelRequest:
    return ModelRequest(
        "profile",
        "provider",
        model,
        [ModelMessage("user", ".")],
        max_tokens=1,
        stream=False,
    )


def test_anthropic_credit_balance_400_is_quota_not_a_connection_error() -> None:
    """The live shape observed on 2026-08-09: HTTP 400, valid key, no credit."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=CREDIT_BALANCE_TOO_LOW)

    provider = _anthropic(handler)
    with pytest.raises(ProviderQuotaExhaustedError, match="provider_quota_exhausted"):
        asyncio.run(provider.chat(_chat("claude-haiku-4-5-20251001")))


def test_openai_insufficient_quota_429_is_quota_not_a_rate_limit() -> None:
    """A retry fixes a rate limit; only paying fixes an exhausted quota."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json=INSUFFICIENT_QUOTA)

    provider = _openai(handler)
    with pytest.raises(ProviderQuotaExhaustedError):
        asyncio.run(provider.chat(_chat("gpt-4o-mini")))


def test_plain_429_without_billing_detail_stays_a_rate_limit() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Too many requests"}})

    provider = _openai(handler)
    with pytest.raises(ProviderRateLimitError):
        asyncio.run(provider.chat(_chat("gpt-4o-mini")))


def test_payment_required_402_is_quota_for_every_openai_compatible_router() -> None:
    """OpenRouter and friends answer an empty account with a bare 402."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    provider = _openai(handler)
    with pytest.raises(ProviderQuotaExhaustedError):
        asyncio.run(provider.chat(_chat("gpt-4o-mini")))


def test_quota_exhaustion_never_echoes_the_provider_message() -> None:
    """The account message is provider prose; only the classified code travels."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=CREDIT_BALANCE_TOO_LOW)

    provider = _anthropic(handler)
    with pytest.raises(ProviderQuotaExhaustedError) as caught:
        asyncio.run(provider.chat(_chat("claude-haiku-4-5-20251001")))
    assert "credit balance" not in str(caught.value).casefold()
    assert "Plans & Billing" not in str(caught.value)


def test_readiness_state_for_quota_is_exact_and_persists(tmp_path: Path) -> None:
    class QuotaProbe:
        async def check(self, key: ModelReadinessKey) -> ModelReadiness:
            return ModelReadiness(
                key=key,
                state=ModelReadinessState.QUOTA_EXHAUSTED,
                checked_at=None,
                expires_at=None,
                summary="Anthropic has no available credit for this account.",
                reason_code="provider_quota_exhausted",
                remediation="Add credit or raise the quota, then check again.",
                evidence={"provider": "anthropic"},
            )

    store = SQLiteStore(tmp_path)
    service = ModelReadinessService(store, probe=QuotaProbe())

    observed = asyncio.run(
        service.check("owner-a", "anthropic-hosted", "claude-haiku-4-5-20251001", "fp")
    )

    assert observed.state is ModelReadinessState.QUOTA_EXHAUSTED
    assert observed.ready is False
    reloaded = service.current(
        "owner-a", "anthropic-hosted", "claude-haiku-4-5-20251001", "fp"
    )
    assert reloaded.state is ModelReadinessState.QUOTA_EXHAUSTED
    assert reloaded.reason_code == "provider_quota_exhausted"
