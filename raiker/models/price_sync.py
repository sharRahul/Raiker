"""The provider price synchronisation job (BUG-21).

The registry stores what a price *was*. This module decides *when to go and
look*, and what to do when looking fails.

Three rules shape it, and all three exist because a pricing surface that lies is
worse than one that says nothing:

1. **Bounded cadence.** A refresh happens no more than every 6 hours and no less
   than every 24. Faster is pointless — providers change rates on the order of
   months — and slower lets a stale rate quietly price a real bill.
2. **Last known good is never discarded.** A failed refresh leaves the previous
   response in place and records the error against it. The UI then shows a real
   price *and* says it is stale, rather than falling back to "Unknown" because
   a network blip happened.
3. **No live scraping.** Only two feeds exist: a provider's own catalogue
   endpoint (the same listing the Models page already triggers), and the
   reviewed documentation adapter, which reads the ``pricing`` block a human
   committed to ``model-profiles.json``. A price is never read out of a web page
   at render time.

The scheduler holds no timer of its own. It is asked "is this provider due?" by
whatever already runs — the Models page opening, a catalogue listing, or an
explicit refresh — which keeps a local-first runtime free of background daemons
while still bounding how old a rate can be.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.models.price_registry import (
    PriceRegistry,
    rates_from_provider_metadata,
    seed_from_config,
)

# The validated window from the required fix: no tighter than 6 hours, no looser
# than 24. A caller asking for anything else is clamped rather than refused —
# an out-of-range configuration should not stop pricing from refreshing at all.
MIN_INTERVAL_HOURS = 6
MAX_INTERVAL_HOURS = 24
DEFAULT_INTERVAL_HOURS = 12

# How far past `next_refresh_at` a price may drift before the UI must call it
# stale rather than merely due. A refresh that is an hour late is normal on a
# machine that was asleep; a day late is a fact the owner needs to see.
STALE_GRACE_HOURS = 6


def clamp_interval_hours(hours: Any) -> int:
    """Coerce any requested cadence into the validated 6–24 hour window."""
    try:
        value = int(hours)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_HOURS
    return max(MIN_INTERVAL_HOURS, min(MAX_INTERVAL_HOURS, value))


def _parse(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SyncState:
    """What the pricing surface has to be able to say about one provider."""

    provider: str
    interval_hours: int
    last_attempt_at: str | None
    last_success_at: str | None
    next_refresh_at: str | None
    last_error: str | None
    models_recorded: int
    has_last_good: bool

    @property
    def due(self) -> bool:
        deadline = _parse(self.next_refresh_at)
        return deadline is None or _now() >= deadline

    @property
    def stale(self) -> bool:
        """Past its refresh deadline by more than the grace window, or failing.

        A provider whose last attempt failed is stale the moment it fails: the
        rates on screen are the previous response, and saying so is the whole
        point of keeping them.
        """
        if self.last_error is not None:
            return True
        deadline = _parse(self.next_refresh_at)
        if deadline is None:
            return self.last_success_at is None
        return _now() >= deadline + timedelta(hours=STALE_GRACE_HOURS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "interval_hours": self.interval_hours,
            "last_attempt_at": self.last_attempt_at,
            "last_success_at": self.last_success_at,
            "next_refresh_at": self.next_refresh_at,
            "last_error": self.last_error,
            "models_recorded": self.models_recorded,
            "has_last_good": self.has_last_good,
            "due": self.due,
            "stale": self.stale,
        }


@dataclass(frozen=True)
class SyncResult:
    provider: str
    ok: bool
    models_recorded: int
    changes_written: int
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "ok": self.ok,
            "models_recorded": self.models_recorded,
            "changes_written": self.changes_written,
            "reason_code": self.reason_code,
        }


class PriceSynchroniser:
    """Bounded, fail-soft synchronisation of provider prices into the registry."""

    def __init__(self, store: Any, registry: PriceRegistry | None = None) -> None:
        self.store = store
        self.registry = registry or PriceRegistry(store)

    # ── state ───────────────────────────────────────────────────────────

    def state(
        self, owner_principal_id: str, provider: str, *, interval_hours: int | None = None
    ) -> SyncState:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_price_sync_state WHERE owner_principal_id = ? "
                "AND provider = ?",
                (owner_principal_id, provider),
            ).fetchone()
        if row is None:
            return SyncState(
                provider=provider,
                interval_hours=clamp_interval_hours(interval_hours),
                last_attempt_at=None,
                last_success_at=None,
                next_refresh_at=None,
                last_error=None,
                models_recorded=0,
                has_last_good=False,
            )
        data = dict(row)
        return SyncState(
            provider=provider,
            interval_hours=clamp_interval_hours(data.get("interval_hours")),
            last_attempt_at=data.get("last_attempt_at"),
            last_success_at=data.get("last_success_at"),
            next_refresh_at=data.get("next_refresh_at"),
            last_error=data.get("last_error"),
            models_recorded=int(data.get("models_recorded") or 0),
            has_last_good=bool(data.get("last_good_payload")),
        )

    def states(self, owner_principal_id: str) -> list[SyncState]:
        with self.store.connect() as connection:
            rows = connection.execute(
                "SELECT provider FROM model_price_sync_state WHERE owner_principal_id = ? "
                "ORDER BY provider",
                (owner_principal_id,),
            ).fetchall()
        return [self.state(owner_principal_id, str(row[0])) for row in rows]

    def due(self, owner_principal_id: str, provider: str) -> bool:
        return self.state(owner_principal_id, provider).due

    # ── synchronisation ─────────────────────────────────────────────────

    def sync_from_catalogue(
        self,
        owner_principal_id: str,
        provider: str,
        models: Iterable[Any],
        *,
        interval_hours: int | None = None,
    ) -> SyncResult:
        """Record whatever a provider's own catalogue published about its prices.

        ``models`` is the provider-model list the catalogue listing already
        returns. Only entries carrying a complete, parseable price are recorded,
        against their exact published id. A catalogue that publishes no prices at
        all (OpenAI, Gemini) is a successful sync that recorded nothing — not an
        error, and not a reason to discard what documentation supplied.
        """
        recorded = 0
        changes = 0
        payload: dict[str, Any] = {}
        try:
            for info in models:
                model_id = getattr(info, "id", None)
                if not isinstance(model_id, str) or not model_id:
                    continue
                rates = rates_from_provider_metadata(getattr(info, "metadata", None))
                if rates is None:
                    continue
                recorded += 1
                payload[model_id] = {
                    "input": str(rates.input_per_mtok),
                    "output": str(rates.output_per_mtok),
                    "currency": rates.currency,
                }
                if self.registry.record(
                    owner_principal_id,
                    provider,
                    model_id,
                    rates,
                    source="provider",
                    reason="Provider catalogue synchronisation",
                ):
                    changes += 1
        except Exception as exc:  # noqa: BLE001 — a malformed catalogue is an error, not a crash
            self._record_failure(
                owner_principal_id, provider, type(exc).__name__, interval_hours
            )
            return SyncResult(provider, False, 0, 0, "provider_catalogue_unreadable")

        self._record_success(
            owner_principal_id,
            provider,
            recorded,
            json.dumps(payload, sort_keys=True) if payload else None,
            interval_hours,
        )
        return SyncResult(provider, True, recorded, changes)

    def sync_from_documentation(
        self,
        owner_principal_id: str,
        provider: str,
        pricing_block: Mapping[str, Any] | None,
        *,
        interval_hours: int | None = None,
    ) -> SyncResult:
        """Record the reviewed list price a human committed for this provider."""
        try:
            changes = seed_from_config(
                self.registry, owner_principal_id, provider, pricing_block
            )
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                owner_principal_id, provider, type(exc).__name__, interval_hours
            )
            return SyncResult(provider, False, 0, 0, "documentation_adapter_unreadable")
        entries = (pricing_block or {}).get("models")
        recorded = len(entries) if isinstance(entries, Mapping) else 0
        self._record_success(owner_principal_id, provider, recorded, None, interval_hours)
        return SyncResult(provider, True, recorded, changes)

    def record_failure(
        self,
        owner_principal_id: str,
        provider: str,
        reason_code: str,
        *,
        interval_hours: int | None = None,
    ) -> SyncResult:
        """Note that a refresh could not happen, keeping the last good response."""
        self._record_failure(owner_principal_id, provider, reason_code, interval_hours)
        return SyncResult(provider, False, 0, 0, reason_code)

    # ── state writes ────────────────────────────────────────────────────

    def _record_success(
        self,
        owner_principal_id: str,
        provider: str,
        models_recorded: int,
        payload: str | None,
        interval_hours: int | None,
    ) -> None:
        interval = clamp_interval_hours(
            interval_hours
            if interval_hours is not None
            else self.state(owner_principal_id, provider).interval_hours
        )
        now = _now()
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_price_sync_state (
                  owner_principal_id, provider, interval_hours, last_attempt_at,
                  last_success_at, next_refresh_at, last_error, last_good_payload,
                  models_recorded
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(owner_principal_id, provider) DO UPDATE SET
                  interval_hours = excluded.interval_hours,
                  last_attempt_at = excluded.last_attempt_at,
                  last_success_at = excluded.last_success_at,
                  next_refresh_at = excluded.next_refresh_at,
                  last_error = NULL,
                  last_good_payload = COALESCE(
                    excluded.last_good_payload, model_price_sync_state.last_good_payload
                  ),
                  models_recorded = excluded.models_recorded
                """,
                (
                    owner_principal_id,
                    provider,
                    interval,
                    utc_now(),
                    utc_now(),
                    (now + timedelta(hours=interval)).isoformat().replace("+00:00", "Z"),
                    payload,
                    int(models_recorded),
                ),
            )

    def _record_failure(
        self,
        owner_principal_id: str,
        provider: str,
        reason_code: str,
        interval_hours: int | None,
    ) -> None:
        """A failed refresh moves the attempt clock only.

        `last_success_at`, `next_refresh_at` and `last_good_payload` are left
        exactly as they were, which is what keeps the last known good response
        on screen — labelled stale — instead of replacing a real rate with a
        gap because one request timed out.
        """
        interval = clamp_interval_hours(
            interval_hours
            if interval_hours is not None
            else self.state(owner_principal_id, provider).interval_hours
        )
        with self.store.connect() as connection:
            connection.execute(
                """
                INSERT INTO model_price_sync_state (
                  owner_principal_id, provider, interval_hours, last_attempt_at,
                  last_success_at, next_refresh_at, last_error, last_good_payload,
                  models_recorded
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, NULL, 0)
                ON CONFLICT(owner_principal_id, provider) DO UPDATE SET
                  interval_hours = excluded.interval_hours,
                  last_attempt_at = excluded.last_attempt_at,
                  last_error = excluded.last_error
                """,
                (
                    owner_principal_id,
                    provider,
                    interval,
                    utc_now(),
                    str(reason_code)[:200],
                ),
            )
