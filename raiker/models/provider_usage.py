"""Provider-native and Raiker-observed rolling usage contracts.

Provider responses are reduced immediately to bounded numeric metrics. Raw
payloads, account identifiers, labels, headers, and credentials are never part
of the returned snapshot and therefore cannot enter the cache or API.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from raiker.models.connections import get_model_connection, list_model_connections
from raiker.models.price_registry import PriceRegistry
from raiker.models.pricing import resolve_model_facts
from raiker.models.registry import ModelProfileRegistry
from raiker.runtime.model_facts_store import ModelFactsStore
from raiker.runtime.model_usage import ModelUsageLedger, UsageTotals

MAX_PROVIDER_USAGE_BODY = 1024 * 1024
MAX_PROVIDER_NUMBER = Decimal("1e30")


@dataclass(frozen=True)
class NativeUsageMetric:
    unit: str
    used: Decimal
    limit: Decimal | None
    remaining: Decimal | None
    reset_interval: str | None
    resets_at: str | None
    scope: str
    source: str = "provider"


@dataclass(frozen=True)
class NativeQuotaSnapshot:
    status: str
    metrics: tuple[NativeUsageMetric, ...] = ()
    reason_code: str | None = None
    checked_at: str | None = None
    expires_at: str | None = None


@dataclass(frozen=True)
class ProviderUsageRow:
    profile_id: str
    provider: str
    display_name: str
    observed: UsageTotals
    known_cost: Decimal | None
    cost_currency: str | None
    unpriced_models: tuple[str, ...]
    owner_budget: int | None
    native: NativeQuotaSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "display_name": self.display_name,
            "observed": {
                "input_tokens": self.observed.input_tokens,
                "output_tokens": self.observed.output_tokens,
                "cache_read_tokens": self.observed.cache_read_tokens,
                "cache_write_tokens": self.observed.cache_write_tokens,
                "total_tokens": self.observed.total_tokens,
                "requests": self.observed.requests,
                "turns": self.observed.turns,
                "compactions": self.observed.compactions,
                "known_cost": str(self.known_cost) if self.known_cost is not None else None,
                "cost_currency": self.cost_currency,
                "unpriced_models": list(self.unpriced_models),
                "source": "raiker_ledger",
                "window": "rolling_7_days",
            },
            "owner_budget": self.owner_budget,
            "native": {
                "status": self.native.status,
                "reason_code": self.native.reason_code,
                "checked_at": self.native.checked_at,
                "expires_at": self.native.expires_at,
                "metrics": [
                    {
                        "unit": metric.unit,
                        "used": str(metric.used),
                        "limit": str(metric.limit) if metric.limit is not None else None,
                        "remaining": (
                            str(metric.remaining) if metric.remaining is not None else None
                        ),
                        "reset_interval": metric.reset_interval,
                        "resets_at": metric.resets_at,
                        "scope": metric.scope,
                        "source": metric.source,
                    }
                    for metric in self.native.metrics
                ],
            },
        }


def _checked(now: datetime) -> str:
    return now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0 or parsed > MAX_PROVIDER_NUMBER:
        return None
    return parsed


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Mapping[str, str],
    params: Mapping[str, str | int] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    try:
        async with client.stream("GET", url, headers=headers, params=params) as response:
            if response.status_code >= 400:
                return response.status_code, None
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_PROVIDER_USAGE_BODY:
                    return 413, None
    except (httpx.HTTPError, TimeoutError):
        return 0, None
    try:
        decoded = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 422, None
    return response.status_code, decoded if isinstance(decoded, dict) else None


def _failure(status: int, now: datetime) -> NativeQuotaSnapshot:
    reason = "provider_unreachable" if status == 0 else f"provider_http_{status}"
    return NativeQuotaSnapshot(
        status="unavailable", reason_code=reason, checked_at=_checked(now)
    )


class OpenRouterUsageAdapter:
    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def read(
        self, *, connection: Mapping[str, str], now: datetime
    ) -> NativeQuotaSnapshot:
        key = connection.get("api_key", "").strip()
        if not key:
            return NativeQuotaSnapshot(
                status="not_configured",
                reason_code="api_key_not_configured",
                checked_at=_checked(now),
            )
        status, payload = await _get_json(
            self.client,
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
        )
        if status != 200 or payload is None:
            return _failure(status, now)
        data = payload.get("data")
        if not isinstance(data, dict):
            return _failure(422, now)
        used = _number(data.get("usage_weekly"))
        if used is None:
            return _failure(422, now)
        metric = NativeUsageMetric(
            unit="USD",
            used=used,
            limit=_number(data.get("limit")),
            remaining=_number(data.get("limit_remaining")),
            reset_interval=(
                str(data["limit_reset"]) if data.get("limit_reset") is not None else None
            ),
            resets_at=None,
            scope="api_key",
        )
        return NativeQuotaSnapshot(
            status="available", metrics=(metric,), checked_at=_checked(now)
        )


class OpenAIUsageAdapter:
    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def read(
        self, *, connection: Mapping[str, str], now: datetime
    ) -> NativeQuotaSnapshot:
        key = connection.get("admin_api_key", "").strip()
        if not key:
            return NativeQuotaSnapshot(
                status="not_configured",
                reason_code="admin_api_key_not_configured",
                checked_at=_checked(now),
            )
        end = now.astimezone(UTC).replace(microsecond=0)
        start = end - timedelta(days=7)
        status, payload = await _get_json(
            self.client,
            "https://api.openai.com/v1/organization/usage/completions",
            headers={"Authorization": f"Bearer {key}"},
            params={
                "start_time": int(start.timestamp()),
                "end_time": int(end.timestamp()),
                "bucket_width": "1d",
                "limit": 7,
            },
        )
        if status != 200 or payload is None:
            return _failure(status, now)
        totals = _sum_results(
            payload,
            token_fields=("input_tokens", "cached_input_tokens", "output_tokens"),
            request_fields=("num_model_requests",),
        )
        if totals is None:
            return _failure(422, now)
        return _usage_snapshot(*totals, now=now, scope="organization")


class AnthropicUsageAdapter:
    def __init__(self, *, client: httpx.AsyncClient) -> None:
        self.client = client

    async def read(
        self, *, connection: Mapping[str, str], now: datetime
    ) -> NativeQuotaSnapshot:
        key = connection.get("admin_api_key", "").strip()
        if not key:
            return NativeQuotaSnapshot(
                status="not_configured",
                reason_code="admin_api_key_not_configured",
                checked_at=_checked(now),
            )
        end = now.astimezone(UTC).replace(microsecond=0)
        start = end - timedelta(days=7)
        status, payload = await _get_json(
            self.client,
            "https://api.anthropic.com/v1/organizations/usage_report/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            params={
                "starting_at": start.isoformat().replace("+00:00", "Z"),
                "ending_at": end.isoformat().replace("+00:00", "Z"),
                "bucket_width": "1d",
            },
        )
        if status != 200 or payload is None:
            return _failure(status, now)
        totals = _sum_results(
            payload,
            token_fields=(
                "uncached_input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            ),
            request_fields=("num_requests",),
        )
        if totals is None:
            return _failure(422, now)
        return _usage_snapshot(*totals, now=now, scope="organization")


def _result_rows(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return ()
    rows: list[Mapping[str, Any]] = []
    for bucket in data:
        if not isinstance(bucket, Mapping):
            continue
        results = bucket.get("results")
        if isinstance(results, list):
            rows.extend(item for item in results if isinstance(item, Mapping))
        else:
            rows.append(bucket)
    return rows


def _sum_results(
    payload: Mapping[str, Any], *, token_fields: tuple[str, ...], request_fields: tuple[str, ...]
) -> tuple[Decimal, Decimal] | None:
    rows = tuple(_result_rows(payload))
    if not rows:
        return None
    tokens = Decimal(0)
    requests = Decimal(0)
    for row in rows:
        for field in token_fields:
            value = _number(row.get(field))
            if row.get(field) is not None and value is None:
                return None
            tokens += value or Decimal(0)
        for field in request_fields:
            value = _number(row.get(field))
            if row.get(field) is not None and value is None:
                return None
            requests += value or Decimal(0)
    return tokens, requests


def _usage_snapshot(
    tokens: Decimal, requests: Decimal, *, now: datetime, scope: str
) -> NativeQuotaSnapshot:
    return NativeQuotaSnapshot(
        status="available",
        metrics=(
            NativeUsageMetric(
                unit="tokens",
                used=tokens,
                limit=None,
                remaining=None,
                reset_interval="rolling_7_days",
                resets_at=None,
                scope=scope,
            ),
            NativeUsageMetric(
                unit="requests",
                used=requests,
                limit=None,
                remaining=None,
                reset_interval="rolling_7_days",
                resets_at=None,
                scope=scope,
            ),
        ),
        checked_at=_checked(now),
    )


class ProviderUsageSnapshotStore:
    """Owner-scoped cache of normalized provider metrics only."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def put(
        self, owner_principal_id: str, profile_id: str, snapshot: NativeQuotaSnapshot
    ) -> NativeQuotaSnapshot:
        checked = _parse_time(snapshot.checked_at) or datetime.now(UTC).replace(microsecond=0)
        expires = checked + timedelta(minutes=5)
        stored = NativeQuotaSnapshot(
            status=snapshot.status,
            metrics=snapshot.metrics,
            reason_code=snapshot.reason_code,
            checked_at=_checked(checked),
            expires_at=_checked(expires),
        )
        metrics_json = json.dumps(
            [
                {
                    "unit": metric.unit,
                    "used": str(metric.used),
                    "limit": str(metric.limit) if metric.limit is not None else None,
                    "remaining": (
                        str(metric.remaining) if metric.remaining is not None else None
                    ),
                    "reset_interval": metric.reset_interval,
                    "resets_at": metric.resets_at,
                    "scope": metric.scope,
                    "source": metric.source,
                }
                for metric in snapshot.metrics
            ],
            separators=(",", ":"),
        )
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_usage_snapshots (
                  owner_principal_id, profile_id, status, metrics_json,
                  reason_code, checked_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, profile_id) DO UPDATE SET
                  status = excluded.status,
                  metrics_json = excluded.metrics_json,
                  reason_code = excluded.reason_code,
                  checked_at = excluded.checked_at,
                  expires_at = excluded.expires_at
                """,
                (
                    owner_principal_id,
                    profile_id,
                    stored.status,
                    metrics_json,
                    stored.reason_code,
                    stored.checked_at,
                    stored.expires_at,
                ),
            )
        return stored

    def latest(
        self, owner_principal_id: str, profile_id: str
    ) -> NativeQuotaSnapshot | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT status, metrics_json, reason_code, checked_at, expires_at "
                "FROM provider_usage_snapshots "
                "WHERE owner_principal_id = ? AND profile_id = ?",
                (owner_principal_id, profile_id),
            ).fetchone()
        if row is None:
            return None
        try:
            raw_metrics = json.loads(str(row[1]))
            metrics = tuple(_metric_from_dict(item) for item in raw_metrics)
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            return None
        return NativeQuotaSnapshot(
            status=str(row[0]),
            metrics=metrics,
            reason_code=str(row[2]) if row[2] is not None else None,
            checked_at=str(row[3]),
            expires_at=str(row[4]),
        )


class ProviderUsageService:
    """Combines connected-profile ledger rows with optional provider-native data."""

    def __init__(
        self,
        store: Any,
        *,
        registry: ModelProfileRegistry | None = None,
    ) -> None:
        self.store = store
        self.registry = registry or ModelProfileRegistry.load()
        self.ledger = ModelUsageLedger(store)
        self.snapshots = ProviderUsageSnapshotStore(store)

    def connected_profile_ids(self, principal_id: str) -> set[str]:
        connected = set(list_model_connections(self.store, principal_id))
        ready_local = {
            readiness.key.profile_id
            for readiness in self.store.list_model_readiness(principal_id)
            if readiness.ready
        }
        for profile in self.registry.list_profiles():
            if profile.local_only and profile.profile_id in ready_local:
                connected.add(profile.profile_id)
        return connected

    async def weekly_rows(
        self, principal_id: str, *, now: datetime, refresh_native: bool
    ) -> tuple[ProviderUsageRow, ...]:
        connected = self.connected_profile_ids(principal_id)
        rows: list[ProviderUsageRow] = []
        end = now.astimezone(UTC).replace(microsecond=0)
        start = end - timedelta(days=7)
        for profile in self.registry.list_profiles():
            if profile.profile_id not in connected:
                continue
            if bool(profile.raw.get("test_only") or profile.raw.get("setup_hidden")):
                continue
            model_rows = self.ledger.provider_usage(
                principal_id,
                profile_id=profile.profile_id,
                started_at=_checked(start),
                ended_at=_checked(end),
            )
            observed = self.ledger.weekly_usage(
                principal_id, profile.profile_id, now=end
            )
            known_cost, currency, unpriced = self._known_cost(
                principal_id, profile, model_rows
            )
            native = await self._native(
                principal_id, profile, now=end, refresh=refresh_native
            )
            rows.append(
                ProviderUsageRow(
                    profile_id=profile.profile_id,
                    provider=profile.provider,
                    display_name=str(
                        profile.raw.get("display_name")
                        or profile.provider.replace("-", " ").replace(".", " ").title()
                    ),
                    observed=observed,
                    known_cost=known_cost,
                    cost_currency=currency,
                    unpriced_models=tuple(unpriced),
                    owner_budget=self.ledger.weekly_token_budget(
                        principal_id, profile.profile_id
                    ),
                    native=native,
                )
            )
        return tuple(rows)

    def _known_cost(
        self, principal_id: str, profile: Any, rows: list[Any]
    ) -> tuple[Decimal | None, str | None, list[str]]:
        facts_store = ModelFactsStore(self.store)
        registry = PriceRegistry(self.store)
        total = Decimal(0)
        currency: str | None = None
        priced = False
        unpriced: list[str] = []
        for row in rows:
            registered = registry.resolve(principal_id, profile.provider, row.model)
            owner_price = facts_store.owner_price(principal_id, profile.provider, row.model)
            if registered is not None:
                owner_price = registered.rates.to_price(
                    registered.source, registered.as_of
                )
            facts = resolve_model_facts(
                provider=profile.provider,
                model=row.model,
                owner_price=owner_price,
                provider_facts=facts_store.provider_facts(
                    principal_id, profile.provider, row.model
                ),
                config_pricing=profile.raw.get("pricing"),
            )
            cost = row.totals.cost(facts)
            if cost is None:
                unpriced.append(row.model)
                continue
            priced = True
            total += cost
            if facts.price is not None:
                currency = facts.price.currency
        return (total if priced else None), currency, sorted(set(unpriced))

    async def _native(
        self, principal_id: str, profile: Any, *, now: datetime, refresh: bool
    ) -> NativeQuotaSnapshot:
        cached = self.snapshots.latest(principal_id, profile.profile_id)
        if not refresh and cached is not None:
            expires = _parse_time(cached.expires_at)
            if expires is not None and expires >= now:
                return cached
        if not refresh:
            return NativeQuotaSnapshot(
                status="not_checked", reason_code="refresh_required"
            )

        connection = get_model_connection(self.store, principal_id, profile.profile_id) or {}
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if profile.provider == "openrouter":
                snapshot = await OpenRouterUsageAdapter(client=client).read(
                    connection=connection, now=now
                )
            elif profile.provider == "openai":
                snapshot = await OpenAIUsageAdapter(client=client).read(
                    connection=connection, now=now
                )
            elif profile.provider == "anthropic":
                snapshot = await AnthropicUsageAdapter(client=client).read(
                    connection=connection, now=now
                )
            else:
                snapshot = NativeQuotaSnapshot(
                    status="not_supported",
                    reason_code="provider_quota_api_not_supported",
                    checked_at=_checked(now),
                )
        return self.snapshots.put(principal_id, profile.profile_id, snapshot)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _metric_from_dict(raw: Mapping[str, Any]) -> NativeUsageMetric:
    used = _number(raw.get("used"))
    if used is None:
        raise ValueError("invalid_cached_provider_usage")
    limit = _number(raw.get("limit"))
    remaining = _number(raw.get("remaining"))
    return NativeUsageMetric(
        unit=str(raw["unit"]),
        used=used,
        limit=limit,
        remaining=remaining,
        reset_interval=(
            str(raw["reset_interval"]) if raw.get("reset_interval") is not None else None
        ),
        resets_at=str(raw["resets_at"]) if raw.get("resets_at") is not None else None,
        scope=str(raw["scope"]),
        source="provider",
    )
