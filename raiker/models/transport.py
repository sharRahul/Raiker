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

**Clients belong to the event loop that created them.** An ``httpx.AsyncClient``
holds anyio connections bound to one loop, so the pool is keyed by the running
loop as well as the endpoint. A loop that has gone is a set of clients that can
no longer be used or even closed, and they are dropped rather than handed to a
caller that would fail on them.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit

import httpx

__all__ = ["ProviderClientPool", "close_provider_clients", "provider_client_pool"]

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


class ProviderClientPool:
    """One :class:`httpx.AsyncClient` per event loop, origin and timeout."""

    def __init__(self) -> None:
        self._clients: dict[tuple[int, str, float], httpx.AsyncClient] = {}
        self._loops: dict[int, asyncio.AbstractEventLoop] = {}

    def client(self, *, endpoint: str, timeout: float) -> httpx.AsyncClient:
        """The client for this endpoint, opening one only when there is none."""
        loop = asyncio.get_running_loop()
        self._drop_dead_loops()
        key = (id(loop), _origin(endpoint), float(timeout))
        existing = self._clients.get(key)
        if existing is not None and not existing.is_closed:
            return existing
        # No default headers: every provider carries its own per request, so a
        # pooled connection never becomes an authorization.
        created = httpx.AsyncClient(timeout=timeout, limits=_LIMITS)
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
