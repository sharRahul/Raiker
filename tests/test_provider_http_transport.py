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
