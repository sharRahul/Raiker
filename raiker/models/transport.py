"""The HTTP connections Raiker keeps open to a model provider.

GCR-14. ``ModelRouter`` builds a provider for each chat, stream, embed, health
and model-list call and closes it in a ``finally``. That is lifecycle-correct —
nothing is left open — but without an injected client each provider constructs
its own :class:`httpx.AsyncClient`, and closing it throws away the connection
pool with it. So every turn, every readiness probe and every catalogue refresh
paid for a fresh TCP connection and a fresh TLS handshake to a host Raiker had
been talking to seconds earlier, and HTTP/2 multiplexing and keep-alive never
applied to anything.

This is the pool that outlives one call. Providers already take an injected
client and already only close the one they own
(``AsyncAnthropicMessagesProvider.__post_init__`` sets ``_owns_client``), so
handing them a pooled client changes nothing about how a request is made.

**Credentials are not part of a connection here.** Both providers merge their
headers — including the owner's key — into each request rather than onto the
client, so one pooled client per endpoint carries no owner's secret and a
connection is never reused *as* an authorization. That is also why a changed
connection needs no invalidation: a new endpoint is a new key, and a new key on
the same endpoint is a different request header on the same socket.

**Addresses (BUG-349).** A direct connection is opened by
:class:`~raiker.models.transport_guard.GuardedNetworkBackend`: the origin's name
is resolved once per new connection, every answer is classified against the
connection's declared class, and the address that passed is the one dialled,
while TLS and the ``Host`` header keep the name. A refused dial raises
``model_dial_refused:<detail>`` before a socket is opened.

**Proxies.** The route is decided by :func:`~raiker.models.transport_guard.proxy_for`
rather than left to httpx's environment reading: a hosted origin honours the
owner's ``HTTPS_PROXY``/``HTTP_PROXY``/``ALL_PROXY``/``NO_PROXY`` — the owner's
environment, which no action, tool or model can set — and a loopback or
private-network origin never uses a proxy. A proxy changes the route, not the
destination, and over HTTPS it carries an end-to-end TLS tunnel it cannot read;
a credential over *plain* HTTP through a proxy is refused
(``model_dial_refused:credential_over_http_proxy``), because there the proxy
reads the key. Redirects are not followed (httpx's default, kept here).

**Credentials only to their origin.** A request that carries a credential
header must be for the origin its client was opened for
(``model_credential_origin_mismatch``), so an adapter that ever builds an
absolute URL to another host fails closed instead of sending the key there.

**Clients belong to the event loop that created them.** An ``httpx.AsyncClient``
holds anyio connections bound to one loop, so the pool is keyed by the running
loop as well as the endpoint. A loop that has gone is a set of clients that can
no longer be used or even closed, and they are dropped rather than handed to a
caller that would fail on them.
"""

from __future__ import annotations

import asyncio
import ssl
from contextlib import suppress
from urllib.parse import urlsplit

import httpcore
import httpx

from raiker.models.exceptions import ProviderPolicyError
from raiker.models.transport_guard import GuardedNetworkBackend, Resolver, dial_refusal, proxy_for

__all__ = [
    "ModelTransport",
    "ProviderClientPool",
    "close_provider_clients",
    "provider_client_pool",
]

#: How many connections one endpoint may hold open, and for how long they may
#: idle. Deliberately small: Raiker is a single-owner product talking to a
#: handful of providers, and the point of the pool is to stop rebuilding one
#: connection, not to hold a fleet of them.
_LIMITS = httpx.Limits(max_connections=8, max_keepalive_connections=4, keepalive_expiry=60.0)


def _origin(endpoint: str) -> str:
    """The scheme and authority a connection is actually made to.

    Two profiles pointing at ``/v1`` and ``/v1/chat`` of one host share a
    connection, because a connection is to a host and not to a path.
    """
    split = urlsplit(endpoint if "//" in endpoint else f"//{endpoint}")
    return f"{split.scheme or 'https'}://{split.netloc}"


#: Request headers that carry a provider credential. ``anthropic-workspace-id``
#: is not one: it names where a key acts.
_CREDENTIAL_HEADERS = ("authorization", "x-api-key", "x-goog-api-key", "api-key")


def _declared_kind(endpoint: str) -> str:
    from raiker.models.endpoint_policy import classify_endpoint

    return classify_endpoint(_origin(endpoint))


def _request_origin(url: httpx.URL) -> str:
    port = url.port or {"http": 80, "https": 443}.get(url.scheme, 0)
    host = url.host.lower().rstrip(".")
    rendered = f"[{host}]" if ":" in host else host
    return f"{url.scheme}://{rendered}:{port}"


class ModelTransport(httpx.AsyncBaseTransport):
    """The one route a model provider's requests take for one origin.

    Direct, through :class:`GuardedNetworkBackend`, unless the owner's
    environment proxies this hosted origin. Either way the two credential rules
    are checked on every request before anything is sent.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        declared_kind: str,
        allow_link_local: bool = False,
        resolver: Resolver | None = None,
        limits: httpx.Limits = _LIMITS,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.origin = _request_origin(httpx.URL(_origin(endpoint)))
        self.declared_kind = declared_kind
        self.proxy = proxy_for(endpoint, declared_kind)
        if self.proxy:
            # The proxy resolves the destination, so there is no address here to
            # pin; the route is the owner's own (D2/D4).
            self._inner = httpx.AsyncHTTPTransport(proxy=self.proxy, limits=limits)
            return
        self._inner = httpx.AsyncHTTPTransport(limits=limits)
        # httpx 0.28 takes no network backend, so its pool is replaced by an
        # identical one that has the guard. `tests/test_model_transport_guard.py`
        # pins this against the httpx/httpcore versions in `uv.lock`: an upgrade
        # that renames `_pool` fails there, not silently in production.
        self._inner._pool = httpcore.AsyncConnectionPool(  # noqa: SLF001
            ssl_context=ssl_context or httpx.create_ssl_context(),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            network_backend=GuardedNetworkBackend(
                declared_kind, allow_link_local=allow_link_local, resolver=resolver
            ),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if any(name in request.headers for name in _CREDENTIAL_HEADERS):
            if _request_origin(request.url) != self.origin:
                raise ProviderPolicyError("model_credential_origin_mismatch")
            if self.proxy and request.url.scheme == "http":
                raise dial_refusal("credential_over_http_proxy")
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class ProviderClientPool:
    """One :class:`httpx.AsyncClient` per event loop, origin, timeout and dial rule."""

    def __init__(self) -> None:
        self._clients: dict[tuple[int, str, float, str, bool], httpx.AsyncClient] = {}
        self._loops: dict[int, asyncio.AbstractEventLoop] = {}

    def client(
        self,
        *,
        endpoint: str,
        timeout: float,
        endpoint_kind: str | None = None,
        allow_link_local: bool = False,
    ) -> httpx.AsyncClient:
        """The client for this endpoint, opening one only when there is none.

        ``endpoint_kind`` is the class the profile was validated as (OpenRouter
        is always hosted); without it the origin's text decides, as before.
        """
        loop = asyncio.get_running_loop()
        self._drop_dead_loops()
        kind = endpoint_kind or _declared_kind(endpoint)
        key = (id(loop), _origin(endpoint), float(timeout), kind, bool(allow_link_local))
        existing = self._clients.get(key)
        if existing is not None and not existing.is_closed:
            return existing
        # No default headers: every provider carries its own per request, so a
        # pooled connection never becomes an authorization. No redirects. The
        # transport decides the route, so httpx reads no proxy, netrc or
        # certificate settings of its own (`trust_env=False`).
        created = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=ModelTransport(
                endpoint, declared_kind=kind, allow_link_local=allow_link_local
            ),
        )
        self._clients[key] = created
        self._loops[id(loop)] = loop
        return created

    def _drop_dead_loops(self) -> None:
        dead = {token for token, loop in self._loops.items() if loop.is_closed()}
        if not dead:
            return
        for key in [key for key in self._clients if key[0] in dead]:
            # Not closed: closing needs the loop the connections belong to, and
            # that loop is gone. Releasing the reference is all that is left.
            self._clients.pop(key, None)
        for token in dead:
            self._loops.pop(token, None)

    async def aclose(self) -> None:
        """Close the clients belonging to the running loop and forget the rest."""
        loop = asyncio.get_running_loop()
        mine = [key for key in self._clients if key[0] == id(loop)]
        for key in mine:
            client = self._clients.pop(key)
            with suppress(Exception):
                await client.aclose()
        self._loops.pop(id(loop), None)
        self._drop_dead_loops()


_POOL = ProviderClientPool()


def provider_client_pool() -> ProviderClientPool:
    """The pool every provider in this process shares."""
    return _POOL


async def close_provider_clients() -> None:
    """Release this loop's provider connections, at host shutdown."""
    await _POOL.aclose()
