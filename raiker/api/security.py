from __future__ import annotations

import json
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Hardening for single-user, internet-accessible exposure. Raiker stays a
# single-owner agent: every request still authenticates as the one owner
# principal (see raiker/api/auth.py). These middlewares add the transport-level
# guardrails that make binding beyond loopback defensible — they do NOT add
# multi-tenant identity.

_SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
)


async def _send_json(send: Send, status_code: int, body: dict[str, object]) -> None:
    raw = json.dumps(body).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(raw)).encode("latin-1")),
            *(_SECURITY_HEADERS),
        ],
    })
    await send({"type": "http.response.body", "body": raw, "more_body": False})


class SecurityHeadersMiddleware:
    """Adds conservative security headers to every response.

    HSTS is only emitted when ``hsts`` is enabled (it must not be sent over
    plain HTTP / loopback, where it would pin a non-TLS origin incorrectly).
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self._hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {key.lower() for key, _ in headers}
                for key, value in _SECURITY_HEADERS:
                    if key not in existing:
                        headers.append((key, value))
                if self._hsts and b"strict-transport-security" not in existing:
                    headers.append(
                        (b"strict-transport-security", b"max-age=63072000; includeSubDomains")
                    )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, wrapped)


class MaxBodySizeMiddleware:
    """Rejects requests whose declared Content-Length exceeds ``max_bytes`` (413)."""

    def __init__(self, app: ASGIApp, *, max_bytes: int = 1_000_000) -> None:
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self._max_bytes:
                    await _send_json(
                        send, 413,
                        {"ok": False, "reason_code": "request_body_too_large"},
                    )
                    return
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Fixed-window in-memory rate limit per client IP, applied to ``/api`` paths.

    Single-user and process-local: this is a denial-of-service guardrail for an
    exposed bind, not an auth boundary. The auth check (bearer token -> owner
    principal) remains the real gate.
    """

    def __init__(self, app: ASGIApp, *, max_requests: int = 120, window_seconds: float = 60.0) -> None:
        self.app = app
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, scope: Scope) -> str:
        client = scope.get("client")
        if isinstance(client, (tuple, list)) and client:
            return str(client[0])
        return "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api"):
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        key = self._client_key(scope)
        hits = self._hits[key]
        cutoff = now - self._window
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self._max:
            await _send_json(send, 429, {"ok": False, "reason_code": "rate_limited"})
            return
        hits.append(now)
        await self.app(scope, receive, send)
