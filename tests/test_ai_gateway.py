from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from raiker.models.contracts import ModelResponse, ModelStreamEvent
from raiker.models.exceptions import ProviderAuthenticationError, ProviderConnectionError
from raiker.models.gateway import AIGateway, GatewayCircuitOpenError, GatewayTarget


def test_circuit_isolates_connections_and_allows_one_recovery_probe() -> None:
    async def body() -> None:
        clock = [0.0]
        gateway = AIGateway(failure_threshold=2, cooldown_seconds=10, clock=lambda: clock[0])
        target = GatewayTarget("owner", "profile", "model", "connection-a")
        calls = 0

        async def fail() -> ModelResponse:
            nonlocal calls
            calls += 1
            raise ProviderConnectionError("provider_connection_failed")

        for _ in range(2):
            with pytest.raises(ProviderConnectionError):
                await gateway.call(target, "chat", fail)
        with pytest.raises(GatewayCircuitOpenError):
            await gateway.call(target, "chat", fail)
        assert calls == 2
        for other in [GatewayTarget("other-owner", "profile", "model", "connection-a"),
                      GatewayTarget("owner", "profile", "model", "connection-b")]:
            assert (await gateway.call(other, "chat", lambda: success())).text == "ok"
        clock[0] = 10
        entered, release = asyncio.Event(), asyncio.Event()

        async def recover() -> ModelResponse:
            entered.set()
            await release.wait()
            return ModelResponse(text="recovered")

        probe = asyncio.create_task(gateway.call(target, "chat", recover))
        await entered.wait()
        with pytest.raises(GatewayCircuitOpenError):
            await gateway.call(target, "chat", fail)
        release.set()
        assert (await probe).text == "recovered"
        assert (await gateway.call(target, "chat", lambda: success())).text == "ok"
    asyncio.run(body())


async def success() -> ModelResponse:
    return ModelResponse(text="ok", usage={"prompt_tokens": 4, "completion_tokens": 2})


def test_permanent_failures_do_not_open_circuit_and_telemetry_has_no_payload() -> None:
    async def body() -> None:
        gateway = AIGateway(failure_threshold=1)
        target = GatewayTarget("owner", "profile", "model", "secret-connection")

        async def rejected() -> ModelResponse:
            raise ProviderAuthenticationError("Bearer secret-provider-body")

        with pytest.raises(ProviderAuthenticationError):
            await gateway.call(target, "chat", rejected)
        await gateway.call(target, "chat", success)
        records = gateway.recent()
        assert len(records) == 2
        assert records[0].error_code == "provider_auth_failed"
        assert records[1].usage == {"input_tokens": 4, "output_tokens": 2}
        assert records[1].duration_ms >= 0
        assert "secret" not in repr(records)
        assert records[0].request_id != records[1].request_id
    asyncio.run(body())


def test_stream_close_releases_probe_and_never_replays_partial_output() -> None:
    async def body() -> None:
        clock = [0.0]
        gateway = AIGateway(failure_threshold=1, cooldown_seconds=1, clock=lambda: clock[0])
        target = GatewayTarget("owner", "profile", "model", "connection")
        closed = []

        async def stream() -> AsyncIterator[ModelStreamEvent]:
            try:
                yield ModelStreamEvent("text_delta", text_delta="partial private answer")
                raise ProviderConnectionError("provider_connection_failed")
            finally:
                closed.append(True)

        events = []
        with pytest.raises(ProviderConnectionError):
            async for event in gateway.stream(target, stream):
                events.append(event.text_delta)
        assert events == ["partial private answer"]
        assert closed == [True]
        clock[0] = 1
        probe = gateway.stream(target, stream)
        assert (await anext(probe)).text_delta == "partial private answer"
        await probe.aclose()
        assert closed == [True, True]
        assert (await gateway.call(target, "chat", success)).text == "ok"
        assert gateway.recent()[-2].outcome == "cancelled"
    asyncio.run(body())


def test_cancelled_recovery_releases_probe() -> None:
    async def body() -> None:
        gateway = AIGateway(failure_threshold=1, cooldown_seconds=1, clock=lambda: 100.0)
        target = GatewayTarget("owner", "profile", "model", "connection")
        entered = asyncio.Event()

        async def wait() -> ModelResponse:
            entered.set()
            await asyncio.Event().wait()
            return ModelResponse(text="unreachable")

        task = asyncio.create_task(gateway.call(target, "chat", wait))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await gateway.call(target, "chat", success)).text == "ok"
        assert gateway.recent()[0].outcome == "cancelled"
    asyncio.run(body())


def test_error_details_are_not_diagnostic_labels() -> None:
    async def body() -> None:
        gateway = AIGateway()
        async def fail() -> ModelResponse:
            raise ProviderConnectionError("provider_connection_failed:private-secret")
        with pytest.raises(ProviderConnectionError):
            await gateway.call(GatewayTarget("o", "p", "m", "c"), "chat", fail)
        assert gateway.recent()[0].error_code == "provider_connection_failed"
        assert "private-secret" not in repr(gateway.recent())
    asyncio.run(body())


def test_bounded_state_does_not_evict_cooling_circuits() -> None:
    async def body() -> None:
        gateway = AIGateway(failure_threshold=1, max_targets=1, max_records=2)
        first = GatewayTarget("owner", "profile", "model", "a")
        second = GatewayTarget("owner", "profile", "model", "b")
        async def fail() -> ModelResponse:
            raise ProviderConnectionError("provider_connection_failed")
        with pytest.raises(ProviderConnectionError):
            await gateway.call(first, "chat", fail)
        with pytest.raises(GatewayCircuitOpenError):
            await gateway.call(second, "chat", success)
        with pytest.raises(GatewayCircuitOpenError):
            await gateway.call(first, "chat", success)
        assert len(gateway.recent()) == 2
        assert [r.outcome for r in gateway.recent()] == ["blocked", "blocked"]
    asyncio.run(body())


def test_late_success_cannot_close_a_newly_opened_circuit() -> None:
    async def body() -> None:
        gateway = AIGateway(failure_threshold=1)
        target = GatewayTarget("owner", "profile", "model", "connection")
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow() -> ModelResponse:
            entered.set()
            await release.wait()
            return ModelResponse(text="older request")
        task = asyncio.create_task(gateway.call(target, "chat", slow))
        await entered.wait()
        async def fail() -> ModelResponse:
            raise ProviderConnectionError("provider_connection_failed")
        with pytest.raises(ProviderConnectionError):
            await gateway.call(target, "chat", fail)
        release.set()
        assert (await task).text == "older request"
        with pytest.raises(GatewayCircuitOpenError):
            await gateway.call(target, "chat", success)
    asyncio.run(body())
