"""Provider fault-injection matrix against a real local socket (beta plan MD-5).

Each case is a TCP server on 127.0.0.1 that misbehaves the way a provider
does in the wild: a 429 carrying ``Retry-After``, a 500, an answer that stops
mid-stream, a reset connection, a malformed event, an exhausted quota. The
real OpenAI-compatible and Anthropic adapters talk to it over the network
stack (no mock transport), and every case asserts two things:

* the failure arrives as the typed provider error that the router and the
  readiness ledger act on (rate limit, quota, timeout, connection, stream);
* the adapter never emits a ``finish`` it did not receive, so a turn cannot
  report as complete an answer the provider did not finish.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest

from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.exceptions import (
    ModelProviderError,
    ProviderConnectionError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitError,
    ProviderStreamError,
    ProviderTimeoutError,
)
from raiker.models.providers.anthropic_messages import AsyncAnthropicMessagesProvider
from raiker.models.providers.http import retry_after_seconds
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider

Writer = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


async def _read_request(reader: asyncio.StreamReader) -> None:
    head = await reader.readuntil(b"\r\n\r\n")
    length = 0
    for line in head.decode("latin-1").split("\r\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1])
    if length:
        await reader.readexactly(length)


def _respond(status: str, headers: dict[str, str], body: bytes, *, close: bool = True) -> Writer:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _read_request(reader)
        lines = [f"HTTP/1.1 {status}", f"Content-Length: {len(body)}", "Connection: close"]
        lines += [f"{name}: {value}" for name, value in headers.items()]
        writer.write(("\r\n".join(lines) + "\r\n\r\n").encode() + body)
        await writer.drain()
        if close:
            writer.close()

    return handler


def _sse(chunks: list[bytes], *, then: str) -> Writer:
    """Stream ``chunks``, then ``reset`` the socket, ``hang`` or ``close`` it cleanly."""

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _read_request(reader)
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
        )
        for chunk in chunks:
            writer.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            await writer.drain()
        if then == "reset":
            transport = writer.transport
            sock = transport.get_extra_info("socket")
            if sock is not None:
                import socket
                import struct

                sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            transport.abort()
        elif then == "hang":
            await asyncio.sleep(30)
        else:
            writer.write(b"0\r\n\r\n")
            await writer.drain()
            writer.close()

    return handler


@contextlib.asynccontextmanager
async def fault_server(handler: Writer) -> AsyncIterator[str]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(server.wait_closed(), 1)


def _openai(endpoint: str, *, timeout: float = 5.0) -> AsyncOpenAICompatibleProvider:
    return AsyncOpenAICompatibleProvider(
        profile_id="fault",
        provider="openai",
        model="fault-model",
        endpoint=endpoint,
        capabilities=ModelCapabilities(supports_streaming=True),
        timeout=timeout,
        client=httpx.AsyncClient(timeout=timeout),
    )


def _anthropic(endpoint: str, *, timeout: float = 5.0) -> AsyncAnthropicMessagesProvider:
    return AsyncAnthropicMessagesProvider(
        profile_id="fault-a",
        provider="anthropic",
        model="claude-fault",
        endpoint=endpoint,
        capabilities=ModelCapabilities(supports_streaming=True),
        extra_headers={"x-api-key": "fault"},
        timeout=timeout,
        client=httpx.AsyncClient(timeout=timeout),
    )


def _request(stream: bool) -> ModelRequest:
    return ModelRequest("fault", "openai", "fault-model", [ModelMessage("user", "hi")], stream=stream)


async def _stream(provider: Any) -> tuple[list[Any], BaseException | None]:
    events: list[Any] = []
    try:
        async for event in provider.stream_chat(_request(True)):
            events.append(event)
    except BaseException as exc:  # noqa: BLE001 - the matrix records what was raised
        return events, exc
    finally:
        await provider.aclose()
    return events, None


async def _chat(provider: Any) -> BaseException | None:
    try:
        await provider.chat(_request(False))
    except BaseException as exc:  # noqa: BLE001
        return exc
    finally:
        await provider.aclose()
    return None


def _finished(events: list[Any]) -> bool:
    return any(getattr(event, "event_type", None) == "finish" for event in events)


def _delta(text: str) -> bytes:
    return f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n".encode()


# ── Refusals before any answer ─────────────────────────────────────────────


def test_a_429_with_retry_after_is_a_rate_limit_that_states_the_wait() -> None:
    async def case() -> None:
        handler = _respond("429 Too Many Requests", {"Retry-After": "42"}, b'{"error":{"message":"slow down"}}')
        async with fault_server(handler) as url:
            raised = await _chat(_openai(url))
        assert isinstance(raised, ProviderRateLimitError)
        assert raised.retry_after_seconds == 42

    asyncio.run(case())


def test_a_streamed_429_carries_the_wait_too() -> None:
    async def case() -> None:
        handler = _respond("429 Too Many Requests", {"Retry-After": "7"}, b"{}")
        async with fault_server(handler) as url:
            events, raised = await _stream(_anthropic(url))
        assert isinstance(raised, ProviderRateLimitError)
        assert raised.retry_after_seconds == 7
        assert events == []

    asyncio.run(case())


def test_a_500_is_an_unavailable_provider() -> None:
    async def case() -> None:
        async with fault_server(_respond("500 Internal Server Error", {}, b"boom")) as url:
            raised = await _chat(_openai(url))
        assert isinstance(raised, ProviderConnectionError)
        assert "provider_unavailable:http_500" in str(raised)

    asyncio.run(case())


def test_an_exhausted_quota_is_not_reported_as_a_rate_limit() -> None:
    async def case() -> None:
        body = json.dumps({"error": {"type": "insufficient_quota", "code": "insufficient_quota"}}).encode()
        async with fault_server(_respond("429 Too Many Requests", {}, body)) as url:
            raised = await _chat(_openai(url))
        assert isinstance(raised, ProviderQuotaExhaustedError)

    asyncio.run(case())


def test_a_connection_reset_before_the_answer_is_a_connection_failure() -> None:
    async def case() -> None:
        async def reset(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await _read_request(reader)
            writer.transport.abort()

        async with fault_server(reset) as url:
            raised = await _chat(_openai(url))
        assert isinstance(raised, ProviderConnectionError)

    asyncio.run(case())


# ── Failures in the middle of an answer ────────────────────────────────────


@pytest.mark.parametrize("make", [_openai, _anthropic], ids=["openai", "anthropic"])
def test_a_stream_that_stops_mid_answer_never_claims_to_have_finished(make: Callable[..., Any]) -> None:
    async def case() -> None:
        first = (
            _delta("Half an ans")
            if make is _openai
            else b'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":1}}}\n\n'
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,'
            b'"delta":{"type":"text_delta","text":"Half an ans"}}\n\n'
        )
        async with fault_server(_sse([first], then="reset")) as url:
            events, raised = await _stream(make(url))
        assert isinstance(raised, ModelProviderError), raised
        assert not _finished(events)

    asyncio.run(case())


def test_a_stream_that_goes_silent_times_out_without_a_finish() -> None:
    async def case() -> None:
        async with fault_server(_sse([_delta("thinking")], then="hang")) as url:
            events, raised = await _stream(_openai(url, timeout=0.5))
        assert isinstance(raised, ProviderTimeoutError | ProviderStreamError | ProviderConnectionError), raised
        assert not _finished(events)

    asyncio.run(case())


def test_a_malformed_event_is_a_stream_error() -> None:
    async def case() -> None:
        async with fault_server(_sse([_delta("ok "), b"data: {not json\n\n"], then="close")) as url:
            events, raised = await _stream(_openai(url))
        assert isinstance(raised, ProviderStreamError)
        assert "malformed_sse_json" in str(raised)
        assert not _finished(events)

    asyncio.run(case())


@pytest.mark.parametrize("make", [_openai, _anthropic], ids=["openai", "anthropic"])
def test_a_stream_closed_cleanly_without_its_end_is_not_a_finished_answer(
    make: Callable[..., Any],
) -> None:
    """The quiet failure: the socket closes in order, but the provider never
    said the answer was done. Raiker must not treat that as a finished turn."""

    async def case() -> None:
        async with fault_server(_sse([_delta("Partial")], then="close")) as url:
            events, raised = await _stream(make(url))
        assert not _finished(events)
        assert isinstance(raised, ProviderStreamError), raised

    asyncio.run(case())


# ── Retry-After parsing ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [("42", 42.0), ("0", 0.0), (None, None), ("soon", None), ("-5", 0.0), ("999999", 24 * 3600.0)],
)
def test_retry_after_reads_seconds(value: str | None, expected: float | None) -> None:
    assert retry_after_seconds(value) == expected


def test_retry_after_reads_an_http_date() -> None:
    assert retry_after_seconds("Thu, 01 Jan 1970 00:01:40 GMT", now=40.0) == 60.0


def test_a_prompt_longer_than_the_context_is_named_not_a_bare_400() -> None:
    """MD-3, 2026-11-07 — llama-server refused a 9,459-token turn sized at 8,192."""
    from raiker.models.exceptions import (
        ProviderConfigurationError,
        provider_error_code,
        provider_failure_message,
    )
    from raiker.models.providers.http import provider_status_error

    body = '{"error":{"code":400,"message":"request (9459 tokens) exceeds the available context size (8192 tokens), try increasing it","type":"exceed_context_size_error"}}'
    error = provider_status_error(400, model="local-gguf", body=body)
    assert isinstance(error, ProviderConfigurationError)
    code = provider_error_code(error)
    assert code.startswith("provider_context_exceeded")
    assert "longer than the context the model was started with" in provider_failure_message(code)
    # An ordinary 400 is still an ordinary 400.
    assert provider_error_code(provider_status_error(400, model="m", body="bad request")).startswith("provider_http_error")
