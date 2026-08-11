from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from raiker.models.provider_usage import (
    AnthropicUsageAdapter,
    NativeQuotaSnapshot,
    NativeUsageMetric,
    OpenAIUsageAdapter,
    OpenRouterUsageAdapter,
    ProviderUsageSnapshotStore,
)
from raiker.storage.sqlite import SQLiteStore

NOW = datetime(2026, 8, 11, 12, tzinfo=UTC)


def _client(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_openrouter_normal_key_reports_weekly_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://openrouter.ai/api/v1/key"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "data": {
                    "usage_weekly": 25.5,
                    "limit": 100,
                    "limit_remaining": 74.5,
                    "limit_reset": "weekly",
                }
            },
        )

    async def scenario():  # type: ignore[no-untyped-def]
        async with _client(handler) as client:
            return await OpenRouterUsageAdapter(client=client).read(
                connection={"api_key": "test-key"}, now=NOW
            )

    snapshot = asyncio.run(scenario())
    assert snapshot.metrics == (
        NativeUsageMetric(
            unit="USD",
            used=Decimal("25.5"),
            limit=Decimal("100"),
            remaining=Decimal("74.5"),
            reset_interval="weekly",
            resets_at=None,
            scope="api_key",
            source="provider",
        ),
    )


def test_openai_admin_usage_aggregates_tokens_and_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/organization/usage/completions"
        assert request.headers["authorization"] == "Bearer admin-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"results": [{"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 5, "num_model_requests": 2}]},
                    {"results": [{"input_tokens": 20, "cached_input_tokens": 7, "output_tokens": 8, "num_model_requests": 4}]},
                ]
            },
        )

    async def scenario():  # type: ignore[no-untyped-def]
        async with _client(handler) as client:
            return await OpenAIUsageAdapter(client=client).read(
                connection={"admin_api_key": "admin-key"}, now=NOW
            )

    snapshot = asyncio.run(scenario())
    assert [(metric.unit, metric.used) for metric in snapshot.metrics] == [
        ("tokens", Decimal("53")),
        ("requests", Decimal("6")),
    ]


def test_anthropic_admin_usage_aggregates_daily_buckets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/organizations/usage_report/messages"
        assert request.headers["x-api-key"] == "admin-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "results": [
                            {
                                "uncached_input_tokens": 11,
                                "cache_creation_input_tokens": 2,
                                "cache_read_input_tokens": 3,
                                "output_tokens": 5,
                                "num_requests": 4,
                            }
                        ]
                    }
                ]
            },
        )

    async def scenario():  # type: ignore[no-untyped-def]
        async with _client(handler) as client:
            return await AnthropicUsageAdapter(client=client).read(
                connection={"admin_api_key": "admin-key"}, now=NOW
            )

    snapshot = asyncio.run(scenario())
    assert [(metric.unit, metric.used) for metric in snapshot.metrics] == [
        ("tokens", Decimal("21")),
        ("requests", Decimal("4")),
    ]


@pytest.mark.parametrize("status", [401, 403, 500])
def test_native_usage_failures_are_bounded_and_do_not_escape(status: int) -> None:
    async def scenario():  # type: ignore[no-untyped-def]
        async with _client(
            lambda _request: httpx.Response(status, json={"secret": "sk-test"})
        ) as client:
            return await OpenRouterUsageAdapter(client=client).read(
                connection={"api_key": "test-key"}, now=NOW
            )

    snapshot = asyncio.run(scenario())
    assert snapshot.metrics == ()
    assert snapshot.status == "unavailable"
    assert snapshot.reason_code == f"provider_http_{status}"


def test_snapshot_cache_is_owner_scoped_and_stores_only_normalized_metrics(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    store.bootstrap()
    snapshots = ProviderUsageSnapshotStore(store)
    original = NativeQuotaSnapshot(
        status="available",
        metrics=(
            NativeUsageMetric(
                unit="USD",
                used=Decimal("1.25"),
                limit=None,
                remaining=None,
                reset_interval="weekly",
                resets_at=None,
                scope="api_key",
            ),
        ),
        checked_at="2026-08-11T12:00:00Z",
    )
    stored = snapshots.put("p1", "openrouter-policy-gated", original)
    assert stored.expires_at == "2026-08-11T12:05:00Z"
    assert snapshots.latest("p1", "openrouter-policy-gated") == stored
    assert snapshots.latest("p2", "openrouter-policy-gated") is None

    with store.connect() as connection:
        raw = connection.execute(
            "SELECT metrics_json FROM provider_usage_snapshots"
        ).fetchone()[0]
    assert "1.25" in raw
    assert "api_key" in raw
    assert "sk-" not in raw
