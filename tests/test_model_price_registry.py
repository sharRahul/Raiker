"""BUG-21 — the historical price registry, its sync job, and its API surface.

The behaviours worth defending are the ones a naive "current price" column got
wrong: a price is a fact with a date, a poll is not a change, an exact model id
never inherits a sibling's rate, a failed refresh must not erase a real number,
and an administrator override must be attributable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.price_registry import (
    PriceRates,
    PriceRegistry,
    PriceRegistryError,
    rates_from_provider_metadata,
    seed_from_config,
)
from raiker.models.price_sync import (
    DEFAULT_INTERVAL_HOURS,
    MAX_INTERVAL_HOURS,
    MIN_INTERVAL_HOURS,
    PriceSynchroniser,
    clamp_interval_hours,
)
from raiker.models.pricing import ModelPrice
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


class _CatalogueModel:
    def __init__(self, model_id: str, metadata: dict | None) -> None:
        self.id = model_id
        self.metadata = metadata


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def registry(store: SQLiteStore) -> PriceRegistry:
    return PriceRegistry(store)


def _rates(inp: str, out: str, **kwargs: str) -> PriceRates:
    return PriceRates(
        input_per_mtok=Decimal(inp),
        output_per_mtok=Decimal(out),
        cache_write_per_mtok=(
            Decimal(kwargs["cache_write"]) if "cache_write" in kwargs else None
        ),
        cache_read_per_mtok=Decimal(kwargs["cache_read"]) if "cache_read" in kwargs else None,
    )


class TestRegistryHistory:
    def test_a_changed_rate_appends_history_rather_than_overwriting(
        self, registry: PriceRegistry
    ) -> None:
        assert registry.record(
            OWNER, "anthropic", "claude-haiku-4-5", _rates("1", "5"),
            source="config", effective_from="2026-01-01",
        )
        assert registry.record(
            OWNER, "anthropic", "claude-haiku-4-5", _rates("1.10", "5.50"),
            source="config", effective_from="2026-06-01",
        )
        history = registry.history(OWNER, "anthropic", "claude-haiku-4-5")
        assert [row.effective_from for row in history] == ["2026-06-01", "2026-01-01"]
        current = registry.resolve(OWNER, "anthropic", "claude-haiku-4-5")
        assert current is not None
        assert current.rates.input_per_mtok == Decimal("1.10")

    def test_an_unchanged_rate_writes_nothing(self, registry: PriceRegistry) -> None:
        assert registry.record(
            OWNER, "anthropic", "claude-haiku-4-5", _rates("1", "5"), source="config"
        )
        # A synchronisation that confirms the price has not changed the price.
        assert not registry.record(
            OWNER, "anthropic", "claude-haiku-4-5", _rates("1", "5"), source="config"
        )
        assert len(registry.history(OWNER, "anthropic", "claude-haiku-4-5")) == 1

    def test_owner_outranks_provider_outranks_config(self, registry: PriceRegistry) -> None:
        registry.record(OWNER, "anthropic", "m", _rates("1", "5"), source="config")
        assert registry.resolve(OWNER, "anthropic", "m").source == "config"  # type: ignore[union-attr]
        registry.record(OWNER, "anthropic", "m", _rates("2", "6"), source="provider")
        assert registry.resolve(OWNER, "anthropic", "m").source == "provider"  # type: ignore[union-attr]
        registry.record(
            OWNER, "anthropic", "m", _rates("3", "7"), source="owner", recorded_by=OWNER
        )
        resolved = registry.resolve(OWNER, "anthropic", "m")
        assert resolved is not None
        assert resolved.source == "owner" and resolved.rates.input_per_mtok == Decimal("3")

    def test_clearing_an_override_restores_the_underlying_source(
        self, registry: PriceRegistry
    ) -> None:
        registry.record(OWNER, "anthropic", "m", _rates("1", "5"), source="config")
        registry.record(OWNER, "anthropic", "m", _rates("9", "9"), source="owner")
        assert registry.clear_source(OWNER, "anthropic", "m", "owner") == 1
        resolved = registry.resolve(OWNER, "anthropic", "m")
        assert resolved is not None and resolved.source == "config"

    def test_a_sibling_model_never_inherits_a_rate(self, registry: PriceRegistry) -> None:
        registry.record(OWNER, "anthropic", "claude-opus-4-1", _rates("15", "75"), source="config")
        assert registry.resolve(OWNER, "anthropic", "claude-haiku-4-5") is None

    def test_owner_scoping_isolates_registries(self, registry: PriceRegistry) -> None:
        registry.record(OWNER, "anthropic", "m", _rates("1", "5"), source="owner")
        assert registry.resolve("principal_other", "anthropic", "m") is None

    def test_a_negative_rate_is_refused(self, registry: PriceRegistry) -> None:
        with pytest.raises(PriceRegistryError):
            registry.record(OWNER, "anthropic", "m", _rates("-1", "5"), source="owner")

    def test_cache_components_round_trip_independently(self, registry: PriceRegistry) -> None:
        registry.record(
            OWNER, "anthropic", "m",
            _rates("1", "5", cache_write="1.25", cache_read="0.1"),
            source="config",
        )
        resolved = registry.resolve(OWNER, "anthropic", "m")
        assert resolved is not None
        assert resolved.rates.cache_write_per_mtok == Decimal("1.25")
        assert resolved.rates.cache_read_per_mtok == Decimal("0.1")


class TestCostWithCacheComponents:
    def test_cache_tokens_bill_at_their_own_rate_when_known(self) -> None:
        price = ModelPrice(
            input_per_mtok=Decimal("1"),
            output_per_mtok=Decimal("5"),
            currency="USD",
            source="config",
            cache_write_per_mtok=Decimal("1.25"),
            cache_read_per_mtok=Decimal("0.1"),
        )
        cost = price.cost(
            input_tokens=1_000_000,
            output_tokens=0,
            cache_write_tokens=1_000_000,
            cache_read_tokens=1_000_000,
        )
        assert cost == Decimal("2.35")

    def test_an_unknown_cache_rate_falls_back_to_input_rather_than_zero(self) -> None:
        price = ModelPrice(
            input_per_mtok=Decimal("1"),
            output_per_mtok=Decimal("5"),
            currency="USD",
            source="config",
        )
        assert price.cost(
            input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000
        ) == Decimal("1")


class TestProviderMetadataAdapter:
    def test_per_token_prices_are_scaled_to_per_million(self) -> None:
        rates = rates_from_provider_metadata(
            {"pricing": {"prompt": "0.000001", "completion": "0.000005"}}
        )
        assert rates is not None
        assert rates.input_per_mtok == Decimal("1")
        assert rates.output_per_mtok == Decimal("5")

    def test_half_a_price_is_no_price(self) -> None:
        assert rates_from_provider_metadata({"pricing": {"prompt": "0.000001"}}) is None

    def test_a_published_zero_is_kept(self) -> None:
        rates = rates_from_provider_metadata({"pricing": {"prompt": "0", "completion": "0"}})
        assert rates is not None and rates.input_per_mtok == Decimal("0")


class TestDocumentationAdapter:
    def test_only_named_models_are_priced(self, registry: PriceRegistry) -> None:
        written = seed_from_config(
            registry,
            OWNER,
            "anthropic",
            {
                "currency": "USD",
                "as_of": "2026-07",
                "models": {"claude-haiku-4-5": {"input": 1.0, "output": 5.0}},
            },
        )
        assert written == 1
        priced = registry.resolve(OWNER, "anthropic", "claude-haiku-4-5")
        assert priced is not None and priced.as_of == "2026-07"
        assert registry.resolve(OWNER, "anthropic", "claude-sonnet-4-5") is None


class TestSynchronisationCadence:
    def test_the_interval_is_clamped_to_the_validated_window(self) -> None:
        assert clamp_interval_hours(1) == MIN_INTERVAL_HOURS
        assert clamp_interval_hours(240) == MAX_INTERVAL_HOURS
        assert clamp_interval_hours("nonsense") == DEFAULT_INTERVAL_HOURS
        assert clamp_interval_hours(8) == 8

    def test_a_fresh_provider_is_due_and_a_synced_one_is_not(
        self, store: SQLiteStore
    ) -> None:
        synchroniser = PriceSynchroniser(store)
        assert synchroniser.due(OWNER, "openrouter")
        synchroniser.sync_from_catalogue(
            OWNER,
            "openrouter",
            [_CatalogueModel("x/y", {"pricing": {"prompt": "0.000001", "completion": "0.000002"}})],
        )
        assert not synchroniser.due(OWNER, "openrouter")
        state = synchroniser.state(OWNER, "openrouter")
        assert state.models_recorded == 1 and state.last_error is None and not state.stale

    def test_a_failed_refresh_keeps_the_last_good_response_and_says_it_is_stale(
        self, store: SQLiteStore
    ) -> None:
        synchroniser = PriceSynchroniser(store)
        synchroniser.sync_from_catalogue(
            OWNER,
            "openrouter",
            [_CatalogueModel("x/y", {"pricing": {"prompt": "0.000001", "completion": "0.000002"}})],
        )
        synchroniser.record_failure(OWNER, "openrouter", "provider_unreachable")
        state = synchroniser.state(OWNER, "openrouter")
        assert state.last_error == "provider_unreachable"
        assert state.stale
        assert state.has_last_good
        assert state.last_success_at is not None
        # The rate the failed refresh could not confirm is still resolvable.
        assert PriceRegistry(store).resolve(OWNER, "openrouter", "x/y") is not None

    def test_next_refresh_is_within_the_validated_window(self, store: SQLiteStore) -> None:
        synchroniser = PriceSynchroniser(store)
        synchroniser.sync_from_documentation(
            OWNER, "anthropic", {"models": {"m": {"input": 1, "output": 5}}}
        )
        state = synchroniser.state(OWNER, "anthropic")
        assert state.next_refresh_at is not None
        deadline = datetime.fromisoformat(state.next_refresh_at.replace("Z", "+00:00"))
        delta = deadline - datetime.now(UTC)
        assert timedelta(hours=MIN_INTERVAL_HOURS - 1) < delta <= timedelta(
            hours=MAX_INTERVAL_HOURS
        )

    def test_a_catalogue_publishing_no_prices_succeeds_without_recording(
        self, store: SQLiteStore
    ) -> None:
        result = PriceSynchroniser(store).sync_from_catalogue(
            OWNER, "openai", [_CatalogueModel("gpt-x", {"max_input_tokens": 100})]
        )
        assert result.ok and result.models_recorded == 0


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


class TestPricingApi:
    def test_the_pricing_read_states_source_dates_and_components(
        self, client: TestClient
    ) -> None:
        headers = _headers(client)
        body = client.get("/api/models/pricing", headers=headers).json()
        assert "entries" in body and "sync" in body and "can_override" in body
        assert body["entries"], "shipped documentation should populate the registry"
        entry = body["entries"][0]
        assert set(entry) >= {
            "provider", "model", "source", "currency", "input_per_mtok",
            "output_per_mtok", "cache_write_per_mtok", "cache_read_per_mtok",
            "effective_from", "as_of", "reviewed_at", "review_due_at",
            "review_status", "history", "has_owner_override",
        }
        assert entry["source"] in {"owner", "provider", "config"}
        if entry["source"] == "config":
            assert entry["reviewed_at"] == "2026-08-01"
            assert entry["review_due_at"] == "2026-11-01"
            assert entry["review_status"] == "current"

    def test_pricing_requires_a_bearer_token(self, client: TestClient) -> None:
        assert client.get("/api/models/pricing").status_code in (401, 403)

    def test_an_override_is_recorded_with_its_reason_and_shows_in_history(
        self, client: TestClient
    ) -> None:
        headers = _headers(client)
        entry = client.get("/api/models/pricing", headers=headers).json()["entries"][0]
        response = client.put(
            f"/api/models/{entry['profile_id']}/price",
            headers=headers,
            json={
                "model": entry["model"],
                "input_per_mtok": "2.50",
                "output_per_mtok": "9.00",
                "cache_write_per_mtok": "3.125",
                "cache_read_per_mtok": "0.25",
                "reason": "Enterprise agreement rate",
            },
        )
        assert response.status_code == 200, response.text
        after = client.get("/api/models/pricing", headers=headers).json()
        row = next(e for e in after["entries"] if e["model"] == entry["model"])
        assert row["source"] == "owner"
        assert row["input_per_mtok"] == "2.50"
        assert row["cache_read_per_mtok"] == "0.25"
        assert row["has_owner_override"]
        assert any(h["reason"] == "Enterprise agreement rate" for h in row["history"])

    def test_clearing_an_override_returns_the_documented_rate(
        self, client: TestClient
    ) -> None:
        headers = _headers(client)
        entry = client.get("/api/models/pricing", headers=headers).json()["entries"][0]
        client.put(
            f"/api/models/{entry['profile_id']}/price",
            headers=headers,
            json={"model": entry["model"], "input_per_mtok": "2.50", "output_per_mtok": "9.00"},
        )
        cleared = client.put(
            f"/api/models/{entry['profile_id']}/price",
            headers=headers,
            json={"model": entry["model"]},
        )
        assert cleared.status_code == 200, cleared.text
        row = next(
            e
            for e in client.get("/api/models/pricing", headers=headers).json()["entries"]
            if e["model"] == entry["model"]
        )
        assert row["source"] == entry["source"]
        assert row["input_per_mtok"] == entry["input_per_mtok"]

    def test_a_malformed_rate_is_refused_rather_than_guessed(
        self, client: TestClient
    ) -> None:
        headers = _headers(client)
        entry = client.get("/api/models/pricing", headers=headers).json()["entries"][0]
        response = client.put(
            f"/api/models/{entry['profile_id']}/price",
            headers=headers,
            json={"model": entry["model"], "input_per_mtok": "abc", "output_per_mtok": "1"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "model_price_invalid"

    def test_refresh_runs_the_reviewed_adapters(self, client: TestClient) -> None:
        headers = _headers(client)
        response = client.post("/api/models/pricing/refresh", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["ok"]
        assert isinstance(response.json()["providers"], list)
