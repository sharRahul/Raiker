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
from datetime import UTC, datetime, timedelta
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
    requests: int = 0
    turns: int = 0
    compactions: int = 0

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
    profile_id: str | None = None


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
        profile_id: str | None = None,
        request_kind: str = "turn",
        recorded_at: str | None = None,
    ) -> bool:
        """Append one turn's counts. Returns False when there is nothing to record.

        A provider that reported no usage writes no row at all, so a missing
        count never becomes a zero that later reads would present as "free".
        """
        if request_kind not in {"turn", "compaction", "readiness"}:
            raise ValueError("invalid_model_usage_request_kind")
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
                  recorded_at, profile_id, request_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _utc_timestamp(recorded_at),
                    profile_id,
                    request_kind,
                ),
            )
        return True

    def _rows(self, sql: str, params: tuple[Any, ...]) -> list[ModelUsageRow]:
        with self.store.connect() as connection:
            cursor = connection.execute(sql, params)
            return [
                ModelUsageRow(
                    profile_id=str(row[0]) if row[0] is not None else None,
                    provider=str(row[1]),
                    model=str(row[2]),
                    totals=UsageTotals(
                        input_tokens=int(row[3] or 0),
                        output_tokens=int(row[4] or 0),
                        cache_read_tokens=int(row[5] or 0),
                        cache_write_tokens=int(row[6] or 0),
                        requests=int(row[7] or 0),
                        turns=int(row[8] or 0),
                        compactions=int(row[9] or 0),
                    ),
                )
                for row in cursor.fetchall()
            ]

    _AGGREGATE = """
        SELECT profile_id, provider, model,
               SUM(input_tokens), SUM(output_tokens),
               SUM(cache_read_tokens), SUM(cache_write_tokens),
               COUNT(*),
               SUM(CASE WHEN request_kind = 'turn' THEN 1 ELSE 0 END),
               SUM(CASE WHEN request_kind = 'compaction' THEN 1 ELSE 0 END)
        FROM model_usage_ledger
        WHERE owner_principal_id = ?{extra}
        GROUP BY profile_id, provider, model
        ORDER BY provider, model, profile_id
    """

    def session_usage(self, owner_principal_id: str, session_id: str) -> list[ModelUsageRow]:
        """Totals for one conversation, split by the models it actually used."""
        return self._rows(
            self._AGGREGATE.format(extra=" AND session_id = ?"),
            (owner_principal_id, session_id),
        )

    def provider_usage(
        self,
        owner_principal_id: str,
        *,
        profile_id: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> list[ModelUsageRow]:
        """Bounded totals for this owner, split by profile, provider, and model."""
        clauses: list[str] = []
        params: list[Any] = [owner_principal_id]
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        if started_at is not None:
            clauses.append("recorded_at >= ?")
            params.append(_utc_timestamp(started_at))
        if ended_at is not None:
            clauses.append("recorded_at <= ?")
            params.append(_utc_timestamp(ended_at))
        extra = "".join(f" AND {clause}" for clause in clauses)
        return self._rows(self._AGGREGATE.format(extra=extra), tuple(params))

    def weekly_usage(
        self, owner_principal_id: str, profile_id: str, *, now: datetime
    ) -> UsageTotals:
        """Raiker-observed usage in the inclusive rolling seven-day window."""
        if now.tzinfo is None:
            raise ValueError("weekly_usage_now_must_be_timezone_aware")
        end = now.astimezone(UTC).replace(microsecond=0)
        start = end - timedelta(days=7)
        return sum_totals(
            self.provider_usage(
                owner_principal_id,
                profile_id=profile_id,
                started_at=start.isoformat(),
                ended_at=end.isoformat(),
            )
        )

    def set_weekly_token_budget(
        self, owner_principal_id: str, profile_id: str, tokens: int | None
    ) -> None:
        """Set or clear an owner-defined advisory token budget."""
        if not owner_principal_id or not profile_id:
            raise ValueError("weekly_token_budget_scope_required")
        if tokens is not None and (
            isinstance(tokens, bool) or not isinstance(tokens, int) or tokens <= 0
        ):
            raise ValueError("weekly_token_budget_must_be_positive")
        with self.store.connect() as connection:
            if tokens is None:
                connection.execute(
                    "DELETE FROM model_weekly_budgets "
                    "WHERE owner_principal_id = ? AND profile_id = ?",
                    (owner_principal_id, profile_id),
                )
                return
            connection.execute(
                """
                INSERT INTO model_weekly_budgets (
                  owner_principal_id, profile_id, token_budget, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, profile_id) DO UPDATE SET
                  token_budget = excluded.token_budget,
                  updated_at = excluded.updated_at
                """,
                (owner_principal_id, profile_id, tokens, utc_now()),
            )

    def weekly_token_budget(self, owner_principal_id: str, profile_id: str) -> int | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT token_budget FROM model_weekly_budgets "
                "WHERE owner_principal_id = ? AND profile_id = ?",
                (owner_principal_id, profile_id),
            ).fetchone()
        return int(row[0]) if row is not None else None


def sum_totals(rows: list[ModelUsageRow]) -> UsageTotals:
    return UsageTotals(
        input_tokens=sum(row.totals.input_tokens for row in rows),
        output_tokens=sum(row.totals.output_tokens for row in rows),
        cache_read_tokens=sum(row.totals.cache_read_tokens for row in rows),
        cache_write_tokens=sum(row.totals.cache_write_tokens for row in rows),
        requests=sum(row.totals.requests for row in rows),
        turns=sum(row.totals.turns for row in rows),
        compactions=sum(row.totals.compactions for row in rows),
    )


def _utc_timestamp(value: str | None) -> str:
    if value is None:
        return utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("model_usage_recorded_at_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("model_usage_recorded_at_timezone_required")
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
