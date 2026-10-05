"""DEC-12 step 6 — a routine's own cost limit for one run.

FIXED-786 bounded one run by time and FIXED-797 by tool calls; this bounds it by
money. A routine whose instructions send it round a tool loop could otherwise
spend whatever its provider would bill, every cycle, with nothing on its card
to say so.

How it is measured, exactly:

* **From the provider's own token counts.** Each model response's usage — the
  counts the usage ledger already records — is priced with the same rate the
  Models page shows (the price registry, then the owner's price, the provider's
  published price, then the profile's configured pricing).
* **Checked before each further model call.** The turn's safe boundary is where
  the owner's Stop is read; the limit is read there too. A run is stopped
  *before* it asks the model again, never in the middle of an answer, so the
  overrun is bounded by one model response — the documented bounded overrun
  DEC-24 step 2 allows when metering lags.
* **Unknown is said, not guessed.** A model with no known price cannot be held
  to a dollar figure. The run is not stopped for that; *Will it run?* says the
  limit cannot be measured for that model, so the owner knows the limit is not
  protecting them rather than believing it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from raiker.models.pricing import ModelPrice

#: The bounds Settings and the API accept, in US dollars.
MIN_COST_USD = 0.01
MAX_COST_USD = 1000.0


def cost_limit(value: Any) -> float | None:
    """A stored limit, if it is one; anything else is no limit of its own."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    amount = float(value)
    return amount if MIN_COST_USD <= amount <= MAX_COST_USD else None


def resolve_price(store: Any, principal_id: str, provider: str, model: str, raw_pricing: Any = None) -> ModelPrice | None:
    """The rate the Models page would show for this pair, or ``None`` when unknown."""
    from raiker.models.price_registry import PriceRegistry
    from raiker.models.pricing import resolve_model_facts
    from raiker.runtime.model_facts_store import ModelFactsStore

    facts_store = ModelFactsStore(store)
    owner_price = facts_store.owner_price(principal_id, provider, model)
    registered = PriceRegistry(store).resolve(principal_id, provider, model)
    if registered is not None:
        owner_price = registered.rates.to_price(registered.source, registered.as_of)
    facts = resolve_model_facts(
        provider=provider,
        model=model,
        owner_price=owner_price,
        provider_facts=facts_store.provider_facts(principal_id, provider, model),
        config_pricing=raw_pricing,
    )
    return facts.price


@dataclass
class TurnSpend:
    """What one turn's model calls have cost so far, in the price's currency."""

    total: Decimal = Decimal(0)
    #: Models whose responses could not be priced; their spend is not in ``total``.
    unpriced: set[str] = field(default_factory=set)

    def add(self, price: ModelPrice | None, model: str, usage: dict[str, int]) -> None:
        if price is None:
            self.unpriced.add(model)
            return
        # `summarize_model_usage`'s normalised keys, which is what the
        # orchestrator meters; the raw provider spelling is accepted too.
        def count(*keys: str) -> int:
            for key in keys:
                value = usage.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value
            return 0

        self.total += price.cost(
            input_tokens=count("input_tokens"),
            output_tokens=count("output_tokens"),
            cache_write_tokens=count("cache_write_tokens", "cache_creation_input_tokens"),
            cache_read_tokens=count("cache_read_tokens", "cache_read_input_tokens"),
        )

    def reached(self, limit: float | None) -> bool:
        return limit is not None and self.total >= Decimal(str(limit))


def stopped_message(limit: float, spent: Decimal) -> str:
    """What a run stopped by its cost limit says, on its card and in its history."""
    return (
        f"Stopped at a safe boundary: this run reached its cost limit of ${limit:.2f} "
        f"(about ${float(spent):.4f} by the provider's token counts). "
        "It counts as a cycle that did not complete."
    )
