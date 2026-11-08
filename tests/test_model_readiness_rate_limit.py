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


def test_an_invalidated_check_on_a_configured_slot_is_rechecked_not_refused(tmp_path: Path) -> None:
    """KB-01 (keyboard round) — after a slot restart the composer promised a check the server never ran."""
    import asyncio as _asyncio

    from raiker.models.readiness import (
        ModelReadiness,
        ModelReadinessKey,
        ModelReadinessService,
        ModelReadinessState,
    )

    store = SQLiteStore(tmp_path)
    store.save_configured_model("owner", "raiker-local-llama-cpp", "local-gguf")
    calls = {"n": 0}

    class Probe:
        def resolve_key(self, owner: str, profile: str, model: str) -> ModelReadinessKey:
            return ModelReadinessKey(owner, profile, model, "loopback")

        async def check(self, key: ModelReadinessKey) -> ModelReadiness:
            calls["n"] += 1
            return ModelReadiness(key=key, state=ModelReadinessState.READY, checked_at=None, expires_at=None,
                                  summary="ok", reason_code="model_ready", remediation="", evidence={})

    service = ModelReadinessService(store, probe=Probe())
    _asyncio.run(service.check("owner", "raiker-local-llama-cpp", "local-gguf", "loopback"))
    store.invalidate_model_readiness("owner", "raiker-local-llama-cpp", reason_code="local_runtime_deployed")
    ready = _asyncio.run(service.require_ready_async("owner", "raiker-local-llama-cpp", "local-gguf"))
    assert ready.ready
    assert calls["n"] == 2, "the invalidated observation was looked at again, not refused"



def test_a_key_or_endpoint_change_and_a_hosted_profile_still_ask_the_owner(tmp_path: Path) -> None:
    """The re-check is limited to Raiker reloading its own managed slot."""
    import asyncio as _asyncio

    import pytest as _pytest

    from raiker.models.readiness import (
        ModelNotReady,
        ModelReadiness,
        ModelReadinessKey,
        ModelReadinessService,
        ModelReadinessState,
    )

    store = SQLiteStore(tmp_path)
    store.save_configured_model("owner", "raiker-local-llama-cpp", "local-gguf")
    store.save_configured_model("owner", "anthropic-hosted", "claude")
    calls = {"n": 0}

    class Probe:
        def resolve_key(self, owner: str, profile: str, model: str) -> ModelReadinessKey:
            return ModelReadinessKey(owner, profile, model, "e")

        async def check(self, key: ModelReadinessKey) -> ModelReadiness:
            calls["n"] += 1
            return ModelReadiness(key=key, state=ModelReadinessState.READY, checked_at=None, expires_at=None,
                                  summary="ok", reason_code="model_ready", remediation="", evidence={})

    service = ModelReadinessService(store, probe=Probe())
    for profile, model in (("raiker-local-llama-cpp", "local-gguf"), ("anthropic-hosted", "claude")):
        _asyncio.run(service.check("owner", profile, model, "e"))
    store.invalidate_model_readiness("owner", "raiker-local-llama-cpp", reason_code="readiness_invalidated")
    store.invalidate_model_readiness("owner", "anthropic-hosted", reason_code="local_runtime_deployed")
    before = calls["n"]
    with _pytest.raises(ModelNotReady):
        _asyncio.run(service.require_ready_async("owner", "raiker-local-llama-cpp", "local-gguf"))
    with _pytest.raises(ModelNotReady):
        _asyncio.run(service.require_ready_async("owner", "anthropic-hosted", "claude"))
    assert calls["n"] == before, "nothing was reached on Raiker's own initiative"
