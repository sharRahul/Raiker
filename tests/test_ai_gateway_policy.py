from __future__ import annotations

import pytest

from raiker.models.attempts import ModelAttempts


@pytest.mark.parametrize(("error", "committed", "expected"), [
    ("provider_connection_failed", False, [(0, "primary", "a", False), (0, "primary", "a", True), (1, "local", "b", False)]),
    ("provider_timeout", False, [(0, "primary", "a", False), (0, "primary", "a", True), (1, "local", "b", False)]),
    ("provider_auth_failed", False, [(0, "primary", "a", False), (1, "local", "b", False)]),
    ("provider_circuit_open", False, [(0, "primary", "a", False), (1, "local", "b", False)]),
    ("provider_connection_failed", True, [(0, "primary", "a", False)]),
])
def test_shared_attempt_policy_bounds_retries_and_prevents_replay(
    error: str, committed: bool, expected: list[tuple[int, str, str, bool]],
) -> None:
    attempts = ModelAttempts([("primary", "a"), ("local", "b")])
    seen = []
    for attempt in attempts:
        seen.append(attempt)
        if attempt[1] == "primary":
            attempts.failed(error, output_committed=committed)
    assert seen == expected


def test_visible_reasoning_prevents_stream_fallback(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from raiker.gateway.agent_gateway import AgentGateway
    from raiker.models.contracts import ModelResponse, ModelStreamEvent
    from raiker.models.exceptions import ProviderConnectionError

    gateway = AgentGateway(tmp_path)
    gateway.runtime.default_provider = ("primary", "a")
    gateway.runtime.fallback_resolver = lambda: [("local", "b")]
    calls = []
    async def stream(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
        calls.append(provider)
        yield ModelStreamEvent("reasoning_delta", reasoning_delta="visible reasoning")
        raise ProviderConnectionError("provider_connection_failed")
    gateway.runtime.model_router.astream = stream  # type: ignore[method-assign, assignment]
    from tests.test_turn_model_fallback import _envelope
    async def run() -> None:
        output = [item async for item in gateway.runtime._astream_model_call(_envelope(), [])]
        responses = [item for item in output if isinstance(item, ModelResponse)]
        assert len(responses) == 1
        assert responses[0].finish_reason == "error"
    asyncio.run(run())
    assert calls == ["primary"]


def test_gateway_transport_outages_do_not_pause_unrelated_provider_credentials(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from raiker.gateway.agent_gateway import AgentGateway
    from raiker.security.containment import (
        CAPABILITY_PROVIDER,
        CapabilityBreaker,
        CapabilityContainment,
    )
    from tests.test_turn_model_fallback import _envelope

    gateway = AgentGateway(tmp_path)
    envelope = _envelope()
    owner = gateway.runtime._source_owner(envelope)
    breaker = CapabilityBreaker(gateway.store)
    for reason in ["provider_connection_failed", "provider_timeout", "provider_circuit_open"]:
        gateway.runtime._record_provider_outcome(breaker, envelope, "openai", ok=False, reason_code=reason)
    assert CapabilityContainment(gateway.store).state(owner, CAPABILITY_PROVIDER, "openai").state == "active"
    for _ in range(3):
        gateway.runtime._record_provider_outcome(breaker, envelope, "openai", ok=False, reason_code="provider_auth_failed")
    assert CapabilityContainment(gateway.store).state(owner, CAPABILITY_PROVIDER, "openai").state == "paused"
