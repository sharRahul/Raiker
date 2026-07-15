from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from raiker.models.contracts import (
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ReasoningOptions,
    ToolSpec,
)
from raiker.models.exceptions import (
    ProviderConfigurationError,
    ProviderUnsupportedCapabilityError,
)
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.providers.anthropic_messages import (
    AsyncAnthropicMessagesProvider,
    _to_anthropic_messages,
)
from raiker.models.registry import ModelProfileRegistry, profile_with_model


def _caps() -> ModelCapabilities:
    return ModelCapabilities(
        supports_streaming=True, supports_tool_calls=True,
        supports_reasoning=True, supports_reasoning_summary=True,
    )


def _provider(
    handler: Any, caps: ModelCapabilities | None = None
) -> AsyncAnthropicMessagesProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AsyncAnthropicMessagesProvider(
        "anthropic-hosted", "anthropic", "claude-opus-4-8",
        "https://api.anthropic.com", caps or _caps(), client=client,
    )


def _request(**kwargs: Any) -> ModelRequest:
    defaults: dict[str, Any] = dict(
        profile_id="anthropic-hosted", provider="anthropic", model="claude-opus-4-8",
        messages=[ModelMessage("system", "be safe"), ModelMessage("user", "hello")],
    )
    defaults.update(kwargs)
    return ModelRequest(**defaults)


# ── Message conversion ───────────────────────────────────────────────────────


def test_message_conversion_system_tool_and_merge() -> None:
    system, messages = _to_anthropic_messages([
        ModelMessage("system", "rules"),
        ModelMessage("user", "run the tool"),
        ModelMessage("assistant", "calling"),
        ModelMessage("tool", "result-data", tool_call_id="toolu_1"),
        ModelMessage("user", "and continue"),
    ])
    assert system == "rules"
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    # tool result and the following user text merge into one user turn
    merged = messages[2]["content"]
    assert merged[0]["type"] == "tool_result" and merged[0]["tool_use_id"] == "toolu_1"
    assert merged[1] == {"type": "text", "text": "and continue"}


# ── Chat ─────────────────────────────────────────────────────────────────────


def test_chat_payload_and_parse() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["version"] = request.headers.get("anthropic-version")
        seen.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "hi there"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    provider = _provider(handler)
    resp = asyncio.run(provider.chat(_request(
        tools=[ToolSpec("read_file", "read a file", {"type": "object", "properties": {}})],
        reasoning=ReasoningOptions(enabled=True, summary="summarized"),
    )))
    assert resp.text == "hi there" and resp.finish_reason == "stop"
    assert resp.usage == {"input_tokens": 10, "output_tokens": 5}
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["version"] == "2023-06-01"
    assert seen["system"] == "be safe"
    assert seen["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert seen["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert seen["thinking"] == {"type": "adaptive", "display": "summarized"}
    # Current-generation Anthropic models reject sampling params.
    assert "temperature" not in seen and "top_p" not in seen


def test_chat_parses_tool_use_blocks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [
                {"type": "text", "text": "using tool"},
                {"type": "tool_use", "id": "toolu_9", "name": "read_file", "input": {"path": "a.txt"}},
            ],
            "stop_reason": "tool_use",
        })

    resp = asyncio.run(_provider(handler).chat(_request()))
    assert resp.finish_reason == "tool_calls"
    assert resp.tool_calls[0].call_id == "toolu_9"
    assert resp.tool_calls[0].tool_name == "read_file"
    assert resp.tool_calls[0].arguments == {"path": "a.txt"}


def test_chat_refusal_maps_to_error_finish() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [], "stop_reason": "refusal"})

    resp = asyncio.run(_provider(handler).chat(_request()))
    assert resp.finish_reason == "error" and resp.text == ""


# ── Prompt caching (cost/latency: reuse the stable prompt prefix) ──────────────


def _cache_handler(seen: dict[str, Any]):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        seen["beta"] = request.headers.get("anthropic-beta")
        seen.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 8},
        })

    return handler


def test_no_cache_control_by_default() -> None:
    seen: dict[str, Any] = {}
    asyncio.run(_provider(_cache_handler(seen)).chat(_request()))
    # Default: system is a plain string, no cache_control, no beta header.
    assert seen["system"] == "be safe"
    assert seen["beta"] is None


def test_cache_control_5m_breaks_system_without_beta_header() -> None:
    seen: dict[str, Any] = {}
    asyncio.run(_provider(_cache_handler(seen)).chat(_request(cache_ttl="5m")))
    assert seen["system"] == [
        {"type": "text", "text": "be safe", "cache_control": {"type": "ephemeral"}}
    ]
    # 5-minute ephemeral cache needs no beta header.
    assert seen["beta"] is None


def test_cache_control_1h_sets_ttl_and_beta_header() -> None:
    seen: dict[str, Any] = {}
    asyncio.run(_provider(_cache_handler(seen)).chat(_request(cache_ttl="1h")))
    assert seen["system"] == [
        {"type": "text", "text": "be safe", "cache_control": {"type": "ephemeral", "ttl": "1h"}}
    ]
    assert seen["beta"] == "extended-cache-ttl-2025-04-11"


def test_invalid_cache_ttl_is_ignored() -> None:
    seen: dict[str, Any] = {}
    asyncio.run(_provider(_cache_handler(seen)).chat(_request(cache_ttl="30s")))
    assert seen["system"] == "be safe"
    assert seen["beta"] is None


def test_router_reads_prompt_cache_ttl_from_profile() -> None:
    from raiker.models.router import _cache_ttl

    profile = profile_with_model(
        ModelProfileRegistry.load().resolve_profile_id("anthropic-hosted"), "claude-sonnet-4"
    )
    # The shipped hosted-Anthropic profile opts into the default 5-minute cache.
    assert _cache_ttl(profile) == "5m"


def test_stream_chat_yields_text_deltas() -> None:
    body = "\n".join([
        'data: {"type": "message_start"}',
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hel"}}',
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "lo"}}',
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}',
        'data: {"type": "message_stop"}',
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

    async def main() -> list[Any]:
        events: list[Any] = []
        async for event in _provider(handler).stream_chat(_request(stream=True)):
            events.append(event)
        return events

    events = asyncio.run(main())
    assert "".join(e.text_delta for e in events if e.event_type == "text_delta") == "hello"
    # The streamed finish must arrive in contract vocabulary ("stop", not the raw
    # Anthropic "end_turn") — a ModelResponse is built from it downstream.
    assert events[-1].event_type == "finish" and events[-1].finish_reason == "stop"


def test_stream_chat_maps_stop_reasons_to_contract_vocabulary() -> None:
    from raiker.models.contracts import FINISH_REASONS

    def run(stop_reason: str) -> str:
        body = "\n".join([
            'data: {"type": "message_start"}',
            f'data: {{"type": "message_delta", "delta": {{"stop_reason": "{stop_reason}"}}}}',
            'data: {"type": "message_stop"}',
        ])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=body.encode(), headers={"content-type": "text/event-stream"}
            )

        async def main() -> str:
            async for event in _provider(handler).stream_chat(_request(stream=True)):
                if event.event_type == "finish":
                    assert event.finish_reason is not None
                    return event.finish_reason
            raise AssertionError("no finish event")

        return asyncio.run(main())

    assert run("end_turn") == "stop"
    assert run("max_tokens") == "length"
    assert run("tool_use") == "tool_calls"
    assert run("refusal") == "error"
    # Unknown future stop reasons stay inside the contract instead of crashing turns.
    assert run("some_future_reason") in FINISH_REASONS


def test_embeddings_unsupported() -> None:
    from raiker.models.contracts import EmbeddingRequest

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(500)

    with pytest.raises(ProviderUnsupportedCapabilityError):
        asyncio.run(_provider(handler).embed(
            EmbeddingRequest("anthropic-hosted", "anthropic", "claude-opus-4-8", "x")
        ))


# ── Factory / profiles ───────────────────────────────────────────────────────

_HOSTED_POLICY = ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True)


def test_hosted_profiles_registered() -> None:
    registry = ModelProfileRegistry.load()
    ids = {p.profile_id for p in registry.list_profiles()}
    assert {"anthropic-hosted", "openai-hosted", "gemini-hosted-openai-compatible"} <= ids


def test_anthropic_factory_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.anthropic.com")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    profile = profile_with_model(
        ModelProfileRegistry.load().resolve_profile_id("anthropic-hosted"), "claude-sonnet-4"
    )
    with pytest.raises(ProviderConfigurationError, match="provider_api_key_missing:ANTHROPIC_API_KEY"):
        ModelProviderFactory(policy=_HOSTED_POLICY).create(profile)


def test_anthropic_factory_builds_native_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.anthropic.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-never-real")
    profile = profile_with_model(
        ModelProfileRegistry.load().resolve_profile_id("anthropic-hosted"), "claude-sonnet-4"
    )
    provider = ModelProviderFactory(policy=_HOSTED_POLICY).create(profile)
    assert isinstance(provider, AsyncAnthropicMessagesProvider)
    assert provider.model == "claude-sonnet-4"
    asyncio.run(provider.aclose())


def test_openai_and_gemini_profiles_fail_closed_without_policy() -> None:
    registry = ModelProfileRegistry.load()
    from raiker.models.exceptions import ProviderPolicyError
    for profile_id in ("openai-hosted", "gemini-hosted-openai-compatible", "anthropic-hosted"):
        with pytest.raises(ProviderPolicyError):
            ModelProviderFactory().create(registry.resolve_profile_id(profile_id), require_model=False)


def test_openai_profile_builds_with_key_and_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.openai.com")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-real")
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openai-hosted")
    configured = type(profile)(**{**profile.__dict__, "model": "gpt-4o"})
    provider = ModelProviderFactory(policy=_HOSTED_POLICY).create(configured)
    assert provider.provider == "openai"
    asyncio.run(provider.aclose())
