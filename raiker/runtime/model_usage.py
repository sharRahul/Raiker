"""Per-session and per-provider token accounting.

The runtime already emits normalised token counts on every
``model_request_completed`` event. That is the right record for audit, but it is
an append-only log — answering "what has this chat cost?" from it would mean
replaying events on every popover open. This module keeps the same counts in a
small queryable ledger alongside the log.

Counts only. No prompt text, no response text, no credential ever reaches this
table, and cost is never stored — it is derived at read time from the currently
resolved price, so correcting a price re-prices history instead of leaving a
stale number on disk.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.models.pricing import ModelFacts


@dataclass(frozen=True)
class UsageTotals:
    """Summed token counts for one scope (a session, or a provider)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    turns: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost(self, facts: ModelFacts | None) -> Decimal | None:
        """Cost for these counts, or None when no price is resolvable."""
        if facts is None or facts.price is None:
            return None
        return facts.price.cost(
            input_tokens=self.input_tokens, output_tokens=self.output_tokens
        )


@dataclass(frozen=True)
class ModelUsageRow:
    """One provider/model pair's totals within a scope."""

    provider: str
    model: str
    totals: UsageTotals


class ModelUsageLedger:
    """Records and aggregates token counts. All reads are owner-scoped."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def record(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        provider: str,
        model: str,
        usage: Mapping[str, Any] | None,
    ) -> bool:
        """Append one turn's counts. Returns False when there is nothing to record.

        A provider that reported no usage writes no row at all, so a missing
        count never becomes a zero that later reads would present as "free".
        """
        if not owner_principal_id or not session_id or not isinstance(usage, Mapping):
            return False

        def _count(key: str) -> int:
            value = usage.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return 0
            return value

        input_tokens = _count("input_tokens")
        output_tokens = _count("output_tokens")
        cache_read = _count("cache_read_input_tokens")
        cache_write = _count("cache_creation_input_tokens")
        if input_tokens == 0 and output_tokens == 0 and cache_read == 0 and cache_write == 0:
            return False

        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_usage_ledger (
                  usage_id, owner_principal_id, session_id, provider, model,
                  input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                  recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("usage_"),
                    owner_principal_id,
                    session_id,
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    cache_read,
                    cache_write,
                    utc_now(),
                ),
            )
        return True

    def _rows(self, sql: str, params: tuple[Any, ...]) -> list[ModelUsageRow]:
        with self.store.connect() as connection:
            cursor = connection.execute(sql, params)
            return [
                ModelUsageRow(
                    provider=str(row[0]),
                    model=str(row[1]),
                    totals=UsageTotals(
                        input_tokens=int(row[2] or 0),
                        output_tokens=int(row[3] or 0),
                        cache_read_tokens=int(row[4] or 0),
                        cache_write_tokens=int(row[5] or 0),
                        turns=int(row[6] or 0),
                    ),
                )
                for row in cursor.fetchall()
            ]

    _AGGREGATE = """
        SELECT provider, model,
               SUM(input_tokens), SUM(output_tokens),
               SUM(cache_read_tokens), SUM(cache_write_tokens), COUNT(*)
        FROM model_usage_ledger
        WHERE owner_principal_id = ?{extra}
        GROUP BY provider, model
        ORDER BY provider, model
    """

    def session_usage(self, owner_principal_id: str, session_id: str) -> list[ModelUsageRow]:
        """Totals for one conversation, split by the models it actually used."""
        return self._rows(
            self._AGGREGATE.format(extra=" AND session_id = ?"),
            (owner_principal_id, session_id),
        )

    def provider_usage(self, owner_principal_id: str) -> list[ModelUsageRow]:
        """All-time totals for this owner, split by provider and model."""
        return self._rows(self._AGGREGATE.format(extra=""), (owner_principal_id,))


def sum_totals(rows: list[ModelUsageRow]) -> UsageTotals:
    return UsageTotals(
        input_tokens=sum(row.totals.input_tokens for row in rows),
        output_tokens=sum(row.totals.output_tokens for row in rows),
        cache_read_tokens=sum(row.totals.cache_read_tokens for row in rows),
        cache_write_tokens=sum(row.totals.cache_write_tokens for row in rows),
        turns=sum(row.totals.turns for row in rows),
    )
