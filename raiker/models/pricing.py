"""Per-model context capacity and price resolution.

Three sources, in a fixed precedence, and the winning one is always named so the
UI can say where a number came from:

1. ``owner``    — a price the owner set explicitly. Always wins.
2. ``provider`` — a fact the provider itself published, cached from its models
   endpoint. Anthropic publishes ``max_input_tokens``; OpenRouter publishes both
   a context length and a per-token price. Most providers publish neither.
3. ``config``   — a documented list price shipped in ``model-profiles.json``,
   carrying the ``as_of`` date it was recorded.

Anything with no source resolves to ``None``. Nothing here ever invents a price:
a model Raiker has no price for reports cost unavailable rather than zero, so
"$0.00" always means "this turn was free", never "we do not know".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

FactSource = Literal["owner", "provider", "config"]

# One million tokens — every price in Raiker is quoted per million tokens,
# because that is how every provider quotes them.
TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


def _decimal(value: Any) -> Decimal | None:
    """A non-negative Decimal, or None. Rejects bools, NaN, and junk."""
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


@dataclass(frozen=True)
class ModelPrice:
    """A resolved price for one model, with the source that supplied it.

    Cache-write and cache-read are separate optional components (BUG-21).
    Providers bill them independently of the normal input rate — Anthropic
    writes cache above the input rate and reads it far below — so they are held
    as their own numbers and stay ``None`` when nobody published them. They are
    never derived from the input rate: an inferred cache rate would be
    indistinguishable in the UI from one a provider actually stated.
    """

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    currency: str
    source: FactSource
    as_of: str | None = None
    cache_write_per_mtok: Decimal | None = None
    cache_read_per_mtok: Decimal | None = None

    def cost(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> Decimal:
        """Cost for one turn's counts.

        Cache counts are billed at their own rate when one is known. When they
        are not, they fall back to the plain input rate — which over-states a
        cache read rather than under-stating it, because a bill should never be
        a surprise in the expensive direction.
        """
        billable_in = Decimal(max(0, input_tokens))
        billable_out = Decimal(max(0, output_tokens))
        total = billable_in * self.input_per_mtok + billable_out * self.output_per_mtok
        for tokens, rate in (
            (cache_write_tokens, self.cache_write_per_mtok),
            (cache_read_tokens, self.cache_read_per_mtok),
        ):
            counted = Decimal(max(0, tokens))
            total += counted * (self.input_per_mtok if rate is None else rate)
        return total / TOKENS_PER_PRICE_UNIT


@dataclass(frozen=True)
class ModelFacts:
    """Everything Raiker knows about one model, each fact separately sourced."""

    provider: str
    model: str
    context_window_tokens: int | None = None
    context_window_source: FactSource | None = None
    price: ModelPrice | None = None

    @property
    def priced(self) -> bool:
        return self.price is not None


def price_from_config(
    pricing_block: Mapping[str, Any] | None, model: str
) -> ModelPrice | None:
    """Read one model's list price out of a profile's ``pricing`` block.

    Shape::

        "pricing": {
          "currency": "USD",
          "as_of": "2026-07",
          "unit": "per_million_tokens",
          "models": {"claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0}}
        }

    A model absent from ``models`` has no configured price — it is not silently
    given the price of a sibling model, because sibling models differ by an
    order of magnitude.
    """
    if not isinstance(pricing_block, Mapping):
        return None
    models = pricing_block.get("models")
    if not isinstance(models, Mapping):
        return None
    entry = models.get(model)
    if not isinstance(entry, Mapping):
        return None
    input_price = _decimal(entry.get("input"))
    output_price = _decimal(entry.get("output"))
    if input_price is None or output_price is None:
        return None
    currency = pricing_block.get("currency")
    as_of = pricing_block.get("as_of")
    return ModelPrice(
        input_per_mtok=input_price,
        output_per_mtok=output_price,
        currency=str(currency) if isinstance(currency, str) and currency else "USD",
        source="config",
        as_of=str(as_of) if isinstance(as_of, str) and as_of else None,
    )


def facts_from_provider_metadata(
    provider: str, model: str, metadata: Mapping[str, Any] | None
) -> ModelFacts:
    """Interpret the metadata a provider's models endpoint returned.

    Handles the two shapes seen in the wild:

    * Anthropic — ``max_input_tokens`` is the usable context window.
    * OpenRouter (OpenAI-compatible) — ``context_length`` plus ``pricing``
      quoted in currency **per single token**, which is scaled to per-million
      here so every price in Raiker shares one unit.

    A provider that publishes neither returns empty facts, which is the normal
    case (OpenAI and Gemini publish no price at all).
    """
    if not isinstance(metadata, Mapping):
        return ModelFacts(provider=provider, model=model)

    window = _positive_int(metadata.get("max_input_tokens")) or _positive_int(
        metadata.get("context_length")
    )

    price: ModelPrice | None = None
    pricing = metadata.get("pricing")
    if isinstance(pricing, Mapping):
        per_token_in = _decimal(pricing.get("prompt"))
        per_token_out = _decimal(pricing.get("completion"))
        if per_token_in is not None and per_token_out is not None:
            # A published price of exactly zero is a real fact (free models on
            # OpenRouter), so it is kept rather than treated as missing.
            price = ModelPrice(
                input_per_mtok=per_token_in * TOKENS_PER_PRICE_UNIT,
                output_per_mtok=per_token_out * TOKENS_PER_PRICE_UNIT,
                currency=str(pricing.get("currency") or "USD"),
                source="provider",
            )

    return ModelFacts(
        provider=provider,
        model=model,
        context_window_tokens=window,
        context_window_source="provider" if window is not None else None,
        price=price,
    )


def resolve_model_facts(
    *,
    provider: str,
    model: str,
    owner_price: ModelPrice | None = None,
    provider_facts: ModelFacts | None = None,
    config_pricing: Mapping[str, Any] | None = None,
    config_context_window: int | None = None,
) -> ModelFacts:
    """Merge the three sources into one answer, per fact rather than per source.

    Capacity and price are resolved independently: a provider that publishes a
    context window but no price yields provider-sourced capacity alongside a
    config-sourced price, and the UI labels each accordingly.
    """
    window = provider_facts.context_window_tokens if provider_facts else None
    window_source: FactSource | None = "provider" if window is not None else None
    if window is None:
        window = _positive_int(config_context_window)
        window_source = "config" if window is not None else None

    price = owner_price
    if price is None and provider_facts is not None:
        price = provider_facts.price
    if price is None:
        price = price_from_config(config_pricing, model)

    return ModelFacts(
        provider=provider,
        model=model,
        context_window_tokens=window,
        context_window_source=window_source,
        price=price,
    )
