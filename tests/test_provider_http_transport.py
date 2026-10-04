"""OPT-09 — the HTTP half both hosted-model adapters share."""

from __future__ import annotations

import asyncio
import inspect

import httpx
import pytest

from raiker.models.exceptions import (
    ProviderConnectionError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)
from raiker.models.providers import anthropic_messages, openai_compatible
from raiker.models.providers.http import (
    ProviderHttpTransport,
    json_object,
    provider_status_error,
)


def _transport(handler: object, **kwargs: object) -> ProviderHttpTransport:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    return ProviderHttpTransport(
        client,
        timeout=5.0,
        headers=kwargs.pop("headers", {"x-api-key": "k"}),  # type: ignore[arg-type]
        map_status=lambda status, body: provider_status_error(status, model="m", body=body),
    )


def test_headers_are_merged_into_each_request_not_set_on_a_borrowed_client() -> None:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json={})

    transport = _transport(handler)

    async def run() -> None:
        await transport.request("GET", "https://example.test/v1", headers={"extra": "1"})
        assert "x-api-key" not in transport.client.headers
        await transport.client.aclose()

    asyncio.run(run())
    assert seen[0]["x-api-key"] == "k"
    assert seen[0]["extra"] == "1"


def test_a_refusal_is_mapped_by_the_callback() -> None:
    transport = _transport(lambda _request: httpx.Response(429, text="slow down"))

    async def run() -> None:
        with pytest.raises(ProviderRateLimitError):
            await transport.request("GET", "https://example.test/")
        await transport.client.aclose()

    asyncio.run(run())


def test_transport_failures_become_provider_errors() -> None:
    def times_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refuses(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no", request=request)

    async def run() -> None:
        for handler, expected in ((times_out, ProviderTimeoutError), (refuses, ProviderConnectionError)):
            transport = _transport(handler)
            with pytest.raises(expected):
                await transport.request("GET", "https://example.test/")
            await transport.client.aclose()

    asyncio.run(run())


def test_a_streamed_refusal_is_read_and_mapped_before_any_line() -> None:
    body = '{"error":{"type":"insufficient_quota"}}'
    transport = _transport(lambda _request: httpx.Response(429, text=body))

    async def run() -> None:
        with pytest.raises(ProviderQuotaExhaustedError):
            async with transport.stream("POST", "https://example.test/"):
                pytest.fail("a refused stream must not be handed to the parser")
        await transport.client.aclose()

    asyncio.run(run())


def test_only_a_client_it_opened_is_closed() -> None:
    borrowed = httpx.AsyncClient()
    shared = ProviderHttpTransport(borrowed, timeout=1, headers={}, map_status=lambda s, b: ValueError())
    owned = ProviderHttpTransport(None, timeout=1, headers={}, map_status=lambda s, b: ValueError())

    async def run() -> None:
        await shared.aclose()
        await owned.aclose()
        assert not borrowed.is_closed
        assert owned.client.is_closed
        await borrowed.aclose()

    asyncio.run(run())


def test_json_object_refuses_anything_but_an_object() -> None:
    with pytest.raises(ProviderResponseValidationError, match="response_not_object"):
        json_object(httpx.Response(200, json=[1]))
    with pytest.raises(ProviderResponseValidationError, match="invalid_json_response"):
        json_object(httpx.Response(200, text="{"))


def test_neither_adapter_keeps_its_own_client_or_ladder() -> None:
    """The point of the change: one transport, one status ladder."""
    for module in (anthropic_messages, openai_compatible):
        source = inspect.getsource(module)
        assert "httpx.AsyncClient(" not in source, module.__name__
        assert "except httpx.TimeoutException" not in source, module.__name__
        assert "ProviderRateLimitError(" not in source, module.__name__


# DEC-25 — what a provider may send back is counted in bytes as it arrives.


def _bounded_transport(handler: object) -> ProviderHttpTransport:
    return _transport(handler)


def test_an_answer_past_the_bound_is_refused_rather_than_held(monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.models.providers import http as provider_http

    monkeypatch.setattr(provider_http, "MAX_RESPONSE_BYTES", 1024)
    transport = _bounded_transport(lambda _request: httpx.Response(200, content=b"x" * 5000))

    async def run() -> None:
        with pytest.raises(ProviderResponseValidationError, match="provider_response_too_large"):
            await transport.request("GET", "https://example.test/")
        await transport.client.aclose()

    asyncio.run(run())


def test_a_bound_counts_inflated_bytes_not_wire_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    import gzip

    from raiker.models.providers import http as provider_http

    monkeypatch.setattr(provider_http, "MAX_RESPONSE_BYTES", 4096)
    bomb = gzip.compress(b"0" * 1_000_000)
    assert len(bomb) < 4096
    transport = _bounded_transport(
        lambda _request: httpx.Response(200, content=bomb, headers={"content-encoding": "gzip"})
    )

    async def run() -> None:
        with pytest.raises(ProviderResponseValidationError, match="provider_response_too_large"):
            await transport.request("GET", "https://example.test/")
        await transport.client.aclose()

    asyncio.run(run())


def test_a_bounded_answer_is_handed_back_read_and_decoded_once() -> None:
    import gzip

    body = b'{"ok": true, "text": "caf\xc3\xa9"}'
    transport = _bounded_transport(
        lambda _request: httpx.Response(
            200, content=gzip.compress(body), headers={"content-encoding": "gzip"}
        )
    )

    async def run() -> httpx.Response:
        response = await transport.request("GET", "https://example.test/")
        await transport.client.aclose()
        return response

    response = asyncio.run(run())
    assert json_object(response) == {"ok": True, "text": "café"}
    assert "content-encoding" not in response.headers


def test_a_refusal_is_classified_from_its_first_part_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.models.providers import http as provider_http

    monkeypatch.setattr(provider_http, "MAX_ERROR_BODY_BYTES", 64)
    seen: list[str] = []

    def mapper(status: int, body: str) -> Exception:
        seen.append(body)
        return provider_status_error(status, model="m", body=body)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                400, text='{"error": "insufficient_quota"}' + " " * 100_000
            )
        )
    )
    transport = ProviderHttpTransport(client, timeout=5.0, headers={}, map_status=mapper)

    async def run() -> None:
        with pytest.raises(ProviderQuotaExhaustedError):
            await transport.request("POST", "https://example.test/")
        await client.aclose()

    asyncio.run(run())
    assert len(seen[0]) == 64


def _stream_of(chunks: list[bytes]) -> httpx.Response:
    async def body() -> object:
        for chunk in chunks:
            yield chunk

    return httpx.Response(200, content=body())  # type: ignore[arg-type]


def _lines(response: httpx.Response, **bounds: int) -> list[str]:
    from raiker.models.providers.http import bounded_lines

    async def run() -> list[str]:
        return [line async for line in bounded_lines(response, **bounds)]

    return asyncio.run(run())


def test_stream_lines_split_on_the_three_breaks_and_nothing_else() -> None:
    response = _stream_of([b"data: a\r", b"\ndata: b\nda", b"ta: \xe2\x80\xa8c\rdata: d"])
    lines = [line for line in _lines(response) if line]
    assert lines == ["data: a", "data: b", "data:  c", "data: d"]


def test_a_stream_line_that_never_ends_is_refused() -> None:
    from raiker.models.exceptions import ProviderStreamError

    response = _stream_of([b"data: " + b"x" * 512 for _ in range(10)])
    with pytest.raises(ProviderStreamError, match="provider_stream_line_too_large"):
        _lines(response, max_line_bytes=1024)


def test_a_stream_past_its_total_is_refused() -> None:
    from raiker.models.exceptions import ProviderStreamError

    response = _stream_of([b"data: {}\n" * 64 for _ in range(10)])
    with pytest.raises(ProviderStreamError, match="provider_stream_too_large"):
        _lines(response, max_total_bytes=2048)


def test_both_adapters_read_their_streams_through_the_bound() -> None:
    for module in (anthropic_messages, openai_compatible):
        source = inspect.getsource(module)
        assert "aiter_lines" not in source
        assert "bounded_lines(response)" in source


def test_the_new_refusals_have_sentences() -> None:
    from raiker.models.exceptions import provider_error_sentence

    fallback = provider_error_sentence("not_a_code")
    for code in (
        "provider_response_too_large",
        "provider_stream_too_large",
        "provider_stream_line_too_large",
    ):
        assert provider_error_sentence(code) != fallback
