from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from raiker.contracts.models import ModelProfile
from raiker.models.contracts import (
    EmbeddingRequest,
    ModelCapabilities,
    ModelContractError,
    ModelImage,
    ModelMessage,
    ModelRequest,
    ReasoningOptions,
    ToolCallProposal,
    ToolSpec,
)
from raiker.models.endpoint_policy import classify_endpoint, enforce_model_egress
from raiker.models.exceptions import (
    ProviderConnectionError,
    ProviderUnsupportedCapabilityError,
)
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def collect(iterator: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in iterator]


def openai_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    provider: str = "openai",
    capabilities: ModelCapabilities | None = None,
    headers: dict[str, str] | None = None,
) -> AsyncOpenAICompatibleProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncOpenAICompatibleProvider(
        profile_id="profile",
        provider=provider,
        model="chat-model",
        endpoint="https://example.test/v1",
        capabilities=capabilities
        or ModelCapabilities(
            supports_streaming=True,
            supports_embeddings=True,
            supports_tool_calls=True,
            supports_json_schema=True,
        ),
        extra_headers=headers or {},
        client=client,
    )


def anthropic_provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AsyncAnthropicMessagesProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncAnthropicMessagesProvider(
        profile_id="anthropic-profile",
        provider="anthropic",
        model="claude-test",
        endpoint="https://api.anthropic.test",
        capabilities=ModelCapabilities(
            supports_streaming=True,
            supports_tool_calls=True,
        ),
        extra_headers={"x-api-key": "test-key"},
        client=client,
    )


def request(*, cache_ttl: str | None = None) -> ModelRequest:
    return ModelRequest(
        profile_id="profile",
        provider="openai",
        model="chat-model",
        messages=[
            ModelMessage(role="system", content="stable system prompt"),
            ModelMessage(role="user", content="hello"),
        ],
        tools=[ToolSpec("read_file", "Read one file")],
        cache_ttl=cache_ttl,
    )


def test_egress_allowlist_matches_hostname_not_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "models.example.com")
    enforce_model_egress("https://models.example.com:8443/v1", kind="remote_hosted")


def test_private_dns_names_are_classified_as_private_network() -> None:
    assert classify_endpoint("http://model-server:8000/v1") == "private_network"
    assert classify_endpoint("http://models.home.arpa:8000/v1") == "private_network"
    assert classify_endpoint("http://models.corp.internal:8000/v1") == "private_network"


def test_model_message_contract_rejects_invalid_role_combinations() -> None:
    image = ModelImage(media_type="image/png", base64_data="eA==")
    with pytest.raises(ModelContractError, match="images_require_user_role"):
        ModelMessage(role="assistant", content="", images=(image,))
    with pytest.raises(ModelContractError, match="tool_message_requires_call_id"):
        ModelMessage(role="tool", content="{}")
    with pytest.raises(ModelContractError, match="tool_calls_require_assistant_role"):
        ModelMessage(
            role="user",
            content="x",
            tool_calls=(ToolCallProposal("call_1", "read_file", {"path": "x"}),),
        )


def test_model_request_contract_rejects_invalid_generation_settings() -> None:
    with pytest.raises(ModelContractError, match="max_tokens_must_be_positive"):
        ModelRequest("p", "openai", "m", [ModelMessage("user", "x")], max_tokens=0)
    with pytest.raises(ModelContractError, match="temperature_out_of_range"):
        ModelRequest("p", "openai", "m", [ModelMessage("user", "x")], temperature=3)
    with pytest.raises(ModelContractError, match="disabled_reasoning_has_options"):
        ReasoningOptions(enabled=False, effort="high")


def test_openai_payload_supports_json_schema_and_current_cache_fields() -> None:
    provider = openai_provider(lambda _: httpx.Response(200, json={}))
    model_request = ModelRequest(
        "profile",
        "openai",
        "chat-model",
        [ModelMessage("system", "stable"), ModelMessage("user", "extract")],
        cache_ttl="5m",
        response_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
        response_schema_name="answer",
    )
    payload = provider._payload(model_request, stream=True)
    assert "prompt_cache_key" not in payload
    assert payload["prompt_cache_options"] == {"ttl": "5m"}
    assert payload["messages"][0]["content"][0]["prompt_cache_breakpoint"] == {
        "mode": "explicit"
    }
    assert payload["response_format"]["json_schema"]["name"] == "answer"
    assert payload["stream_options"] == {"include_usage": True}
    run(provider.aclose())


def test_json_schema_request_fails_closed_when_profile_does_not_support_it() -> None:
    provider = openai_provider(
        lambda _: httpx.Response(200, json={}),
        capabilities=ModelCapabilities(supports_streaming=True),
    )
    model_request = ModelRequest(
        "profile",
        "openai",
        "chat-model",
        [ModelMessage("user", "extract")],
        response_schema={"type": "object"},
    )
    with pytest.raises(ProviderUnsupportedCapabilityError, match="json_schema_unsupported"):
        provider._payload(model_request, stream=False)
    run(provider.aclose())


def test_openai_buffered_refusal_and_content_parts_are_normalized() -> None:
    provider = openai_provider(lambda _: httpx.Response(200, json={}))
    response = provider._parse_chat(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Cannot comply. "},
                            {"type": "refusal", "refusal": "Request refused."},
                        ]
                    },
                    "finish_reason": "content_filter",
                }
            ]
        }
    )
    assert response.text == "Cannot comply. Request refused."
    assert response.finish_reason == "error"
    run(provider.aclose())


def test_openrouter_in_band_error_fails_instead_of_becoming_empty_success() -> None:
    provider = openai_provider(lambda _: httpx.Response(200, json={}), provider="openrouter")
    with pytest.raises(ProviderConnectionError, match="provider_response_error:429"):
        provider._parse_chat(
            {
                "choices": [
                    {
                        "message": {"content": None},
                        "finish_reason": "error",
                        "error": {"code": 429, "message": "rate limited"},
                    }
                ]
            }
        )
    run(provider.aclose())


def test_openai_stream_assembles_fragmented_tool_call_and_done_does_not_override_finish() -> None:
    body = "\n\n".join(
        [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"read_","arguments":"{\\"path\\":"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"file","arguments":"\\"README.md\\"}"}}]},"finish_reason":"tool_calls"}]}',
            "data: [DONE]",
            "",
        ]
    )
    provider = openai_provider(lambda _: httpx.Response(200, text=body))
    events = run(collect(provider.stream_chat(request())))
    tool_events = [event for event in events if event.event_type == "tool_call_delta"]
    finish_events = [event for event in events if event.event_type == "finish"]
    assert tool_events[0].tool_call_delta == {
        "call_id": "call_1",
        "tool_name": "read_file",
        "arguments": {"path": "README.md"},
    }
    assert [event.finish_reason for event in finish_events] == ["tool_calls"]
    run(provider.aclose())


def test_openai_stream_preserves_length_finish_across_done_marker() -> None:
    body = (
        'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n\n'
        "data: [DONE]\n\n"
    )
    provider = openai_provider(lambda _: httpx.Response(200, text=body))
    events = run(collect(provider.stream_chat(request())))
    assert [event.finish_reason for event in events if event.event_type == "finish"] == [
        "length"
    ]
    run(provider.aclose())


def test_anthropic_stream_assembles_tool_use_input_json_deltas() -> None:
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "read_file",
                "input": {},
            },
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "input_json_delta", "partial_json": '{"path":'},
        },
        {
            "type": "content_block_delta",
            "index": 1,
            "delta": {"type": "input_json_delta", "partial_json": '"README.md"}'},
        },
        {"type": "content_block_stop", "index": 1},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    body = "\n\n".join(f"data: {json.dumps(event)}" for event in events) + "\n\n"
    provider = anthropic_provider(lambda _: httpx.Response(200, text=body))
    model_request = ModelRequest(
        "anthropic-profile",
        "anthropic",
        "claude-test",
        [ModelMessage("user", "read it")],
        [ToolSpec("read_file", "Read one file")],
    )
    streamed = run(collect(provider.stream_chat(model_request)))
    tool_events = [event for event in streamed if event.event_type == "tool_call_delta"]
    assert tool_events[0].tool_call_delta == {
        "call_id": "toolu_1",
        "tool_name": "read_file",
        "arguments": {"path": "README.md"},
    }
    assert [event.finish_reason for event in streamed if event.event_type == "finish"] == [
        "tool_calls"
    ]
    run(provider.aclose())


def test_shared_http_client_still_receives_provider_headers() -> None:
    seen: dict[str, str] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["authorization"] = http_request.headers.get("Authorization", "")
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
            },
        )

    provider = openai_provider(handler, headers={"Authorization": "Bearer secret"})
    response = run(provider.chat(request()))
    assert response.text == "ok"
    assert seen["authorization"] == "Bearer secret"
    run(provider.aclose())


def test_embedding_response_reports_the_embedding_model_not_chat_model() -> None:
    seen: dict[str, Any] = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(http_request.content.decode()))
        return httpx.Response(200, json={"data": [{"embedding": [1, 2.5]}]})

    provider = openai_provider(handler)
    response = run(
        provider.embed(
            EmbeddingRequest("profile", "openai", "text-embedding-3-small", "hello")
        )
    )
    assert seen["model"] == "text-embedding-3-small"
    assert response.model == "text-embedding-3-small"
    run(provider.aclose())


def test_router_uses_profile_settings_for_streamed_and_buffered_requests() -> None:
    profile = ModelProfile(
        profile_id="profile",
        provider="openai",
        model="chat-model",
        build_phase="phase_4",
        default_state="enabled",
        tui_launch_action="/model use profile",
        local_only=True,
        requires_network=False,
        raw={
            "temperature": 0.7,
            "max_tokens": 16000,
            "tool_call_mode": "native_or_text_json",
            "prompt_cache_ttl": "5m",
        },
    )
    router = ModelRouter(ModelProfileRegistry([profile]))
    buffered = router._request(
        profile,
        "openai",
        "chat-model",
        [ModelMessage("user", "x")],
        None,
        stream=False,
    )
    streamed = router._request(
        profile,
        "openai",
        "chat-model",
        [ModelMessage("user", "x")],
        None,
        stream=True,
    )
    assert streamed.temperature == buffered.temperature == 0.7
    assert streamed.max_tokens == buffered.max_tokens == 16000
    assert streamed.tool_call_mode == buffered.tool_call_mode == "native_or_text_json"
    assert streamed.cache_ttl == buffered.cache_ttl == "5m"


def test_builtin_profiles_separate_embedding_models_and_gemini_schema_support() -> None:
    registry = ModelProfileRegistry.load()
    openai = registry.resolve_profile_id("openai-hosted")
    gemini = registry.resolve_profile_id("gemini-hosted-openai-compatible")
    assert openai.raw["embedding_model"] == "text-embedding-3-small"
    assert gemini.raw["embedding_model"] == "gemini-embedding-2-preview"
    assert gemini.raw["supports_json_schema"] is True
