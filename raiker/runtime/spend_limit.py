"""DEC-24 step 2 — one spending limit for everything an owner's models do.

FIXED-804 bounded one run of a routine by money. Nothing bounded the owner's
spend *across* runs: a dozen routines each inside their own limit, a long Build
session and the work they delegate could together spend whatever the providers
would bill, and the only number anywhere was an advisory weekly token budget per
provider that nothing read.

This is that number, owner-wide and enforced:

* **One window, rolling.** The limit is a dollar amount for the last 24 hours,
  across every model, every surface and every task — foreground turns, routines
  and the children they delegate all write the same usage ledger, so one query
  over it is one answer for all of them.
* **Read at the turn's safe boundary,** before each further model call — the
  boundary the owner's Stop and a run's own cost limit already use. A turn that
  starts over the limit stops before its first model call; one that crosses it
  stops before its next. The overrun is therefore bounded by the responses in
  flight when it was crossed (one per running turn) — the documented bounded
  overrun this step allows when metering lags.
* **Settled, not estimated.** Spend is the provider's own token counts in the
  ledger, priced at read time with the rate the Models page shows, so a price
  correction re-prices the window. Usage on a model with no known price is not
  counted and is named, rather than read as free.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from raiker.contracts.ids import utc_now

#: The bounds the API accepts, in US dollars.
MIN_LIMIT_USD = 0.01
MAX_LIMIT_USD = 10_000.0
WINDOW = timedelta(hours=24)

def valid_limit(value: Any) -> float | None:
    """A limit the API accepts, or ``None`` for anything else."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    amount = float(value)
    return amount if MIN_LIMIT_USD <= amount <= MAX_LIMIT_USD else None


def owner_limit(store: Any, owner_principal_id: str) -> float | None:
    """The owner's 24-hour limit, or ``None`` when none is set."""
    with store.connect() as connection:
        row = connection.execute(
            "SELECT daily_limit_usd FROM owner_spend_limits WHERE owner_principal_id = ?",
            (owner_principal_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        return valid_limit(float(row[0]))
    except (TypeError, ValueError):
        return None


def set_owner_limit(store: Any, owner_principal_id: str, limit_usd: float | None) -> None:
    with store.connect() as connection:
        if limit_usd is None:
            connection.execute(
                "DELETE FROM owner_spend_limits WHERE owner_principal_id = ?",
                (owner_principal_id,),
            )
            return
        connection.execute(
            """INSERT INTO owner_spend_limits (owner_principal_id, daily_limit_usd, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(owner_principal_id) DO UPDATE SET
                 daily_limit_usd = excluded.daily_limit_usd, updated_at = excluded.updated_at""",
            (owner_principal_id, str(limit_usd), utc_now()),
        )


@dataclass
class WindowSpend:
    """What the owner's models have cost in the window, by the provider's counts."""

    total: Decimal = Decimal(0)
    #: Models used in the window whose responses could not be priced.
    unpriced: list[str] = field(default_factory=list)


#: The configured ``pricing`` block for a provider/model pair, when a profile has one.
RawPricing = Callable[[str, str], Any]


def spend_in_window(
    store: Any,
    owner_principal_id: str,
    *,
    now: datetime | None = None,
    raw_pricing: RawPricing | None = None,
) -> WindowSpend:
    from raiker.runtime.model_usage import ModelUsageLedger
    from raiker.tasks.cost_limit import resolve_price

    end = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    rows = ModelUsageLedger(store).provider_usage(
        owner_principal_id,
        started_at=(end - WINDOW).isoformat(),
        ended_at=end.isoformat(),
    )
    spend = WindowSpend()
    for row in rows:
        if row.totals.input_tokens + row.totals.output_tokens <= 0:
            continue
        pricing = None
        if raw_pricing is not None:
            try:
                pricing = raw_pricing(row.provider, row.model)
            except Exception:  # noqa: BLE001 - an unreadable profile is no configured price
                pricing = None
        try:
            price = resolve_price(store, owner_principal_id, row.provider, row.model, pricing)
        except Exception:  # noqa: BLE001 - an unreadable price is an unpriced model
            price = None
        if price is None:
            if row.model not in spend.unpriced:
                spend.unpriced.append(row.model)
            continue
        spend.total += price.cost(
            input_tokens=row.totals.input_tokens,
            output_tokens=row.totals.output_tokens,
            cache_write_tokens=row.totals.cache_write_tokens,
            cache_read_tokens=row.totals.cache_read_tokens,
        )
    return spend


def reached(limit_usd: float | None, spend: WindowSpend) -> bool:
    return limit_usd is not None and spend.total >= Decimal(str(limit_usd))


def stopped_message(limit_usd: float, spent: Decimal) -> str:
    """What a turn stopped by the owner-wide limit says."""
    return (
        f"Stopped at a safe boundary: your spending limit of ${limit_usd:.2f} for the last "
        f"24 hours is reached (about ${float(spent):.4f} across every model, by the "
        "providers' token counts). Raise or clear it on Models → Usage to continue."
    )
