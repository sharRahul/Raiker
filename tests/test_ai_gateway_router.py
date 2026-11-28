"""Exercise the real factory/router/adapters with only HTTP replaced."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from raiker.models import credential_pool
from raiker.models.contracts import ModelMessage, ToolSpec
from raiker.models.exceptions import ProviderConnectionError, ProviderPolicyError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.gateway import AIGateway, GatewayCircuitOpenError
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.models.router import ModelRouter


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("refusal", ["tools", "keys"])
@pytest.mark.parametrize("revoke", ["gate", "connection", "none"])
def test_retries_reauthorize_current_owner_connection(
    monkeypatch: pytest.MonkeyPatch, streaming: bool, refusal: str, revoke: str,
) -> None:
    credential_pool.forget()
    monkeypatch.setattr("raiker.models.router._TOOLLESS_MODELS", set())
    registry = ModelProfileRegistry.load()
    profile = profile_with_model(registry.resolve_profile_id("openai-hosted"), "gateway-test")
    registry.register(profile)
    saved = {"api_key": "private-first", "api_key_2": "private-backup"} if refusal == "keys" else {"api_key": "private-first"}
    connection: list[dict[str, str] | None] = [saved]
    allowed = [True]
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.headers.get("authorization"), json.loads(request.content)))
        if len(seen) == 1:
            if revoke == "gate":
                allowed[0] = False
            elif revoke == "connection":
                connection[0] = None
            return httpx.Response(429 if refusal == "keys" else 400, json={"error": {"message": "Rate limit exceeded" if refusal == "keys" else "This model does not support tools"}})
        if streaming:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 2}})

    async def body() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            gateway = AIGateway()
            router = ModelRouter(registry, gateway=gateway, gateway_scope="owner",
                connection_resolver=lambda _: connection[0],
                runtime_policy_resolver=lambda: ProviderRuntimePolicy(
                    allow_policy_gated_provider=allowed[0], allow_hosted_provider=allowed[0]))
            messages = [ModelMessage("user", "private prompt")]
            tools = [ToolSpec("read_file", "read", {"type": "object"})]

            async def call() -> None:
                if streaming:
                    assert "".join([e.text_delta async for e in router.astream("openai", "gateway-test", messages, tools)]) == "ok"
                else:
                    assert (await router.achat("openai", "gateway-test", messages, tools)).text == "ok"
            if revoke == "none":
                await call()
                assert len(seen) == 2
                assert len({r.request_id for r in gateway.recent()}) == 1
                assert [r.attempt for r in gateway.recent()] == [1, 2]
            else:
                with pytest.raises(ProviderPolicyError):
                    await call()
                assert len(seen) == 1
            assert "private" not in repr(gateway.recent())
    try:
        asyncio.run(body())
    finally:
        credential_pool.forget()


def test_router_circuit_blocks_network_but_permission_revocation_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def body() -> None:
        registry = ModelProfileRegistry.load()
        profile = profile_with_model(registry.resolve_profile_id("openai-hosted"), "gateway-test")
        registry.register(profile)
        saved = {"api_key": "private-key"}
        allowed = [True]
        requests = []
        def fail(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            raise httpx.ConnectError("offline", request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            router = ModelRouter(registry, gateway=AIGateway(failure_threshold=1), gateway_scope="owner",
                connection_resolver=lambda _: saved,
                runtime_policy_resolver=lambda: ProviderRuntimePolicy(
                    allow_policy_gated_provider=allowed[0], allow_hosted_provider=allowed[0]))
            args = ("openai", "gateway-test", [ModelMessage("user", "hi")])
            with pytest.raises(ProviderConnectionError):
                await router.achat(*args)
            with pytest.raises(GatewayCircuitOpenError):
                await router.achat(*args)
            allowed[0] = False
            with pytest.raises(ProviderPolicyError):
                await router.achat(*args)
            assert len(requests) == 1
    asyncio.run(body())


def test_embeddings_and_explicit_probes_share_instrumentation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def body() -> None:
        from raiker.models.gateway_context import model_request_context
        registry = ModelProfileRegistry.load()
        profile = profile_with_model(registry.resolve_profile_id("openai-hosted"), "gateway-test")
        registry.register(profile)
        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("embeddings"):
                return httpx.Response(200, json={"data": [{"embedding": [0.25, 0.75]}], "model": "gateway-test", "usage": {"prompt_tokens": 3}})
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 2}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            gateway = AIGateway()
            router = ModelRouter(registry, gateway=gateway, gateway_scope="owner",
                connection_resolver=lambda _: {"api_key": "private-key"},
                runtime_policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True))
            assert (await router.aembed("openai", "gateway-test", "private document")).vector == [0.25, 0.75]
            await router.aprobe_model(profile)
            with model_request_context(kind="compaction", session_id="session-a", turn_id="turn-a"):
                await router.achat("openai", "gateway-test", [ModelMessage("user", "private prompt")])
            records = gateway.recent()
            assert [r.kind for r in records] == ["embedding", "probe", "compaction"]
            assert records[0].usage == {"input_tokens": 3}
            assert records[2].session_id == "session-a"
            assert records[2].turn_id == "turn-a"
            assert "private" not in repr(records)
    asyncio.run(body())


def test_gateway_telemetry_does_not_duplicate_runtime_billing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    from raiker.gateway.agent_gateway import AgentGateway
    from tests.test_turn_model_fallback import _envelope

    async def body() -> None:
        agent = AgentGateway(tmp_path)
        registry = agent.model_registry
        profile = profile_with_model(registry.resolve_profile_id("openai-hosted"), "gateway-test")
        registry.register(profile)
        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 2}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            gateway = AIGateway()
            router = ModelRouter(registry, gateway=gateway, gateway_scope="owner",
                connection_resolver=lambda _: {"api_key": "private-key"},
                runtime_policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True))
            agent.runtime.model_router = router
            agent.runtime.default_provider = ("openai", "gateway-test")
            response = await agent.runtime._acall_model(_envelope(), [ModelMessage("user", "hi")])
            assert response.text == "ok"
            assert len(gateway.recent()) == 1
            with agent.store.connect() as connection:
                rows = connection.execute("SELECT input_tokens, output_tokens FROM model_usage_ledger").fetchall()
            assert [(row[0], row[1]) for row in rows] == [(4, 2)]
    asyncio.run(body())


@pytest.mark.parametrize("streaming", [False, True])
def test_toolless_retry_resolves_current_environment_credentials(monkeypatch: pytest.MonkeyPatch, streaming: bool) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "private-old-key")
    monkeypatch.setattr("raiker.models.router._TOOLLESS_MODELS", set())
    async def body() -> None:
        registry = ModelProfileRegistry.load()
        profile = profile_with_model(registry.resolve_profile_id("openai-hosted"), "gateway-environment-test")
        registry.register(profile)
        seen = []
        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("authorization"))
            if len(seen) == 1:
                monkeypatch.setenv("OPENAI_API_KEY", "private-new-key")
                return httpx.Response(400, json={"error": {"message": "This model does not support tools"}})
            if streaming:
                return httpx.Response(200, headers={"content-type": "text/event-stream"}, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            router = ModelRouter(registry, gateway=AIGateway(), gateway_scope="owner",
                connection_resolver=lambda _: {"credential_source": "environment"},
                runtime_policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True))
            args = ("openai", "gateway-environment-test", [ModelMessage("user", "hi")], [ToolSpec("read_file", "read")])
            if streaming:
                assert "".join([e.text_delta async for e in router.astream(*args)]) == "ok"
            else:
                assert (await router.achat(*args)).text == "ok"
        assert seen == ["Bearer private-old-key", "Bearer private-new-key"]
    asyncio.run(body())


def test_closing_runtime_after_a_delta_closes_provider_immediately(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    from raiker.contracts.streaming import TEXT_DELTA
    from raiker.gateway.agent_gateway import AgentGateway
    from tests.test_turn_model_fallback import _envelope

    async def body() -> None:
        closed = []
        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):  # type: ignore[no-untyped-def]
                yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                await asyncio.Event().wait()
            async def aclose(self) -> None:
                closed.append(True)
        agent = AgentGateway(tmp_path)
        profile = profile_with_model(agent.model_registry.resolve_profile_id("openai-hosted"), "gateway-close-test")
        agent.model_registry.register(profile)
        def handle(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            monkeypatch.setattr(ModelProviderFactory, "_client_for", lambda *args: client)
            gateway = AIGateway()
            router = ModelRouter(agent.model_registry, gateway=gateway, gateway_scope="owner",
                connection_resolver=lambda _: {"api_key": "private-key"},
                runtime_policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True))
            agent.runtime.model_router = router
            agent.runtime.default_provider = ("openai", "gateway-close-test")
            stream = agent.runtime._astream_model_call(_envelope(), [ModelMessage("user", "hi")])
            while True:
                event = await anext(stream)
                if getattr(event, "kind", None) == TEXT_DELTA:
                    break
            await stream.aclose()
            assert closed == [True]
            assert gateway.recent()[-1].outcome == "cancelled"
    asyncio.run(body())
