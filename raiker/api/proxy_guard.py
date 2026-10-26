"""BUG-347 / BUG-358 — which requests come from this computer, and which do not.

``raiker-web`` decides what is *local* from the connection, never from what a
request says about itself. A reverse proxy on the same machine (Caddy, nginx)
that forwards to ``127.0.0.1`` is itself a loopback peer, so without this guard
every request from the internet would arrive as a local one.

Classification comes from **where the connection arrived**, which no request
can change:

* **The local listener** (``127.0.0.1``, always) is for this computer only. A
  request there is local when its peer is loopback. Any forwarding header
  (``Forwarded``, ``X-Forwarded-For``, ``X-Forwarded-Host``,
  ``X-Forwarded-Proto``, ``X-Real-IP``) is refused with
  ``proxied_request_refused`` and a reason naming what to change: the common
  misconfiguration, a proxy pointed at this listener, is caught whenever the
  proxy says it is one. A proxy that says nothing cannot be caught here, which
  is why the proxy has a listener of its own.
* **The remote listener** — one of two kinds, set in Settings → Security →
  Remote access (``raiker/app/remote_access.py``):

  * a **reverse-proxy** listener on ``127.0.0.1:<port>`` or a Unix domain
    socket, where the proxy terminates HTTPS. Its ``X-Forwarded-Proto`` is
    believed *only here*, and only to say the browser used HTTPS;
  * a **private-network** listener on a private or VPN address, where Raiker
    terminates HTTPS itself with the owner's certificate.

  **Every** request on it is remote, whatever its headers say: no recovery, no
  instance list, no host restart, no loopback rate exemption, and (BUG-358)
  no session that was not established with the password *and* an MFA code
  from a remote device. A request that did not reach the outside entry point
  over HTTPS is refused (``remote_https_required``), except the health probe a
  proxy uses. HSTS is added to every remote answer.
* A connection with no TCP address (a Unix socket) is never local.

Forwarding headers identify nobody: the client address a proxy reports is not
used as an identity or a rate-limit key. They only ever make a request *less*
trusted, or, on the proxy listener alone, say that the browser used HTTPS.

What the guard saw is kept on the app (``remote_access``) so Diagnostics and
Settings can say how the host is reached and what it refused. Turning remote
access off takes effect here at once, before the listener closes on restart.
"""

from __future__ import annotations

import ipaddress
import json
import threading
from dataclasses import dataclass
from typing import Any, Literal

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.contracts.ids import utc_now

#: Settings and start options that earlier builds read. Refused at start
#: (``raiker.api.serve``), so a configuration made for them cannot silently
#: change meaning.
RETIRED_TRUSTED_PROXY_ENV = "RAIKER_TRUSTED_PROXY"

#: Headers a reverse proxy adds. Any one of them marks a request as forwarded.
FORWARDING_HEADERS = frozenset(
    {b"forwarded", b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto", b"x-real-ip"}
)

#: The scope key the guard sets on a request that arrived on the remote listener.
REMOTE_SCOPE_KEY = "raiker.remote"
#: Set beside it when the outside entry point was reached over HTTPS.
REMOTE_HTTPS_SCOPE_KEY = "raiker.remote_https"

#: The rate-limit bucket every request on a proxy listener shares: the address
#: a proxy reports identifies nobody, and the proxy's own peer is this computer.
PROXY_RATE_KEY = "proxy-listener"

#: The one path answered on a remote listener without HTTPS: a proxy's health
#: check, which says only that the host answers.
HTTPS_EXEMPT_PATHS = frozenset({"/api/health"})

REFUSAL_REASON = "proxied_request_refused"
REFUSAL_MESSAGE = (
    "This request reached Raiker's local listener through a reverse proxy, so it was refused. "
    "That listener is for this computer only. In Settings → Security → Remote access, choose "
    "Reverse proxy and point the proxy at the listener Raiker opens for it (or start raiker-web "
    "with --proxy-port or --proxy-socket). An SSH tunnel needs neither."
)
HTTPS_REASON = "remote_https_required"
HTTPS_MESSAGE = (
    "Raiker answers other devices only over HTTPS. Open it at your proxy's https:// address, "
    "and make sure the proxy sends X-Forwarded-Proto: https to Raiker's proxy listener."
)
DISABLED_REASON = "remote_access_disabled"
DISABLED_MESSAGE = (
    "Remote access to this Raiker is turned off. Turn it on again on the computer Raiker runs on, "
    "in Settings → Security → Remote access."
)

ListenerKind = Literal["proxy", "private"]


@dataclass(frozen=True)
class RemoteListener:
    """The listener other devices reach. Everything on it is remote.

    ``kind="proxy"`` is ``127.0.0.1:<port>`` or a Unix socket behind a reverse
    proxy; ``kind="private"`` is a private or VPN address where Raiker serves
    HTTPS itself.
    """

    kind: ListenerKind = "proxy"
    port: int | None = None
    socket_path: str | None = None
    host: str | None = None

    def describe(self) -> str:
        if self.socket_path:
            return f"unix:{self.socket_path}"
        if self.kind == "private":
            host = self.host or ""
            shown = f"[{host}]" if ":" in host else host
            return f"https://{shown}:{self.port}"
        return f"127.0.0.1:{self.port}"

    def accepted(self, scope: Scope) -> bool:
        """Whether this connection arrived on the remote listener."""
        server = scope.get("server")
        if not isinstance(server, (tuple, list)) or len(server) < 2:
            return False
        if self.socket_path is not None:
            return server[1] is None
        if self.port is None or server[1] != self.port:
            return False
        if self.kind == "private" and self.host:
            try:
                return ipaddress.ip_address(str(server[0])) == ipaddress.ip_address(self.host)
            except ValueError:
                return False
        return True


#: Kept for callers written against the first BUG-347 fix.
ProxyListener = RemoteListener


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

    Local means: a loopback peer, over TCP, on the local listener, carrying no
    forwarding header. The remote listener's requests are marked by the guard
    before anything inside it asks.
    """
    return (
        peer_is_loopback(scope)
        and not arrived_without_tcp(scope)
        and not is_forwarded(scope)
        and not scope.get(REMOTE_SCOPE_KEY)
    )


def is_remote_request(scope: Scope) -> bool:
    """Anything that is not provably this computer is another device (BUG-358)."""
    return not is_local_request(scope)


def forwarded_https(scope: Scope) -> bool:
    for name, value in scope.get("headers") or ():
        lowered = name.lower()
        text = value.decode("latin-1").lower()
        if lowered == b"x-forwarded-proto" and text.split(",")[0].strip() == "https":
            return True
        if lowered == b"forwarded" and "proto=https" in text.replace(" ", ""):
            return True
    return False


class RemoteAccessRecord:
    """What the guard has seen since the host started, for Diagnostics and Settings."""

    def __init__(
        self,
        *,
        loopback_only: bool,
        listener: RemoteListener | None,
        source: str = "settings",
    ) -> None:
        self._lock = threading.Lock()
        self.loopback_only = loopback_only
        self.listener = listener
        self.source = source
        self.disabled = False
        self.refused = 0
        self.served = 0
        self.https_refused = 0
        self.https_seen = False
        self.last_refused_at: str | None = None
        self.last_served_at: str | None = None
        self.last_https_refused_at: str | None = None
        self.startup: dict[str, Any] = {}

    def note(self, *, refused: bool) -> None:
        with self._lock:
            if refused:
                self.refused += 1
                self.last_refused_at = utc_now()
            else:
                self.served += 1
                self.last_served_at = utc_now()

    def note_https(self, *, ok: bool) -> None:
        with self._lock:
            if ok:
                self.https_seen = True
            else:
                self.https_refused += 1
                self.last_https_refused_at = utc_now()

    def disable_now(self) -> None:
        """Refuse every request on the remote listener from this moment on."""
        with self._lock:
            self.disabled = True

    def view(self) -> dict[str, Any]:
        with self._lock:
            if not self.loopback_only:
                mode = "public"
            elif self.listener is not None and not self.disabled:
                mode = "proxy_listener" if self.listener.kind == "proxy" else "private_listener"
            else:
                mode = "loopback"
            return {
                "mode": mode,
                "proxy_listener": self.listener.describe() if self.listener is not None else None,
                "listener_kind": self.listener.kind if self.listener is not None else None,
                "listener_source": self.source if self.listener is not None else None,
                "disabled_while_running": self.disabled,
                "https_seen": self.https_seen
                or (self.listener is not None and self.listener.kind == "private"),
                "https_refused": self.https_refused,
                "proxied_requests_refused": self.refused,
                "proxied_requests_served": self.served,
                "last_refused_at": self.last_refused_at,
                "last_served_at": self.last_served_at,
            }


class ProxyGuardMiddleware:
    """Mark the remote listener's requests remote; refuse forwarded ones on the local listener."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        loopback_only: bool,
        record: RemoteAccessRecord,
        listener: RemoteListener | None,
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
            await self._serve_remote(scope, receive, send)
            return
        if not is_forwarded(scope) or not self._loopback_only:
            # A host built without a local-only listener (tests, embedded
            # servers) treats a forwarded request as remote, which
            # `is_local_request` says.
            await self.app(scope, receive, send)
            return
        self._record.note(refused=True)
        await _refuse(scope, send, REFUSAL_REASON, REFUSAL_MESSAGE)

    async def _serve_remote(self, scope: Scope, receive: Receive, send: Send) -> None:
        listener = self._listener
        assert listener is not None
        if self._record.disabled:
            await _refuse(scope, send, DISABLED_REASON, DISABLED_MESSAGE)
            return
        # Remote by the listener it arrived on, headers or not.
        https = scope.get("scheme") in {"https", "wss"} if listener.kind == "private" else forwarded_https(scope)
        if not https and str(scope.get("path") or "") not in HTTPS_EXEMPT_PATHS:
            self._record.note_https(ok=False)
            await _refuse(scope, send, HTTPS_REASON, HTTPS_MESSAGE)
            return
        if https:
            self._record.note_https(ok=True)
        self._record.note(refused=False)
        scope = {**scope, REMOTE_SCOPE_KEY: True, REMOTE_HTTPS_SCOPE_KEY: https}
        if scope["type"] != "http" or not https:
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


async def _refuse(scope: Scope, send: Send, reason: str, message: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    path = str(scope.get("path") or "")
    if path.startswith("/api") or "/api/" in path:
        body = json.dumps(
            {"detail": {"ok": False, "reason_code": reason, "message": message}}
        ).encode("utf-8")
        content_type = b"application/json"
    else:
        body = f"Raiker refused this request.\n\n{message}\n".encode()
        content_type = b"text/plain; charset=utf-8"
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", content_type), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
