"""MD-5 — a provider's Retry-After is shown and honoured by the readiness ledger."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.models.exceptions import ProviderRateLimitError
from raiker.models.readiness import (
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
    ProbeStage,
    classify_provider_failure,
    rate_limited_until,
)
from raiker.storage.sqlite import SQLiteStore

NOW = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)


def _limited(seconds: float) -> ProviderRateLimitError:
    error = ProviderRateLimitError("provider_rate_limited")
    error.retry_after_seconds = seconds
    return error


class CountingProbe:
    def __init__(self) -> None:
        self.calls = 0

    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        self.calls += 1
        failure = classify_provider_failure(
            _limited(600), stage=ProbeStage.CATALOGUE, label="Anthropic", model="m", local_only=False
        )
        return ModelReadiness(
            key=key, state=failure.state, checked_at=None, expires_at=None,
            summary=failure.summary, reason_code=failure.reason_code,
            remediation=failure.remediation,
            evidence={"retry_after_seconds": failure.retry_after_seconds},
        )


def test_a_retry_after_is_classified_with_its_wait() -> None:
    failure = classify_provider_failure(
        _limited(90), stage=ProbeStage.CATALOGUE, label="Anthropic", model="m", local_only=False
    )
    assert failure.reason_code == "provider_rate_limited"
    assert failure.retry_after_seconds == 90
    assert "rate-limiting" in failure.summary
    # Without a Retry-After it is the ordinary rate-limit answer, with no wait.
    plain = classify_provider_failure(
        ProviderRateLimitError("x"), stage=ProbeStage.CATALOGUE, label="A", model="m", local_only=False
    )
    assert plain.retry_after_seconds is None


def test_the_ledger_records_the_time_and_does_not_ask_again_before_it(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    probe = CountingProbe()
    clock = [NOW]
    service = ModelReadinessService(store, probe=probe, clock=lambda: clock[0], ttl=timedelta(minutes=5))

    first = asyncio.run(service.check("owner", "anthropic-hosted", "m", "e"))
    assert first.state is ModelReadinessState.UNREACHABLE
    assert rate_limited_until(first) == NOW + timedelta(seconds=600)
    assert "retry_after_seconds" not in first.evidence

    clock[0] = NOW + timedelta(minutes=5)
    again = asyncio.run(service.check("owner", "anthropic-hosted", "m", "e"))
    assert probe.calls == 1, "the provider was asked again before its Retry-After"
    assert again.evidence == first.evidence

    clock[0] = NOW + timedelta(minutes=11)
    asyncio.run(service.check("owner", "anthropic-hosted", "m", "e"))
    assert probe.calls == 2
