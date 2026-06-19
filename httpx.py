from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

__version__ = "0.27.0-local-shim"


class HTTPError(Exception): ...
class TimeoutException(HTTPError): ...

@dataclass
class Request:
    method: str
    url: str
    content: bytes = b""

class Response:
    def __init__(self, status_code: int = 200, *, json: Any = None, text: str | None = None, content: bytes | None = None) -> None:
        self.status_code = status_code
        self._json = json
        if content is not None:
            self.content = content
        elif text is not None:
            self.content = text.encode()
        elif json is not None:
            self.content = _json.dumps(json).encode()
        else:
            self.content = b""
    def json(self) -> Any:
        if self._json is not None:
            return self._json
        return _json.loads(self.content.decode())
    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self.content.decode().splitlines():
            yield line

class MockTransport:
    def __init__(self, handler: Callable[[Request], Response]) -> None:
        self.handler = handler

class _StreamContext:
    def __init__(self, response: Response) -> None:
        self.response = response
    async def __aenter__(self) -> Response:
        return self.response
    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

class AsyncClient:
    def __init__(self, *, timeout: float | None = None, headers: dict[str, str] | None = None, transport: MockTransport | None = None) -> None:
        self.timeout = timeout
        self.headers = headers or {}
        self.transport = transport
        self.closed = False
    async def request(self, method: str, url: str, **kwargs: Any) -> Response:
        if self.closed:
            raise HTTPError("client_closed")
        content = b""
        if "json" in kwargs:
            content = _json.dumps(kwargs["json"]).encode()
        if self.transport:
            return self.transport.handler(Request(method, url, content))
        raise HTTPError("network_unavailable_in_local_httpx_shim")
    def stream(self, method: str, url: str, **kwargs: Any) -> _StreamContext:
        async def _none() -> None: ...
        # Execute synchronously via transport because MockTransport handlers are sync.
        content = b""
        if "json" in kwargs:
            content = _json.dumps(kwargs["json"]).encode()
        if self.transport:
            return _StreamContext(self.transport.handler(Request(method, url, content)))
        return _StreamContext(Response(599, json={"error": "network_unavailable_in_local_httpx_shim"}))
    async def aclose(self) -> None:
        self.closed = True
