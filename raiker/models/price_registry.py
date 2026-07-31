"""The historical, effective-dated price registry (BUG-21).

Before this module a price was a *current value*: whatever the shipped profile
said, or whatever the last catalogue listing cached, overwritten in place. That
cannot answer the only question a bill ever raises — *what was this model's rate
on the day that turn ran* — and it cannot show an owner why a number changed.

So prices are stored the way facts with a date are stored:

* **Append-only and effective-dated.** One row per
  ``(owner, provider, exact model id, source, effective_from)``. A refresh that
  sees new rates writes a new row; the old row stays and becomes history.
* **Idempotent.** ``content_hash`` covers every rate component plus the
  currency, so a 6-hourly synchronisation against unchanged rates writes
  nothing. History records changes, not polls.
* **Exact model IDs only.** ``claude-haiku-4-5-20251001`` never inherits
  ``claude-sonnet-4-5``'s rate. Sibling models differ by an order of magnitude,
  so a near-miss is worse than an honest "Unknown".
* **Four independent rate components.** Input, output, cache-write and
  cache-read are separate columns because providers price them separately.
  Folding a cache read into "input" over-states a cached turn by 10x.
* **Sourced and audited.** ``source`` is one of ``owner`` (an administrator set
  it), ``provider`` (the provider's own catalogue published it), or ``config``
  (a reviewed documentation adapter shipped it, carrying the ``as_of`` date it
  was recorded). An owner row additionally carries ``recorded_by`` and
  ``reason``, so an override is never anonymous.

Precedence when resolving *the* rate for a model is unchanged from
``raiker.models.pricing``: owner > provider > config. What is new is that each
source keeps its own history, so switching precedence never destroys evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.models.pricing import (
    TOKENS_PER_PRICE_UNIT,
    FactSource,
    ModelPrice,
    _decimal,
)

# Owner beats provider beats config. A list rather than a dict so the order is
# the statement: the first source with a row for this exact model wins.
SOURCE_PRECEDENCE: tuple[FactSource, ...] = ("owner", "provider", "config")

VALID_SOURCES = frozenset(SOURCE_PRECEDENCE)


class PriceRegistryError(ValueError):
    """A price that cannot be stored as stated. Never stored approximately."""


@dataclass(frozen=True)
class PriceRates:
    """Four independently-billed rates, all quoted per million tokens."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_write_per_mtok: Decimal | None = None
    cache_read_per_mtok: Decimal | None = None
    currency: str = "USD"

    @property
    def content_hash(self) -> str:
        """Stable identity for "these exact rates", used to suppress re-writes."""
        parts = "|".join(
            [
                str(self.input_per_mtok),
                str(self.output_per_mtok),
                "" if self.cache_write_per_mtok is None else str(self.cache_write_per_mtok),
                "" if self.cache_read_per_mtok is None else str(self.cache_read_per_mtok),
                self.currency,
            ]
        )
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()

    def to_price(self, source: FactSource, as_of: str | None) -> ModelPrice:
        return ModelPrice(
            input_per_mtok=self.input_per_mtok,
            output_per_mtok=self.output_per_mtok,
            cache_write_per_mtok=self.cache_write_per_mtok,
            cache_read_per_mtok=self.cache_read_per_mtok,
            currency=self.currency,
            source=source,
            as_of=as_of,
        )


@dataclass(frozen=True)
class RegisteredPrice:
    """One effective-dated row, with everything the UI has to be able to state."""

    provider: str
    model: str
    source: FactSource
    rates: PriceRates
    effective_from: str
    recorded_at: str
    as_of: str | None = None
    recorded_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "source": self.source,
            "effective_from": self.effective_from,
            "recorded_at": self.recorded_at,
            "as_of": self.as_of,
            "recorded_by": self.recorded_by,
            "reason": self.reason,
            "currency": self.rates.currency,
            "input_per_mtok": str(self.rates.input_per_mtok),
            "output_per_mtok": str(self.rates.output_per_mtok),
            "cache_write_per_mtok": (
                None
                if self.rates.cache_write_per_mtok is None
                else str(self.rates.cache_write_per_mtok)
            ),
            "cache_read_per_mtok": (
                None
                if self.rates.cache_read_per_mtok is None
                else str(self.rates.cache_read_per_mtok)
            ),
        }


def rates_from_mapping(entry: Mapping[str, Any], currency: str = "USD") -> PriceRates | None:
    """Read one model's rates out of a documentation/config block.

    Input and output are mandatory — a price with only half of itself is not a
    price. Cache components are optional and stay ``None`` rather than being
    inferred from a provider's usual multiplier: an invented cache rate would be
    indistinguishable from a published one in the UI.
    """
    input_price = _decimal(entry.get("input"))
    output_price = _decimal(entry.get("output"))
    if input_price is None or output_price is None:
        return None
    return PriceRates(
        input_per_mtok=input_price,
        output_per_mtok=output_price,
        cache_write_per_mtok=_decimal(entry.get("cache_write")),
        cache_read_per_mtok=_decimal(entry.get("cache_read")),
        currency=str(currency) if currency else "USD",
    )


def rates_from_provider_metadata(metadata: Mapping[str, Any] | None) -> PriceRates | None:
    """Read rates out of a provider catalogue entry.

    OpenAI-compatible catalogues (OpenRouter is the one that actually publishes
    prices) quote per single token, which is scaled here so every rate in Raiker
    shares one unit. A published zero is a real fact — free models exist — and
    is preserved rather than treated as missing.
    """
    if not isinstance(metadata, Mapping):
        return None
    pricing = metadata.get("pricing")
    if not isinstance(pricing, Mapping):
        return None
    per_token_in = _decimal(pricing.get("prompt"))
    per_token_out = _decimal(pricing.get("completion"))
    if per_token_in is None or per_token_out is None:
        return None
    cache_write = _decimal(pricing.get("input_cache_write"))
    cache_read = _decimal(pricing.get("input_cache_read"))
    return PriceRates(
        input_per_mtok=per_token_in * TOKENS_PER_PRICE_UNIT,
        output_per_mtok=per_token_out * TOKENS_PER_PRICE_UNIT,
        cache_write_per_mtok=(
            None if cache_write is None else cache_write * TOKENS_PER_PRICE_UNIT
        ),
        cache_read_per_mtok=None if cache_read is None else cache_read * TOKENS_PER_PRICE_UNIT,
        currency=str(pricing.get("currency") or "USD"),
    )


class PriceRegistry:
    """Owner-scoped, append-only storage for effective-dated model prices."""

    def __init__(self, store: Any) -> None:
        self.store = store

    # ── writing ─────────────────────────────────────────────────────────

    def record(
        self,
        owner_principal_id: str,
        provider: str,
        model: str,
        rates: PriceRates,
        *,
        source: FactSource,
        effective_from: str | None = None,
        as_of: str | None = None,
        recorded_by: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Append one effective-dated row. Returns whether anything was written.

        A record whose rates match the current row for the same source is a
        no-op: a synchronisation that confirms today's price has not changed the
        price, and history that logged every poll would bury the one entry that
        matters.
        """
        if not owner_principal_id or not provider or not model:
            raise PriceRegistryError("model_price_scope_incomplete")
        if source not in VALID_SOURCES:
            raise PriceRegistryError("model_price_source_invalid")
        if rates.input_per_mtok < 0 or rates.output_per_mtok < 0:
            raise PriceRegistryError("model_price_must_not_be_negative")
        for optional in (rates.cache_write_per_mtok, rates.cache_read_per_mtok):
            if optional is not None and optional < 0:
                raise PriceRegistryError("model_price_must_not_be_negative")

        existing = self._latest(owner_principal_id, provider, model, source)
        if existing is not None and existing.rates.content_hash == rates.content_hash:
            return False

        now = utc_now()
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_price_registry (
                  owner_principal_id, provider, model, source, effective_from,
                  input_per_mtok, output_per_mtok, cache_write_per_mtok,
                  cache_read_per_mtok, currency, as_of, content_hash,
                  recorded_at, recorded_by, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, provider, model, source, effective_from)
                DO UPDATE SET
                  input_per_mtok = excluded.input_per_mtok,
                  output_per_mtok = excluded.output_per_mtok,
                  cache_write_per_mtok = excluded.cache_write_per_mtok,
                  cache_read_per_mtok = excluded.cache_read_per_mtok,
                  currency = excluded.currency,
                  as_of = excluded.as_of,
                  content_hash = excluded.content_hash,
                  recorded_at = excluded.recorded_at,
                  recorded_by = excluded.recorded_by,
                  reason = excluded.reason
                """,
                (
                    owner_principal_id,
                    provider,
                    model,
                    source,
                    effective_from or now,
                    str(rates.input_per_mtok),
                    str(rates.output_per_mtok),
                    None if rates.cache_write_per_mtok is None else str(rates.cache_write_per_mtok),
                    None if rates.cache_read_per_mtok is None else str(rates.cache_read_per_mtok),
                    rates.currency,
                    as_of,
                    rates.content_hash,
                    now,
                    recorded_by,
                    reason,
                ),
            )
        return True

    def clear_source(
        self, owner_principal_id: str, provider: str, model: str, source: FactSource
    ) -> int:
        """Withdraw every row for one source — how an owner override is removed.

        The override's history goes with it, because a withdrawn override is not
        an effective-dated fact any more; the provider and config histories that
        the model falls back to are untouched.
        """
        with self.store.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_price_registry WHERE owner_principal_id = ? "
                "AND provider = ? AND model = ? AND source = ?",
                (owner_principal_id, provider, model, source),
            )
        return int(cursor.rowcount or 0)

    # ── reading ─────────────────────────────────────────────────────────

    def resolve(
        self, owner_principal_id: str, provider: str, model: str
    ) -> RegisteredPrice | None:
        """The rate in force for this exact model, by source precedence."""
        if not owner_principal_id or not provider or not model:
            return None
        for source in SOURCE_PRECEDENCE:
            row = self._latest(owner_principal_id, provider, model, source)
            if row is not None:
                return row
        return None

    def history(
        self, owner_principal_id: str, provider: str, model: str, *, limit: int = 50
    ) -> list[RegisteredPrice]:
        """Every recorded rate for one model, newest first, across all sources."""
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_price_registry WHERE owner_principal_id = ? "
                "AND provider = ? AND model = ? ORDER BY effective_from DESC, recorded_at DESC "
                "LIMIT ?",
                (owner_principal_id, provider, model, max(1, min(int(limit), 500))),
            ).fetchall()
        return [_row_to_price(row) for row in rows]

    def models(self, owner_principal_id: str) -> list[tuple[str, str]]:
        """Every ``(provider, exact model id)`` this owner has any price for."""
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT provider, model FROM model_price_registry "
                "WHERE owner_principal_id = ? ORDER BY provider, model",
                (owner_principal_id,),
            ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]

    def _latest(
        self, owner_principal_id: str, provider: str, model: str, source: str
    ) -> RegisteredPrice | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_price_registry WHERE owner_principal_id = ? "
                "AND provider = ? AND model = ? AND source = ? "
                "ORDER BY effective_from DESC, recorded_at DESC LIMIT 1",
                (owner_principal_id, provider, model, source),
            ).fetchone()
        return None if row is None else _row_to_price(row)


def _row_to_price(row: Any) -> RegisteredPrice:
    data = dict(row)
    rates = PriceRates(
        input_per_mtok=Decimal(str(data["input_per_mtok"])),
        output_per_mtok=Decimal(str(data["output_per_mtok"])),
        cache_write_per_mtok=(
            None
            if data.get("cache_write_per_mtok") is None
            else Decimal(str(data["cache_write_per_mtok"]))
        ),
        cache_read_per_mtok=(
            None
            if data.get("cache_read_per_mtok") is None
            else Decimal(str(data["cache_read_per_mtok"]))
        ),
        currency=str(data.get("currency") or "USD"),
    )
    source = str(data["source"])
    return RegisteredPrice(
        provider=str(data["provider"]),
        model=str(data["model"]),
        source=source if source in VALID_SOURCES else "config",  # type: ignore[arg-type]
        rates=rates,
        effective_from=str(data["effective_from"]),
        recorded_at=str(data["recorded_at"]),
        as_of=None if data.get("as_of") is None else str(data["as_of"]),
        recorded_by=None if data.get("recorded_by") is None else str(data["recorded_by"]),
        reason=None if data.get("reason") is None else str(data["reason"]),
    )


def seed_from_config(
    registry: PriceRegistry,
    owner_principal_id: str,
    provider: str,
    pricing_block: Mapping[str, Any] | None,
    models: Iterable[str] | None = None,
) -> int:
    """Record a shipped ``pricing`` block through the reviewed-documentation path.

    This is deliberately *not* live scraping: the rates come from the profile
    JSON a human reviewed and committed, carrying the ``as_of`` date it was
    recorded, and land in the registry as ``source="config"``. Anything the
    block does not name stays unpriced.
    """
    if not isinstance(pricing_block, Mapping):
        return 0
    entries = pricing_block.get("models")
    if not isinstance(entries, Mapping):
        return 0
    currency = str(pricing_block.get("currency") or "USD")
    as_of = pricing_block.get("as_of")
    wanted = None if models is None else set(models)
    written = 0
    for model_id, entry in entries.items():
        if not isinstance(model_id, str) or not isinstance(entry, Mapping):
            continue
        if wanted is not None and model_id not in wanted:
            continue
        rates = rates_from_mapping(entry, currency)
        if rates is None:
            continue
        if registry.record(
            owner_principal_id,
            provider,
            model_id,
            rates,
            source="config",
            effective_from=str(as_of) if isinstance(as_of, str) and as_of else None,
            as_of=str(as_of) if isinstance(as_of, str) and as_of else None,
            reason="Shipped list price, reviewed documentation adapter",
        ):
            written += 1
    return written
