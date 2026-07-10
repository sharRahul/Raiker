"""Option A prompt caching: OpenAI-compatible cache hints + provider-agnostic
cache-hit metrics.

The KV cache lives inside each provider and is model-specific, so Raiker cannot
share one cache across models. What it does do: (1) send each backend's own
cache lever where one exists (OpenAI `prompt_cache_key`, llama.cpp
`cache_prompt`); (2) normalise every provider's `usage` block into one shape so
cache activity is visible irrespective of the model in use.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import (
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    summarize_model_usage,
)
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID

# ── Provider-agnostic usage normalisation ─────────────────────────────────────


class TestSummarizeUsage:
    def test_anthropic_shape(self) -> None:
        out = summarize_model_usage(
            {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 80, "cache_creation_input_tokens": 100}
        )
        assert out == {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_read_tokens": 80,
            "cache_write_tokens": 100,
            "cache_hit": 1,
        }

    def test_openai_shape_nested_cached_tokens(self) -> None:
        out = summarize_model_usage(
            {"prompt_tokens": 100, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 64}}
        )
        assert out["input_tokens"] == 100
        assert out["output_tokens"] == 20
        assert out["cache_read_tokens"] == 64
        assert out["cache_hit"] == 1
        assert "cache_write_tokens" not in out  # OpenAI reports no write metric

    def test_no_cache_hit_is_zero(self) -> None:
        out = summarize_model_usage({"input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 0})
        assert out["cache_read_tokens"] == 0
        assert out["cache_hit"] == 0

    def test_none_and_garbage_yield_empty(self) -> None:
        assert summarize_model_usage(None) == {}
        assert summarize_model_usage("nope") == {}  # type: ignore[arg-type]
        assert summarize_model_usage({}) == {}


# ── OpenAI-compatible cache hints (only where the backend documents one) ───────


def _caps() -> ModelCapabilities:
    return ModelCapabilities(supports_streaming=True, supports_tool_calls=True)


def _oai_provider(provider: str) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(
        f"{provider}-profile", provider, "m", "http://127.0.0.1:1234/v1", _caps(),
    )


def _req(**kw: Any) -> ModelRequest:
    d: dict[str, Any] = dict(
        profile_id="p", provider="x", model="m",
        messages=[ModelMessage("system", "s"), ModelMessage("user", "hi")],
    )
    d.update(kw)
    return ModelRequest(**d)


class TestOpenAICompatibleHints:
    def test_openai_gets_prompt_cache_key(self) -> None:
        payload = _oai_provider("openai")._payload(_req(cache_ttl="5m"), stream=False)
        assert payload["prompt_cache_key"] == "openai-profile"
        assert "cache_prompt" not in payload

    def test_llama_cpp_gets_cache_prompt(self) -> None:
        payload = _oai_provider("llama.cpp")._payload(_req(cache_ttl="5m"), stream=False)
        assert payload["cache_prompt"] is True
        assert "prompt_cache_key" not in payload

    def test_other_providers_get_no_hint(self) -> None:
        for provider in ("vllm", "ollama", "lm-studio", "gemini", "openrouter"):
            payload = _oai_provider(provider)._payload(_req(cache_ttl="5m"), stream=False)
            assert "cache_prompt" not in payload
            assert "prompt_cache_key" not in payload

    def test_no_hint_without_cache_ttl(self) -> None:
        payload = _oai_provider("openai")._payload(_req(), stream=False)
        assert "prompt_cache_key" not in payload

    def test_openai_stream_requests_usage(self) -> None:
        payload = _oai_provider("openai")._payload(_req(cache_ttl="5m"), stream=True)
        assert payload["stream_options"] == {"include_usage": True}

    def test_local_stream_omits_stream_options(self) -> None:
        # Local servers can reject stream_options — only OpenAI gets it.
        payload = _oai_provider("llama.cpp")._payload(_req(cache_ttl="5m"), stream=True)
        assert "stream_options" not in payload


# ── Streaming usage survives the streamed path (both providers) ────────────────


def _collect(provider: Any, request: ModelRequest) -> list[Any]:
    async def run() -> list[Any]:
        return [ev async for ev in provider.stream_chat(request)]

    return asyncio.run(run())


class TestStreamingUsage:
    def test_openai_stream_yields_usage_event(self) -> None:
        body = "\n".join([
            'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            'data: {"choices":[],"usage":{"prompt_tokens":50,"completion_tokens":5,"prompt_tokens_details":{"cached_tokens":40}}}',
            "data: [DONE]",
            "",
        ])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

        provider = AsyncOpenAICompatibleProvider(
            "openai-profile", "openai", "m", "https://api.openai.com/v1", _caps(),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        events = _collect(provider, _req(cache_ttl="5m", stream=True))
        usage_events = [e for e in events if e.event_type == "usage"]
        assert usage_events and usage_events[0].metadata["usage"]["prompt_tokens_details"]["cached_tokens"] == 40

    def test_anthropic_stream_yields_usage_event(self) -> None:
        body = "\n".join([
            'data: {"type":"message_start","message":{"usage":{"input_tokens":100,"cache_read_input_tokens":80}}}',
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":7}}',
            'data: {"type":"message_stop"}',
            "",
        ])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

        provider = AsyncAnthropicMessagesProvider(
            "anthropic-hosted", "anthropic", "claude-opus-4-8", "https://api.anthropic.com",
            ModelCapabilities(supports_streaming=True),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        events = _collect(provider, _req(cache_ttl="5m", stream=True))
        usage_events = [e for e in events if e.event_type == "usage"]
        assert usage_events
        merged = usage_events[0].metadata["usage"]
        assert merged["cache_read_input_tokens"] == 80 and merged["output_tokens"] == 7


# ── Orchestrator emits normalised cache metrics on model_request_completed ─────


def _envelope() -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"), session_id=new_id("sess_"), turn_id=new_id("turn_"),
        client=ClientMetadata(type="rest", name="test", version="0"),
        user=UserMetadata(), prompt=PromptPayload(text="hi"), options=PromptOptions(model_profile=""),
    )


def _completed_payload(gw: AgentGateway, turn_id: str) -> dict[str, Any]:
    from raiker.events.query import EventViewer

    viewer = EventViewer(gw.store)
    rows = gw.store.list_event_index(turn_id=turn_id, event_type="model_request_completed", limit=10)
    assert rows, "expected a model_request_completed event"
    payload = viewer.read_event_payload(rows[0]["event_id"])
    assert payload is not None
    return dict(payload["payload"])


class TestOrchestratorEmitsUsage:
    def test_completed_event_carries_normalised_cache_metrics(self, tmp_path: Any) -> None:
        gw = AgentGateway(tmp_path)
        env = _envelope()

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            return ModelResponse(
                text="ok", finish_reason="stop",
                usage={"input_tokens": 200, "output_tokens": 10, "cache_read_input_tokens": 160},
            )

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        asyncio.run(gw.runtime._acall_model(env, []))
        payload = _completed_payload(gw, env.turn_id)
        assert payload["usage"]["cache_read_tokens"] == 160
        assert payload["usage"]["cache_hit"] == 1

    def test_no_fallback_sequence_needed(self, tmp_path: Any) -> None:
        # Sanity: with no usage from the provider, the metric is an empty dict,
        # never a crash.
        gw = AgentGateway(tmp_path)
        gw.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, [])
        env = _envelope()

        async def fake_achat(provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
            return ModelResponse(text="ok", finish_reason="stop")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        asyncio.run(gw.runtime._acall_model(env, []))
        assert _completed_payload(gw, env.turn_id)["usage"] == {}
