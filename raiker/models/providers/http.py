"""The HTTP half every hosted-model adapter shares.

OPT-09. The Anthropic and OpenAI-compatible adapters each owned a client, merged
their headers into every request, translated ``httpx`` failures and HTTP status
into provider errors, and read a JSON object off a response — the same code
twice, with the status ladder copied beside a comment asking it be kept in step.
Their wire protocols are genuinely different and stay in the adapters: payload
shape, tool-call mapping, the stream parser, reasoning and model metadata.

Status mapping is a callback rather than a subclass hook, so an adapter that
has a refusal of its own (Anthropic's thinking-shape 400) puts it in front of
:func:`provider_status_error` without an inheritance tree.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from typing import Any

import httpx

from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
    ProviderWorkspaceRequiredError,
    is_quota_exhausted,
    needs_workspace_id,
    workspace_id_rejected,
)

__all__ = ["ProviderHttpTransport", "StatusMapper", "json_object", "provider_status_error"]

#: ``(status, body) -> exception``: what a refused request means to the caller.
StatusMapper = Callable[[int, str], Exception]


def provider_status_error(status: int, *, model: str, body: str = "") -> Exception:
    """The provider error an HTTP refusal stands for.

    Quota and the two workspace refusals are read from the body before the
    status is: providers answer an empty balance or a missing workspace with an
    ordinary 400 or 429 on a valid key, and status alone would send the owner to
    rotate a credential that is not the problem.
    """
    if workspace_id_rejected(status, body):
        return ProviderWorkspaceRequiredError(f"provider_workspace_invalid:http_{status}")
    if needs_workspace_id(status, body):
        return ProviderWorkspaceRequiredError(f"provider_workspace_required:http_{status}")
    if is_quota_exhausted(status, body):
        return ProviderQuotaExhaustedError(f"provider_quota_exhausted:http_{status}")
    if status in {401, 403}:
        return ProviderAuthenticationError(f"provider_auth_failed:http_{status}")
    if status == 404:
        return ProviderModelNotFoundError(f"model_not_found:{model}")
    if status == 408:
        return ProviderTimeoutError("provider_timeout")
    if status == 429:
        return ProviderRateLimitError("provider_rate_limited")
    if status >= 500:
        return ProviderConnectionError(f"provider_unavailable:http_{status}")
    return ProviderConnectionError(f"provider_http_error:http_{status}")


def json_object(response: httpx.Response) -> dict[str, Any]:
    """The response body as a JSON object, or a validation error saying why not."""
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise ProviderResponseValidationError("invalid_json_response") from exc
    if not isinstance(data, dict):
        raise ProviderResponseValidationError("response_not_object")
    return data


class ProviderHttpTransport:
    """One adapter's client, its headers, and how its refusals are read.

    A client passed in (the process pool's, or a test's) is borrowed and never
    closed here; one created here is owned and closed by :meth:`aclose`.
    Headers — the owner's key among them — are merged into each request rather
    than set on a borrowed client, so a pooled connection is never an
    authorization.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None,
        *,
        timeout: float,
        headers: Mapping[str, str],
        map_status: StatusMapper,
    ) -> None:
        self.headers = dict(headers)
        self.client = client or httpx.AsyncClient(timeout=timeout, headers=self.headers)
        self.owns_client = client is None
        self._map_status = map_status

    async def aclose(self) -> None:
        if self.owns_client:
            await self.client.aclose()

    async def request(
        self, method: str, url: str, *, headers: Mapping[str, str] | None = None, **kwargs: Any
    ) -> httpx.Response:
        """Send one request; a transport failure or a refusal raises a provider error."""
        try:
            response = await self.client.request(
                method, url, headers={**self.headers, **(headers or {})}, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("provider_connection_failed") from exc
        if response.status_code >= 400:
            raise self._map_status(response.status_code, response.text)
        return response

    @asynccontextmanager
    async def stream(
        self, method: str, url: str, *, headers: Mapping[str, str] | None = None, **kwargs: Any
    ) -> AsyncIterator[httpx.Response]:
        """Open a streamed response, raising the mapped refusal before any line is read.

        Transport failures are left to the caller's stream handler, which knows
        whether anything has been yielded yet.
        """
        async with self.client.stream(
            method, url, headers={**self.headers, **(headers or {})}, **kwargs
        ) as response:
            if response.status_code >= 400:
                # A streamed body has not been read yet, and classification
                # needs it; an error body is bounded.
                body = (await response.aread()).decode("utf-8", "replace")
                raise self._map_status(response.status_code, body)
            yield response
