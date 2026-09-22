"""Provider connections outlive one call.

GCR-14. ``ModelRouter`` builds a provider for each chat, stream, embed, health
and model-list call and closes it in a ``finally``. Without an injected client
each provider built its own, so closing it threw away the TCP connection and the
TLS session with it: a turn, the readiness probe behind it and the catalogue
refresh beside it each handshook separately with a host Raiker had been talking
to seconds earlier.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.registry import ModelProfileRegistry
from raiker.models.transport import ProviderClientPool

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def run(coro: Any) -> Any:
    """The suite's convention: one event loop per test, started here."""
    return asyncio.run(coro)


@pytest.fixture
def pool() -> ProviderClientPool:
    return ProviderClientPool()


@pytest.fixture(autouse=True)
def _allow_anthropic_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model egress is process configuration, and these tests resolve a host."""
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "api.anthropic.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used-no-request-is-made")


def _hosted_factory(**extra: Any) -> ModelProviderFactory:
    return ModelProviderFactory(policy=_hosted_policy(), **extra)


def _hosted_policy() -> ProviderRuntimePolicy:
    """Every gate open: this suite is about the transport, not the policy."""
    return ProviderRuntimePolicy(
        allow_policy_gated_provider=True,
        allow_hosted_provider=True,
        allow_private_network_provider=True,
        require_api_key_for_hosted=False,
    )


def test_one_client_per_endpoint_and_timeout(pool: ProviderClientPool) -> None:
    async def body() -> None:
        first = pool.client(endpoint="https://api.example/v1", timeout=120.0)
        assert pool.client(endpoint="https://api.example/v1", timeout=120.0) is first
        # A connection is to a host, not to a path: two profiles pointing at
        # different paths of one host share it.
        assert pool.client(endpoint="https://api.example/v1/chat", timeout=120.0) is first
        # A different host, and a different timeout, are different connections.
        assert pool.client(endpoint="https://other.example/v1", timeout=120.0) is not first
        assert pool.client(endpoint="https://api.example/v1", timeout=5.0) is not first
        await pool.aclose()

    run(body())


def test_a_pooled_client_carries_no_credential(pool: ProviderClientPool) -> None:
    """Which is why one client per endpoint is safe, and needs no invalidation.

    Both providers merge their headers — the owner's key included — into each
    request rather than onto the client, so a reused connection is never reused
    *as* an authorization, and a changed connection is a different request
    header on the same socket.
    """

    async def body() -> None:
        client = pool.client(endpoint="https://api.example/v1", timeout=120.0)
        carried = {name.lower() for name in client.headers}
        assert "authorization" not in carried
        assert "x-api-key" not in carried
        await pool.aclose()

    run(body())


def test_closing_releases_this_loops_clients(pool: ProviderClientPool) -> None:
    async def body() -> None:
        client = pool.client(endpoint="https://api.example/v1", timeout=120.0)
        await pool.aclose()
        assert client.is_closed
        # And the next caller gets a working one rather than the closed one.
        assert pool.client(endpoint="https://api.example/v1", timeout=120.0) is not client
        await pool.aclose()

    run(body())


def test_a_client_is_never_handed_across_event_loops(pool: ProviderClientPool) -> None:
    """An httpx client holds connections bound to the loop that made them."""

    async def take() -> httpx.AsyncClient:
        return pool.client(endpoint="https://api.example/v1", timeout=120.0)

    first = run(take())
    assert run(take()) is not first


def test_the_factory_gives_a_provider_the_pooled_client(pool: ProviderClientPool) -> None:
    async def body() -> None:
        profile = ModelProfileRegistry.load().resolve("anthropic", ANTHROPIC_MODEL)
        provider = _hosted_factory(client_pool=pool).create(profile)
        pooled = pool.client(endpoint=provider.endpoint, timeout=provider.timeout)
        assert provider._client is pooled  # noqa: SLF001 — the point of the test
        # And the provider does not own it, so ending one call does not close
        # the connection the next call wants.
        await provider.aclose()
        assert not pooled.is_closed
        await pool.aclose()

    run(body())


def test_a_factory_with_no_pool_behaves_as_before() -> None:
    async def body() -> None:
        profile = ModelProfileRegistry.load().resolve("anthropic", ANTHROPIC_MODEL)
        provider = _hosted_factory().create(profile)
        assert provider._client is not None  # noqa: SLF001 — it opened its own
        await provider.aclose()
        assert provider._client.is_closed  # noqa: SLF001

    run(body())


def test_a_router_shares_one_connection_across_its_calls(pool: ProviderClientPool) -> None:
    """The defect, stated as the thing it cost: five calls, five handshakes."""
    from raiker.models.router import ModelRouter

    async def body() -> None:
        registry = ModelProfileRegistry.load()
        router = ModelRouter(registry, client_pool=pool)
        router.runtime_policy = _hosted_policy()
        profile = registry.resolve("anthropic", ANTHROPIC_MODEL)
        clients = set()
        for _ in range(5):
            provider = router._factory(profile).create(profile)  # noqa: SLF001
            clients.add(id(provider._client))  # noqa: SLF001
            await provider.aclose()
        assert len(clients) == 1
        await pool.aclose()

    run(body())
