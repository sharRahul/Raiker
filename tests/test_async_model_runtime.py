from __future__ import annotations

import asyncio
import json
import tomllib
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from raiker.models.contracts import (
    EmbeddingRequest,
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ReasoningOptions,
    ToolSpec,
)
from raiker.models.endpoint_policy import (
    EndpointPolicy,
    classify_endpoint,
    validate_endpoint_policy,
)
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderPolicyError,
    ProviderResponseValidationError,
    ProviderUnsupportedCapabilityError,
)
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.registry import ModelProfileRegistry


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_dependency_baseline() -> None:
    assert httpx.__version__
    with open("pyproject.toml", "rb") as handle:
        data = tomllib.loads(handle.read().decode())
    deps = data["project"]["dependencies"]
    assert deps == ["httpx>=0.27"]
    assert not any("rich" in d or "textual" in d for d in deps)
    assert not any("openai" in d or "pydantic" in d or "requests" in d or "aiohttp" in d for d in deps)


def test_endpoint_classification_and_policy() -> None:
    assert classify_endpoint("http://127.0.0.1:8080") == "local_machine"
    assert classify_endpoint("http://localhost:8080") == "local_machine"
    assert classify_endpoint("http://[::1]:8080") == "local_machine"
    assert classify_endpoint("http://0.0.0.0:8080") == "local_machine"
    assert classify_endpoint("http://192.168.1.50:8000") == "private_network"
    assert classify_endpoint("http://10.1.2.3") == "private_network"
    assert classify_endpoint("http://172.16.0.1") == "private_network"
    assert classify_endpoint("https://example.com") == "remote_hosted"
    with pytest.raises(ProviderPolicyError):
        validate_endpoint_policy("http://192.168.1.50", EndpointPolicy(True, False))
    with pytest.raises(ProviderPolicyError):
        validate_endpoint_policy("https://example.com", EndpointPolicy(True, False))
    with pytest.raises(ProviderPolicyError):
        validate_endpoint_policy("https://openrouter.ai/api/v1", EndpointPolicy(False, True, True, False, provider="openrouter"))


def test_factory_test_provider_gate_and_openai_profiles() -> None:
    r = ModelProfileRegistry.load()
    test_profile = r.resolve_profile_id("deterministic-test")
    with pytest.raises(ProviderPolicyError):
        ModelProviderFactory().create(test_profile)
    assert ModelProviderFactory(allow_test_provider=True).create(test_profile).profile_id == "deterministic-test"
    provider = ModelProviderFactory().create(r.resolve_profile_id("raiker-local-llama-cpp"))
    assert isinstance(provider, AsyncOpenAICompatibleProvider)
    run(provider.aclose())
    for profile_id in [
        "ollama-local-openai-compatible",
        "lm-studio-local-openai-compatible",
        "vllm-homelab-openai-compatible",
        "generic-openai-compatible",
        "openrouter-policy-gated",
    ]:
        with pytest.raises(ProviderConfigurationError, match="model_name_not_configured"):
            ModelProviderFactory(
                policy=ProviderRuntimePolicy(
                    allow_policy_gated_provider=True,
                    allow_hosted_provider=True,
                    allow_private_network_provider=True,
                )
            ).create(r.resolve_profile_id(profile_id))


def _provider(handler: Callable[[httpx.Request], httpx.Response], caps: ModelCapabilities | None = None) -> AsyncOpenAICompatibleProvider:
    if caps is None:
        caps = ModelCapabilities(supports_tool_calls=True, supports_embeddings=True, supports_reasoning=True, supports_reasoning_effort=True, reasoning_effort_values=("low", "high"))
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncOpenAICompatibleProvider("p", "llama.cpp", "m", "http://127.0.0.1:1/v1", caps, client=client)


def test_async_chat_payload_tool_reasoning_and_errors() -> None:
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],"usage":{"total_tokens":3}})
    p = _provider(handler)
    resp = run(p.chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "secret prompt")], [ToolSpec("read_file", "read")], reasoning=ReasoningOptions(True, effort="low"))))
    assert resp.text == "ok"
    assert seen["tools"] and seen["reasoning_effort"] == "low"

    q = _provider(lambda request: httpx.Response(200, json={}), ModelCapabilities())
    with pytest.raises(ProviderResponseValidationError):
        run(q.chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "x")])))
    auth = _provider(lambda request: httpx.Response(401, json={"error":"no"}))
    with pytest.raises(ProviderAuthenticationError):
        run(auth.chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "x")])))


def test_streaming_embeddings_and_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data":[{"id":"m","owned_by":"local"}]})
        if str(request.url).endswith("embeddings"):
            return httpx.Response(200, json={"data":[{"embedding":[1,2.0]}],"usage":{"prompt_tokens":1}})
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"he"}}]}\n\ndata: {"choices":[{"delta":{"content":"llo"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
    p = _provider(handler)
    events = run(_collect(p.stream_chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "x")]))))
    assert [e.text_delta for e in events if e.text_delta] == ["he", "llo"]
    assert run(p.list_models())[0].id == "m"
    assert run(p.embed(EmbeddingRequest("p", "llama.cpp", "m", "text"))).vector == [1.0, 2.0]
    no_embed = _provider(handler, ModelCapabilities())
    with pytest.raises(ProviderUnsupportedCapabilityError):
        run(no_embed.embed(EmbeddingRequest("p", "llama.cpp", "m", "text")))


async def _collect(aiter: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in aiter]
