"""Token accounting and API cost resolution.

Covers the three price sources and their precedence, the per-turn ledger, and
the rule that matters most: a figure Raiker cannot source is reported as absent,
never as zero. "$0.00" must always mean "this was free".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.control.dashboard import DashboardService
from raiker.models.pricing import (
    ModelFacts,
    ModelPrice,
    facts_from_provider_metadata,
    price_from_config,
    resolve_model_facts,
)
from raiker.runtime.model_usage import ModelUsageLedger, UsageTotals, sum_totals
from raiker.storage.sqlite import SQLiteStore

CONFIG_PRICING = {
    "currency": "USD",
    "unit": "per_million_tokens",
    "as_of": "2026-07",
    "models": {"claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0}},
}


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    created = SQLiteStore(tmp_path)
    created.bootstrap()
    return created


class TestPriceResolution:
    def test_config_price_is_read_per_model(self) -> None:
        price = price_from_config(CONFIG_PRICING, "claude-haiku-4-5-20251001")
        assert price is not None
        assert price.input_per_mtok == Decimal("1.0")
        assert price.source == "config"
        assert price.as_of == "2026-07"

    def test_a_model_absent_from_the_table_is_unpriced_not_defaulted(self) -> None:
        # Sibling Claude models differ by ~15x, so borrowing a neighbour's rate
        # would be worse than admitting the price is unknown.
        assert price_from_config(CONFIG_PRICING, "claude-opus-5") is None

    def test_anthropic_metadata_yields_capacity_but_no_price(self) -> None:
        facts = facts_from_provider_metadata(
            "anthropic", "claude-opus-5", {"max_input_tokens": 1_000_000, "max_tokens": 128_000}
        )
        assert facts.context_window_tokens == 1_000_000
        assert facts.context_window_source == "provider"
        assert facts.price is None

    def test_openrouter_metadata_scales_per_token_prices_to_per_million(self) -> None:
        facts = facts_from_provider_metadata(
            "openrouter",
            "some/model",
            {"context_length": 200_000, "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        )
        assert facts.context_window_tokens == 200_000
        assert facts.price is not None
        assert facts.price.input_per_mtok == Decimal("3.000000")
        assert facts.price.output_per_mtok == Decimal("15.000000")
        assert facts.price.source == "provider"

    def test_a_provider_publishing_nothing_yields_empty_facts(self) -> None:
        facts = facts_from_provider_metadata("openai", "gpt-4o", {})
        assert facts.context_window_tokens is None
        assert facts.price is None

    def test_owner_price_outranks_provider_and_config(self) -> None:
        owner = ModelPrice(
            input_per_mtok=Decimal("0.5"),
            output_per_mtok=Decimal("2"),
            currency="USD",
            source="owner",
        )
        facts = resolve_model_facts(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            owner_price=owner,
            provider_facts=facts_from_provider_metadata(
                "anthropic", "claude-haiku-4-5-20251001", {"max_input_tokens": 200_000}
            ),
            config_pricing=CONFIG_PRICING,
        )
        assert facts.price is not None
        assert facts.price.source == "owner"
        # Capacity and price resolve independently, from different sources.
        assert facts.context_window_source == "provider"

    def test_provider_capacity_beats_configured_capacity(self) -> None:
        facts = resolve_model_facts(
            provider="anthropic",
            model="claude-opus-5",
            provider_facts=facts_from_provider_metadata(
                "anthropic", "claude-opus-5", {"max_input_tokens": 1_000_000}
            ),
            config_context_window=200_000,
        )
        assert facts.context_window_tokens == 1_000_000
        assert facts.context_window_source == "provider"

    def test_config_capacity_is_the_fallback_before_a_catalogue_fetch(self) -> None:
        facts = resolve_model_facts(
            provider="anthropic", model="claude-opus-5", config_context_window=200_000
        )
        assert facts.context_window_tokens == 200_000
        assert facts.context_window_source == "config"


class TestCost:
    def test_remote_keyed_profile_is_billable_without_a_cached_endpoint_kind(self) -> None:
        # Shipped profiles classify their endpoint at connection time. The
        # dashboard must still distinguish a remote API-key provider from a
        # local runtime before that transient field is present.
        profile = SimpleNamespace(
            raw={"requires_api_key": True, "api_key_env": "ANTHROPIC_API_KEY"},
            local_only=False,
            requires_network=True,
        )

        assert DashboardService._profile_is_billable(profile)

    def test_local_runtime_with_a_token_stays_non_billable(self) -> None:
        profile = SimpleNamespace(
            raw={"api_key_env": "LM_API_TOKEN"},
            local_only=True,
            requires_network=False,
        )

        assert not DashboardService._profile_is_billable(profile)

    def test_cost_uses_the_per_million_convention(self) -> None:
        price = price_from_config(CONFIG_PRICING, "claude-haiku-4-5-20251001")
        assert price is not None
        # 1M in at $1 + 1M out at $5 = $6.
        assert price.cost(input_tokens=1_000_000, output_tokens=1_000_000) == Decimal("6")

    def test_an_unpriced_model_reports_no_cost_rather_than_zero(self) -> None:
        totals = UsageTotals(input_tokens=5_000, output_tokens=500)
        unpriced = resolve_model_facts(provider="anthropic", model="claude-opus-5")
        assert totals.cost(unpriced) is None
        assert totals.cost(None) is None


class TestLedger:
    def test_a_turn_is_recorded_and_aggregated_by_model(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        assert ledger.record(
            owner_principal_id="p1",
            session_id="sess_1",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            usage={"input_tokens": 1_200, "output_tokens": 300},
        )
        assert ledger.record(
            owner_principal_id="p1",
            session_id="sess_1",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            usage={"input_tokens": 800, "output_tokens": 200},
        )
        rows = ledger.session_usage("p1", "sess_1")
        assert len(rows) == 1
        assert rows[0].totals.input_tokens == 2_000
        assert rows[0].totals.output_tokens == 500
        assert rows[0].totals.turns == 2

    def test_a_turn_with_no_reported_usage_writes_no_row(self, store: SQLiteStore) -> None:
        # A missing count must not become a zero that later reads call "free".
        ledger = ModelUsageLedger(store)
        assert not ledger.record(
            owner_principal_id="p1", session_id="s", provider="anthropic", model="m", usage={}
        )
        assert not ledger.record(
            owner_principal_id="p1", session_id="s", provider="anthropic", model="m", usage=None
        )
        assert ledger.session_usage("p1", "s") == []

    def test_usage_is_scoped_to_its_owner(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        ledger.record(
            owner_principal_id="p1",
            session_id="sess_1",
            provider="anthropic",
            model="m",
            usage={"input_tokens": 10, "output_tokens": 1},
        )
        assert ledger.provider_usage("p1") != []
        assert ledger.provider_usage("p2") == []

    def test_provider_totals_span_sessions_and_models(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        for session, model in (("s1", "haiku"), ("s2", "haiku"), ("s2", "opus")):
            ledger.record(
                owner_principal_id="p1",
                session_id=session,
                provider="anthropic",
                model=model,
                usage={"input_tokens": 100, "output_tokens": 10},
            )
        rows = ledger.provider_usage("p1")
        assert {row.model for row in rows} == {"haiku", "opus"}
        assert sum_totals(rows).input_tokens == 300
        assert sum_totals(rows).turns == 3

    def test_weekly_usage_is_profile_scoped_and_excludes_older_rows(
        self, store: SQLiteStore
    ) -> None:
        ledger = ModelUsageLedger(store)
        common = {
            "owner_principal_id": "p1",
            "session_id": "s1",
            "provider": "openai",
            "model": "gpt-5",
        }
        assert ledger.record(
            **common,
            profile_id="openai-hosted",
            recorded_at="2026-08-10T12:00:00+00:00",
            usage={"input_tokens": 80},
        )
        assert ledger.record(
            **common,
            profile_id="openai-hosted",
            recorded_at="2026-08-04T12:00:00+00:00",
            usage={"input_tokens": 20},
        )
        assert ledger.record(
            **common,
            profile_id="openai-hosted",
            recorded_at="2026-08-03T12:00:00+00:00",
            usage={"input_tokens": 900},
        )
        assert ledger.record(
            **common,
            profile_id="openai-compatible",
            recorded_at="2026-08-10T12:00:00+00:00",
            usage={"input_tokens": 40},
        )

        totals = ledger.weekly_usage(
            "p1",
            "openai-hosted",
            now=datetime(2026, 8, 11, 12, tzinfo=UTC),
        )
        assert totals.input_tokens == 100
        assert totals.requests == 2
        assert totals.turns == 2
        assert totals.compactions == 0

    def test_compaction_counts_as_usage_but_not_as_a_user_turn(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        common = {
            "owner_principal_id": "p1",
            "session_id": "s1",
            "provider": "anthropic",
            "model": "claude-sonnet-4-5",
            "profile_id": "anthropic-hosted",
            "recorded_at": "2026-08-10T12:00:00+00:00",
        }
        ledger.record(**common, request_kind="turn", usage={"input_tokens": 30})
        ledger.record(**common, request_kind="compaction", usage={"input_tokens": 70})
        totals = ledger.weekly_usage(
            "p1",
            "anthropic-hosted",
            now=datetime(2026, 8, 11, 12, tzinfo=UTC),
        )
        assert totals.input_tokens == 100
        assert totals.requests == 2
        assert totals.turns == 1
        assert totals.compactions == 1

    def test_weekly_budget_can_be_set_updated_cleared_and_is_owner_scoped(
        self, store: SQLiteStore
    ) -> None:
        ledger = ModelUsageLedger(store)
        ledger.set_weekly_token_budget("p1", "openai-hosted", 100_000)
        assert ledger.weekly_token_budget("p1", "openai-hosted") == 100_000
        assert ledger.weekly_token_budget("p2", "openai-hosted") is None

        ledger.set_weekly_token_budget("p1", "openai-hosted", 250_000)
        assert ledger.weekly_token_budget("p1", "openai-hosted") == 250_000

        ledger.set_weekly_token_budget("p1", "openai-hosted", None)
        assert ledger.weekly_token_budget("p1", "openai-hosted") is None

        with pytest.raises(ValueError, match="weekly_token_budget_must_be_positive"):
            ledger.set_weekly_token_budget("p1", "openai-hosted", 0)

    def test_rejects_unknown_request_kinds(self, store: SQLiteStore) -> None:
        with pytest.raises(ValueError, match="invalid_model_usage_request_kind"):
            ModelUsageLedger(store).record(
                owner_principal_id="p1",
                session_id="s1",
                provider="openai",
                model="gpt-5",
                profile_id="openai-hosted",
                request_kind="background",
                usage={"input_tokens": 1},
            )


class TestMixedModelPricing:
    """A provider total must price each model at its own rate.

    Found live: summing every token first and applying the *currently selected*
    model's price charged cheap-model history at the expensive model's rate.
    Claude models differ by roughly 15x, so a mixed history was badly wrong.
    """

    CHEAP = {"models": {"cheap": {"input": 1.0, "output": 5.0}}, "currency": "USD"}
    DEAR = {"models": {"dear": {"input": 15.0, "output": 75.0}}, "currency": "USD"}

    def _facts(self, model: str) -> ModelFacts:
        pricing = self.CHEAP if model == "cheap" else self.DEAR
        return resolve_model_facts(provider="anthropic", model=model, config_pricing=pricing)

    def test_each_model_is_priced_at_its_own_rate(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        for model in ("cheap", "dear"):
            ledger.record(
                owner_principal_id="p1",
                session_id="s1",
                provider="anthropic",
                model=model,
                usage={"input_tokens": 1_000_000, "output_tokens": 0},
            )
        rows = ledger.provider_usage("p1")

        per_model = sum(
            (row.totals.cost(self._facts(row.model)) or Decimal(0)) for row in rows
        )
        # 1M at $1 + 1M at $15 = $16.
        assert per_model == Decimal("16")

        # The bug: sum tokens first, then apply one model's rate.
        blended = sum_totals(rows).cost(self._facts("dear"))
        assert blended == Decimal("30")
        assert blended != per_model

    def test_an_unpriced_model_is_skipped_not_counted_as_free(self, store: SQLiteStore) -> None:
        ledger = ModelUsageLedger(store)
        ledger.record(
            owner_principal_id="p1",
            session_id="s1",
            provider="anthropic",
            model="cheap",
            usage={"input_tokens": 1_000_000, "output_tokens": 0},
        )
        ledger.record(
            owner_principal_id="p1",
            session_id="s1",
            provider="anthropic",
            model="unknown-model",
            usage={"input_tokens": 1_000_000, "output_tokens": 0},
        )
        rows = ledger.provider_usage("p1")
        priced = [
            row.totals.cost(self._facts(row.model))
            for row in rows
            if row.totals.cost(self._facts(row.model)) is not None
        ]
        # The unpriced model contributes nothing rather than a zero-cost row.
        assert priced == [Decimal("1")]
