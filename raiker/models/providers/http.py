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

import codecs
import json
import re
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
    ProviderStreamError,
    ProviderTimeoutError,
    ProviderWorkspaceRequiredError,
    is_quota_exhausted,
    needs_workspace_id,
    workspace_id_rejected,
)

__all__ = [
    "MAX_ERROR_BODY_BYTES",
    "MAX_RESPONSE_BYTES",
    "MAX_STREAM_BYTES",
    "MAX_STREAM_LINE_BYTES",
    "ProviderHttpTransport",
    "StatusMapper",
    "bounded_lines",
    "json_object",
    "provider_status_error",
]

# DEC-25 — what a provider may send back, counted in bytes as they arrive.
#
# Every hosted adapter read its answer with ``client.request(...)``, which holds
# the whole body in memory before anything looks at it, and a refusal's body was
# read the same way. A provider is a destination the owner chose, not one Raiker
# trusts with its memory: a private server, a misbehaving proxy or a gzip body
# that inflates a thousandfold could hand the host as much as it liked. The
# counts are of *decoded* bytes, so a compressed body is bounded by what it
# inflates to rather than by what crossed the wire.
#
# The limits are generous for the real thing: the largest ordinary answer is a
# catalogue (OpenRouter's is a few megabytes), and a stream carrying a maximal
# answer with its reasoning is tens of megabytes of SSE framing at most.
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
#: A refusal is read to classify it (quota, workspace, auth); its first 64 kB say which.
MAX_ERROR_BODY_BYTES = 64 * 1024
#: One SSE line carries one event; a line that never ends is not an event.
MAX_STREAM_LINE_BYTES = 4 * 1024 * 1024
MAX_STREAM_BYTES = 128 * 1024 * 1024

_LINE_BREAK = re.compile(r"\r\n|\r|\n")

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


async def _read_capped(response: httpx.Response, limit: int) -> tuple[bytes, bool]:
    """Up to ``limit`` decoded bytes of a streamed body, and whether there was more."""
    body = bytearray()
    async for chunk in response.aiter_bytes():
        room = limit - len(body)
        if len(chunk) > room:
            body.extend(chunk[:room])
            return bytes(body), True
        body.extend(chunk)
    return bytes(body), False


async def bounded_lines(
    response: httpx.Response,
    *,
    max_line_bytes: int = MAX_STREAM_LINE_BYTES,
    max_total_bytes: int = MAX_STREAM_BYTES,
) -> AsyncIterator[str]:
    """The lines of a streamed body, refusing a line or a stream past its bound.

    ``httpx``'s own ``aiter_lines`` buffers until it sees a line break, so a
    server that never sends one grows that buffer for as long as it likes. This
    splits on the same three breaks (CRLF, CR, LF) and nothing
    else — ``str.splitlines`` would also split on U+2028, which JSON carries
    unescaped — and stops with :class:`ProviderStreamError` the moment either
    bound is crossed, before the excess is held.
    """
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    pending = ""
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_total_bytes:
            raise ProviderStreamError("provider_stream_too_large")
        pending += decoder.decode(chunk)
        parts = _LINE_BREAK.split(pending)
        pending = parts.pop()
        # A lone CR at the end of a chunk may be the first half of a CRLF;
        # splitting there costs one empty line, which every SSE reader skips.
        for line in parts:
            yield line
        if len(pending) > max_line_bytes:
            raise ProviderStreamError("provider_stream_line_too_large")
    pending += decoder.decode(b"", final=True)
    for line in _LINE_BREAK.split(pending):
        if line:
            yield line


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
        """Send one request; a transport failure or a refusal raises a provider error.

        The body is read here, by its decoded bytes, and refused past
        :data:`MAX_RESPONSE_BYTES` (a refusal's past :data:`MAX_ERROR_BODY_BYTES`,
        which is truncated rather than refused: its first part classifies it).
        The response handed back is already read, so ``.json()`` and ``.text``
        never touch the network again.
        """
        timeout = kwargs.pop("timeout", httpx.USE_CLIENT_DEFAULT)
        request = self.client.build_request(
            method, url, headers={**self.headers, **(headers or {})}, timeout=timeout, **kwargs
        )
        try:
            response = await self.client.send(request, stream=True)
            try:
                limit = MAX_ERROR_BODY_BYTES if response.status_code >= 400 else MAX_RESPONSE_BYTES
                body, over = await _read_capped(response, limit)
            finally:
                await response.aclose()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("provider_connection_failed") from exc
        if response.status_code >= 400:
            raise self._map_status(response.status_code, body.decode("utf-8", "replace"))
        if over:
            raise ProviderResponseValidationError("provider_response_too_large")
        # The bytes above are already decoded, so the copy must not claim an
        # encoding (httpx would inflate them a second time) or a length.
        kept = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        ]
        return httpx.Response(
            response.status_code, headers=kept, content=body, request=request
        )

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
                # needs it — its first part, never all of it (DEC-25).
                body, _over = await _read_capped(response, MAX_ERROR_BODY_BYTES)
                raise self._map_status(response.status_code, body.decode("utf-8", "replace"))
            yield response
