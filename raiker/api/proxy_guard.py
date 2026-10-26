"""BUG-347 — a reverse proxy in front of a loopback-bound Raiker.

``raiker-web`` decides what is *local* from the connection. A reverse proxy on
the same machine (Caddy, nginx) that forwards to ``127.0.0.1`` is itself a
loopback peer, so without this guard every request from the internet would
arrive as a local one: password recovery reachable from anywhere, reads exempt
from the abuse window, and none of the public-bind guardrails in force.

A first fix (2026-10-26) told a proxy apart by its forwarding headers. Review
found the gap in that: a proxy that sends no forwarding header is, on the same
socket, indistinguishable from a browser on this computer. Headers cannot be
the boundary. So the classification now comes from **where the connection
arrived**, which no request can change:

* **The loopback listener** (``--host 127.0.0.1``, the default) is for this
  computer only. A request there is local when its peer is loopback. Any
  forwarding header (``Forwarded``, ``X-Forwarded-For``, ``X-Forwarded-Host``,
  ``X-Forwarded-Proto``, ``X-Real-IP``) is refused with
  ``proxied_request_refused`` and a reason naming what to change: the common
  misconfiguration, a proxy pointed at this listener, is caught whenever the
  proxy says it is one. A proxy that says nothing cannot be caught here, which
  is why the documentation never points a proxy at this listener.
* **The proxy listener** (``--proxy-port`` on ``127.0.0.1``, or
  ``--proxy-socket``, a Unix domain socket) exists only for a reverse proxy.
  **Every** request on it is remote, whatever its headers say: no recovery, no
  instance list, no loopback rate exemption, rate limited in its own bucket, and
  answered with HSTS when the proxy says the browser came over HTTPS. Opening it
  requires ``RAIKER_OWNER_TOKEN`` to be set (BUG-358: its value is not yet read), exactly as
  ``--allow-public`` does.
* A connection with no TCP address (a Unix socket) is never local, on any
  listener.

Forwarding headers identify nobody: the client address a proxy reports is not
used as an identity or a rate-limit key. They only ever make a request *less*
trusted.

``RAIKER_TRUSTED_PROXY`` (the header-based trust of the first fix) is no longer
read; ``raiker-web`` refuses to start while it is set, so a configuration made
for it cannot silently change meaning.

What the guard saw is kept on the app (``remote_access``) so Diagnostics can
say how the host is reached and what it refused.
"""

from __future__ import annotations

import ipaddress
import json
import threading
from dataclasses import dataclass
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.contracts.ids import utc_now

#: The first fix's setting. Refused at start (see ``raiker.api.serve``).
RETIRED_TRUSTED_PROXY_ENV = "RAIKER_TRUSTED_PROXY"

#: Headers a reverse proxy adds. Any one of them marks a request as forwarded.
FORWARDING_HEADERS = frozenset(
    {b"forwarded", b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto", b"x-real-ip"}
)

#: The scope key the guard sets on a request that arrived on the proxy listener.
PROXIED_SCOPE_KEY = "raiker.proxied"

#: The rate-limit bucket every proxied request shares: the address a proxy
#: reports is not an identity, and the proxy's own peer is this computer.
PROXY_RATE_KEY = "proxy-listener"

REFUSAL_REASON = "proxied_request_refused"
REFUSAL_MESSAGE = (
    "This request reached Raiker's local listener through a reverse proxy, so it was refused. "
    "That listener is for this computer only. Point the proxy at Raiker's proxy listener instead "
    "(start raiker-web with --proxy-port or --proxy-socket, with RAIKER_OWNER_TOKEN set), or bind "
    "Raiker to a private address with --allow-public. An SSH tunnel needs neither."
)


@dataclass(frozen=True)
class ProxyListener:
    """The listener a reverse proxy connects to. Everything on it is remote."""

    port: int | None = None
    socket_path: str | None = None

    def describe(self) -> str:
        if self.socket_path:
            return f"unix:{self.socket_path}"
        return f"127.0.0.1:{self.port}"

    def accepted(self, scope: Scope) -> bool:
        """Whether this connection arrived on the proxy listener."""
        server = scope.get("server")
        if not isinstance(server, (tuple, list)) or len(server) < 2:
            return False
        if self.socket_path is not None and server[1] is None:
            return True
        return self.port is not None and server[1] == self.port


def is_forwarded(scope: Scope) -> bool:
    """True when any forwarding header is present on the request."""
    return any(name.lower() in FORWARDING_HEADERS for name, _value in scope.get("headers") or ())


def arrived_without_tcp(scope: Scope) -> bool:
    """A connection with no TCP address: a Unix socket, never this computer's browser."""
    server = scope.get("server")
    return server is None or (isinstance(server, (tuple, list)) and len(server) >= 2 and server[1] is None)


def peer_is_loopback(scope: Scope) -> bool:
    client = scope.get("client")
    if not isinstance(client, (tuple, list)) or not client:
        return False
    host = str(client[0])
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_local_request(scope: Scope) -> bool:
    """The one answer every local-only check uses.

    Local means: a loopback peer, over TCP, on the loopback listener, carrying
    no forwarding header. The proxy listener's requests are marked by the guard
    before anything inside it asks.
    """
    return (
        peer_is_loopback(scope)
        and not arrived_without_tcp(scope)
        and not is_forwarded(scope)
        and not scope.get(PROXIED_SCOPE_KEY)
    )


def _forwarded_https(scope: Scope) -> bool:
    for name, value in scope.get("headers") or ():
        lowered = name.lower()
        text = value.decode("latin-1").lower()
        if lowered == b"x-forwarded-proto" and text.split(",")[0].strip() == "https":
            return True
        if lowered == b"forwarded" and "proto=https" in text.replace(" ", ""):
            return True
    return False


class RemoteAccessRecord:
    """What the guard has seen since the host started, for Diagnostics."""

    def __init__(self, *, loopback_only: bool, listener: ProxyListener | None) -> None:
        self._lock = threading.Lock()
        self.loopback_only = loopback_only
        self.listener = listener.describe() if listener is not None else None
        self.refused = 0
        self.served = 0
        self.last_refused_at: str | None = None
        self.last_served_at: str | None = None

    def note(self, *, refused: bool) -> None:
        with self._lock:
            if refused:
                self.refused += 1
                self.last_refused_at = utc_now()
            else:
                self.served += 1
                self.last_served_at = utc_now()

    def view(self) -> dict[str, Any]:
        with self._lock:
            if not self.loopback_only:
                mode = "public"
            elif self.listener:
                mode = "proxy_listener"
            else:
                mode = "loopback"
            return {
                "mode": mode,
                "proxy_listener": self.listener,
                "proxied_requests_refused": self.refused,
                "proxied_requests_served": self.served,
                "last_refused_at": self.last_refused_at,
                "last_served_at": self.last_served_at,
            }


class ProxyGuardMiddleware:
    """Mark the proxy listener's requests remote; refuse forwarded ones on the loopback listener."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        loopback_only: bool,
        record: RemoteAccessRecord,
        listener: ProxyListener | None,
    ) -> None:
        self.app = app
        self._loopback_only = loopback_only
        self._record = record
        self._listener = listener

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        if self._listener is not None and self._listener.accepted(scope):
            await self._serve_proxied(scope, receive, send)
            return
        if not is_forwarded(scope) or not self._loopback_only:
            # A public bind already runs under the public posture; a forwarded
            # request there is simply remote, which `is_local_request` says.
            await self.app(scope, receive, send)
            return
        self._record.note(refused=True)
        await _refuse(scope, send)

    async def _serve_proxied(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Remote by the listener it arrived on, headers or not.
        self._record.note(refused=False)
        scope = {**scope, PROXIED_SCOPE_KEY: True}
        if scope["type"] != "http" or not _forwarded_https(scope):
            await self.app(scope, receive, send)
            return

        async def with_hsts(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    *message.get("headers", []),
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                ]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, with_hsts)


async def _refuse(scope: Scope, send: Send) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    path = str(scope.get("path") or "")
    if path.startswith("/api") or "/api/" in path:
        body = json.dumps(
            {"detail": {"ok": False, "reason_code": REFUSAL_REASON, "message": REFUSAL_MESSAGE}}
        ).encode("utf-8")
        content_type = b"application/json"
    else:
        body = f"Raiker refused this request.\n\n{REFUSAL_MESSAGE}\n".encode()
        content_type = b"text/plain; charset=utf-8"
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", content_type), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
