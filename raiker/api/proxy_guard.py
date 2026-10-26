"""BUG-347 — a reverse proxy in front of a loopback-bound Raiker.

``raiker-web`` decides what is *local* from the socket peer. A reverse proxy on
the same machine (Caddy, nginx) that forwards to ``127.0.0.1`` is itself that
peer, so without this guard every request from the internet would arrive as a
local one: password recovery reachable from anywhere, reads exempt from the
abuse window, and none of the public-bind guardrails in force.

Owner's decision (2026-10-26): **refuse by default, trust a named proxy on
request.**

* A request that carries any forwarding header (``Forwarded``,
  ``X-Forwarded-For``, ``X-Forwarded-Host``, ``X-Forwarded-Proto``,
  ``X-Real-IP``) is **never local**, whatever its socket peer says.
* On a loopback-only host it is **refused** (``proxied_request_refused``) with
  a reason that names the two ways to run behind a proxy, unless the socket
  peer is a proxy the owner named in ``RAIKER_TRUSTED_PROXY``.
* A request from a **trusted proxy** is served under the public posture:
  remote for every local-only check (recovery, instances, the loopback rate
  exemption), rate limited, and answered with HSTS when the proxy says the
  browser reached it over HTTPS. Trusting a proxy requires the hardened owner
  token (``RAIKER_OWNER_TOKEN``), exactly as ``--allow-public`` does; the host
  refuses to start otherwise.

Forwarding headers still identify nothing: the client address a proxy reports
is not used as an identity or a rate-limit key. They only ever make a request
*less* trusted.

What the guard saw is kept on the app (``remote_access``) so Diagnostics can
name a proxied host as public and say what to change.
"""

from __future__ import annotations

import ipaddress
import json
import os
import threading
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.contracts.ids import utc_now

TRUSTED_PROXY_ENV = "RAIKER_TRUSTED_PROXY"

#: Headers a reverse proxy adds. Any one of them marks a request as forwarded.
FORWARDING_HEADERS = frozenset(
    {b"forwarded", b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto", b"x-real-ip"}
)

#: The scope key the guard sets on a request a trusted proxy forwarded.
PROXIED_SCOPE_KEY = "raiker.proxied"

REFUSAL_REASON = "proxied_request_refused"
REFUSAL_MESSAGE = (
    "Raiker is bound to this computer only, and this request came through a reverse proxy, "
    "so it was refused. To reach Raiker through a proxy, either name the proxy's address in "
    "RAIKER_TRUSTED_PROXY (with RAIKER_OWNER_TOKEN set), or bind Raiker to a private address "
    "with --allow-public and point the proxy there. An SSH tunnel needs neither."
)

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class ProxyConfigError(ValueError):
    pass


def trusted_proxies(raw: str | None = None) -> tuple[Network, ...]:
    """The proxies the owner named, as networks. An entry that is not an address refuses."""
    value = os.environ.get(TRUSTED_PROXY_ENV, "") if raw is None else raw
    networks: list[Network] = []
    for entry in (part.strip() for part in value.replace(";", ",").split(",")):
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            raise ProxyConfigError(f"{TRUSTED_PROXY_ENV} entry is not an address: {entry!r}") from None
    return tuple(networks)


def is_forwarded(scope: Scope) -> bool:
    """True when any forwarding header is present on the request."""
    return any(name.lower() in FORWARDING_HEADERS for name, _value in scope.get("headers") or ())


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
    """The one answer every local-only check uses: a loopback peer, and not forwarded."""
    return peer_is_loopback(scope) and not is_forwarded(scope) and not scope.get(PROXIED_SCOPE_KEY)


def _peer_trusted(scope: Scope, networks: tuple[Network, ...]) -> bool:
    client = scope.get("client")
    if not networks or not isinstance(client, (tuple, list)) or not client:
        return False
    host = str(client[0])
    if host in {"localhost", "testclient"}:
        host = "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in networks)


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

    def __init__(self, *, loopback_only: bool, networks: tuple[Network, ...]) -> None:
        self._lock = threading.Lock()
        self.loopback_only = loopback_only
        self.trusted = tuple(str(network) for network in networks)
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
            elif self.trusted:
                mode = "trusted_proxy"
            else:
                mode = "loopback"
            return {
                "mode": mode,
                "trusted_proxies": list(self.trusted),
                "proxied_requests_refused": self.refused,
                "proxied_requests_served": self.served,
                "last_refused_at": self.last_refused_at,
                "last_served_at": self.last_served_at,
            }


class ProxyGuardMiddleware:
    """Refuse, or mark as remote, every forwarded request on a loopback-only host."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        loopback_only: bool,
        record: RemoteAccessRecord,
        networks: tuple[Network, ...],
    ) -> None:
        self.app = app
        self._loopback_only = loopback_only
        self._record = record
        self._networks = networks

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"} or not is_forwarded(scope):
            await self.app(scope, receive, send)
            return
        if not self._loopback_only:
            # A public bind already runs under the public posture; a forwarded
            # request there is simply remote, which `is_local_request` says.
            await self.app(scope, receive, send)
            return
        if not _peer_trusted(scope, self._networks):
            self._record.note(refused=True)
            await _refuse(scope, send)
            return
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
