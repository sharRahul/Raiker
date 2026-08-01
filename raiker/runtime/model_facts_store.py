"""Cache of provider-published model facts, and owner price overrides.

Provider catalogues cost a network round trip and change rarely, so what a
provider publishes about its models is cached per owner and refreshed on demand.
Owner overrides live in the same table under a different ``source`` so one read
answers "what do we know about this model, and who told us".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.models.pricing import ModelFacts, ModelPrice, facts_from_provider_metadata


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — a corrupt cached price is simply unknown
        return None


class ModelFactsStore:
    """Owner-scoped persistence for provider-reported facts and owner prices."""

    def __init__(self, store: Any) -> None:
        self.store = store

    # ── provider-reported facts ─────────────────────────────────────────

    def save_provider_facts(
        self, owner_principal_id: str, provider: str, models: list[Any]
    ) -> int:
        """Cache what a catalogue listing told us. Returns the row count written.

        Models the provider published nothing useful about are skipped rather
        than stored as a row of nulls, so a later read can tell "not fetched"
        from "fetched, provider says nothing".
        """
        if not owner_principal_id:
            return 0
        written = 0
        now = utc_now()
        with self.store.connect() as connection:
            for info in models:
                model_id = getattr(info, "id", None)
                if not isinstance(model_id, str) or not model_id:
                    continue
                facts = facts_from_provider_metadata(
                    provider, model_id, getattr(info, "metadata", None)
                )
                if facts.context_window_tokens is None and facts.price is None:
                    continue
                connection.execute(
                    """
                    INSERT INTO model_facts_cache (
                      owner_principal_id, provider, model, source,
                      context_window_tokens, max_output_tokens,
                      input_price_per_mtok, output_price_per_mtok, currency, fetched_at
                    ) VALUES (?, ?, ?, 'provider', ?, NULL, ?, ?, ?, ?)
                    ON CONFLICT(owner_principal_id, provider, model, source) DO UPDATE SET
                      context_window_tokens = excluded.context_window_tokens,
                      input_price_per_mtok = excluded.input_price_per_mtok,
                      output_price_per_mtok = excluded.output_price_per_mtok,
                      currency = excluded.currency,
                      fetched_at = excluded.fetched_at
                    """,
                    (
                        owner_principal_id,
                        provider,
                        model_id,
                        facts.context_window_tokens,
                        str(facts.price.input_per_mtok) if facts.price else None,
                        str(facts.price.output_per_mtok) if facts.price else None,
                        facts.price.currency if facts.price else None,
                        now,
                    ),
                )
                written += 1
        return written

    def provider_facts(
        self, owner_principal_id: str, provider: str, model: str
    ) -> ModelFacts | None:
        return self._read(owner_principal_id, provider, model, "provider")

    def owner_price(
        self, owner_principal_id: str, provider: str, model: str
    ) -> ModelPrice | None:
        facts = self._read(owner_principal_id, provider, model, "owner")
        return facts.price if facts else None

    def owner_context_capacity(
        self, owner_principal_id: str, provider: str, model: str
    ) -> tuple[int, str] | None:
        with self.store.connect() as connection:
            row = connection.execute(
                """SELECT context_window_tokens, fetched_at FROM model_facts_cache
                WHERE owner_principal_id = ? AND provider = ? AND model = ? AND source = 'owner'""",
                (owner_principal_id, provider, model),
            ).fetchone()
        if row is None or row["context_window_tokens"] is None:
            return None
        return int(row["context_window_tokens"]), str(row["fetched_at"])

    def set_owner_context_capacity(
        self,
        owner_principal_id: str,
        provider: str,
        model: str,
        *,
        tokens: int | None,
        endpoint_identity: str,
        reason: str,
        recorded_by: str,
    ) -> None:
        if tokens is not None and (isinstance(tokens, bool) or tokens < 1024 or tokens > 100_000_000):
            raise ValueError("model_context_capacity_invalid")
        now = utc_now()
        with self.store.connect() as connection:
            if tokens is None:
                connection.execute(
                    """UPDATE model_facts_cache SET context_window_tokens = NULL, fetched_at = ?
                    WHERE owner_principal_id = ? AND provider = ? AND model = ? AND source = 'owner'""",
                    (now, owner_principal_id, provider, model),
                )
            else:
                connection.execute(
                    """INSERT INTO model_facts_cache (
                      owner_principal_id, provider, model, source, context_window_tokens,
                      max_output_tokens, input_price_per_mtok, output_price_per_mtok, currency, fetched_at
                    ) VALUES (?, ?, ?, 'owner', ?, NULL, NULL, NULL, NULL, ?)
                    ON CONFLICT(owner_principal_id, provider, model, source) DO UPDATE SET
                      context_window_tokens = excluded.context_window_tokens,
                      fetched_at = excluded.fetched_at""",
                    (owner_principal_id, provider, model, tokens, now),
                )
            connection.execute(
                "INSERT INTO model_capacity_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id("mcap_"), owner_principal_id, provider, model,
                    endpoint_identity, tokens, "cleared" if tokens is None else "set",
                    reason, recorded_by, now,
                ),
            )

    def capacity_history(
        self, owner_principal_id: str, provider: str, model: str
    ) -> list[dict[str, Any]]:
        with self.store.connect() as connection:
            rows = connection.execute(
                """SELECT capacity_id, endpoint_identity, context_window_tokens, action,
                reason, recorded_by, recorded_at FROM model_capacity_history
                WHERE owner_principal_id = ? AND provider = ? AND model = ?
                ORDER BY recorded_at DESC, capacity_id DESC""",
                (owner_principal_id, provider, model),
            ).fetchall()
        return [dict(row) for row in rows]

    def capacity_refresh_state(self, owner_principal_id: str) -> list[dict[str, Any]]:
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_capacity_refresh_state WHERE owner_principal_id = ? ORDER BY profile_id",
                (owner_principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def capacity_refresh_due(self, owner_principal_id: str, profile_id: str) -> bool:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT next_refresh_at FROM model_capacity_refresh_state WHERE owner_principal_id = ? AND profile_id = ?",
                (owner_principal_id, profile_id),
            ).fetchone()
        return row is None or str(row["next_refresh_at"]) <= utc_now()

    def record_capacity_refresh(
        self, owner_principal_id: str, profile_id: str, status: str, reason_code: str | None
    ) -> None:
        now = datetime.now(UTC)
        now_text = now.isoformat().replace("+00:00", "Z")
        next_text = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
        with self.store.connect() as connection:
            connection.execute(
                """INSERT INTO model_capacity_refresh_state VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, profile_id) DO UPDATE SET
                last_refresh_at = excluded.last_refresh_at, next_refresh_at = excluded.next_refresh_at,
                status = excluded.status, reason_code = excluded.reason_code""",
                (owner_principal_id, profile_id, now_text, next_text, status, reason_code),
            )

    def _read(
        self, owner_principal_id: str, provider: str, model: str, source: str
    ) -> ModelFacts | None:
        if not owner_principal_id:
            return None
        with self.store.connect() as connection:
            row = connection.execute(
                """
                SELECT context_window_tokens, input_price_per_mtok,
                       output_price_per_mtok, currency
                FROM model_facts_cache
                WHERE owner_principal_id = ? AND provider = ? AND model = ? AND source = ?
                """,
                (owner_principal_id, provider, model, source),
            ).fetchone()
        if row is None:
            return None
        window = int(row[0]) if row[0] is not None else None
        input_price = _decimal_or_none(row[1])
        output_price = _decimal_or_none(row[2])
        price = (
            ModelPrice(
                input_per_mtok=input_price,
                output_per_mtok=output_price,
                currency=str(row[3] or "USD"),
                source="owner" if source == "owner" else "provider",
            )
            if input_price is not None and output_price is not None
            else None
        )
        return ModelFacts(
            provider=provider,
            model=model,
            context_window_tokens=window,
            context_window_source=("provider" if window is not None else None),
            price=price,
        )

    # ── owner overrides ─────────────────────────────────────────────────

    def set_owner_price(
        self,
        owner_principal_id: str,
        provider: str,
        model: str,
        *,
        input_per_mtok: Decimal,
        output_per_mtok: Decimal,
        currency: str = "USD",
    ) -> None:
        """Record an owner-set price. It outranks both provider and config."""
        if input_per_mtok < 0 or output_per_mtok < 0:
            raise ValueError("model_price_must_not_be_negative")
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_facts_cache (
                  owner_principal_id, provider, model, source,
                  context_window_tokens, max_output_tokens,
                  input_price_per_mtok, output_price_per_mtok, currency, fetched_at
                ) VALUES (?, ?, ?, 'owner', NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, provider, model, source) DO UPDATE SET
                  input_price_per_mtok = excluded.input_price_per_mtok,
                  output_price_per_mtok = excluded.output_price_per_mtok,
                  currency = excluded.currency,
                  fetched_at = excluded.fetched_at
                """,
                (
                    owner_principal_id,
                    provider,
                    model,
                    str(input_per_mtok),
                    str(output_per_mtok),
                    currency,
                    utc_now(),
                ),
            )

    def clear_owner_price(self, owner_principal_id: str, provider: str, model: str) -> None:
        with self.store.connect() as connection:
            connection.execute(
                "DELETE FROM model_facts_cache WHERE owner_principal_id = ? "
                "AND provider = ? AND model = ? AND source = 'owner'",
                (owner_principal_id, provider, model),
            )
