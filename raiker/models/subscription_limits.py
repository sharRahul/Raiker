"""What a subscription says is left, in the provider's own words (BUG-254).

ChatGPT reports a five-hour limit, a weekly limit, and how much of each is left.
Ollama Cloud reports session and weekly usage. Raiker showed neither, so an
owner discovered a limit by hitting it mid-turn.

The rule that shapes this module is the one that keeps it honest:

> **Read only what the provider volunteers as part of a turn. Never poll a
> portal, and never infer.**

That is a different thing from :mod:`raiker.models.provider_usage`, which reads
a provider's usage *API* on request and is explicitly a network call the owner
asks for. These windows cost nothing and reach nowhere: they arrive attached to
a turn that was already happening, and are recorded as they were stated.

Consequences of that rule, all deliberate:

* A provider that says nothing has **nothing shown**. Not zero, not an estimate,
  not "unknown" dressed up as a number — the surface simply omits it.
* A window is stored with the moment it was observed, because "68% used" is
  meaningless without knowing when, and a stale window must be able to say so.
* Only bounded numbers survive. A percentage outside 0–100, a window length that
  is not a positive number of minutes, a reset that is not a count of seconds:
  each is dropped individually, so one malformed field cannot take a whole
  reading with it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

#: How a provider hands on what it volunteered: profile id, and the windows.
#: Kept here rather than with the provider so every provider that gains this
#: reports it the same shape.
LimitWindowSink = Callable[[str, "tuple[LimitWindow, ...]"], None]

#: A reading older than this is reported as stale rather than as the truth. A
#: five-hour window is the shortest any of these providers publishes, so a day
#: is comfortably long enough to still be worth showing and short enough that
#: nothing months old is presented as current.
STALE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class LimitWindow:
    """One limit the provider stated, exactly as stated."""

    #: The provider's own name for it where it gives one, else the duration.
    label: str
    #: How much of the window is spent, 0–100.
    used_percent: float
    #: The window's length in minutes, when the provider says.
    window_minutes: int | None
    #: When it refreshes, as an ISO-8601 instant, when the provider says.
    resets_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "used_percent": self.used_percent,
            "window_minutes": self.window_minutes,
            "resets_at": self.resets_at,
        }


@dataclass(frozen=True)
class SubscriptionLimits:
    """Everything one provider volunteered, and when."""

    windows: tuple[LimitWindow, ...]
    observed_at: str

    def is_stale(self, now: datetime | None = None) -> bool:
        moment = _parse(self.observed_at)
        if moment is None:
            return True
        return (now or datetime.now(UTC)) - moment > STALE_AFTER

    def to_dict(self, now: datetime | None = None) -> dict[str, Any]:
        return {
            "windows": [window.to_dict() for window in self.windows],
            "observed_at": self.observed_at,
            "stale": self.is_stale(now),
            # Named so a reader of the API can tell this apart from the usage
            # API: this was volunteered, not fetched.
            "source": "provider_turn",
        }


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _percent(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0 or number > 100:  # NaN, or out of range
        return None
    return round(number, 2)


def _minutes(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if 0 < number <= 60 * 24 * 400 else None


def _label(window_minutes: int | None, fallback: str) -> str:
    """Name a window the way a person would say it."""
    if window_minutes is None:
        return fallback
    if window_minutes % (60 * 24 * 7) == 0:
        weeks = window_minutes // (60 * 24 * 7)
        return "Weekly" if weeks == 1 else f"Every {weeks} weeks"
    if window_minutes % (60 * 24) == 0:
        days = window_minutes // (60 * 24)
        return "Daily" if days == 1 else f"Every {days} days"
    if window_minutes % 60 == 0:
        hours = window_minutes // 60
        return "Hourly" if hours == 1 else f"{hours}-hour"
    return f"{window_minutes}-minute"


def parse_windows(raw: object, *, now: datetime | None = None) -> tuple[LimitWindow, ...]:
    """Read whatever limit windows a turn's payload actually contains.

    Accepts the two shapes these servers use — a mapping of named windows
    (``primary``/``secondary``) and a plain list — and both spellings of every
    key, because one server writes ``used_percent`` and another writes
    ``usedPercent``. Anything it cannot read is left out rather than guessed.
    """
    moment = now or datetime.now(UTC)
    if isinstance(raw, Mapping):
        candidates = [(str(key), value) for key, value in raw.items()]
    elif isinstance(raw, list):
        candidates = [("", value) for value in raw]
    else:
        return ()

    windows: list[LimitWindow] = []
    for key, value in candidates:
        if not isinstance(value, Mapping):
            continue
        used = _percent(value.get("used_percent", value.get("usedPercent")))
        if used is None:
            # A window with no stated usage says nothing worth showing.
            continue
        minutes = _minutes(value.get("window_minutes", value.get("windowMinutes")))
        resets_in = _minutes_from_seconds(
            value.get("resets_in_seconds", value.get("resetsInSeconds"))
        )
        resets_at = None
        if resets_in is not None:
            resets_at = (
                (moment + timedelta(seconds=resets_in))
                .astimezone(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        stated = value.get("label", value.get("name"))
        label = str(stated) if isinstance(stated, str) and stated else _label(minutes, key or "Limit")
        windows.append(
            LimitWindow(
                label=label,
                used_percent=used,
                window_minutes=minutes,
                resets_at=resets_at,
            )
        )
    # Shortest window first: it is the one about to bite.
    return tuple(
        sorted(windows, key=lambda window: (window.window_minutes is None, window.window_minutes or 0))
    )


def _minutes_from_seconds(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 60 * 60 * 24 * 400 else None


class SubscriptionLimitStore:
    """The last window each provider volunteered, per owner and profile.

    One row per profile, overwritten: this is a *current* reading, not a
    history. The audit log already records what each turn did; keeping a series
    of percentages here would add a second, weaker record of the same thing.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store
        self._ensure()

    def _ensure(self) -> None:
        with self._store.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_limit_windows (
                    owner_principal_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    windows_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY (owner_principal_id, profile_id)
                )
                """
            )

    def record(
        self,
        owner_principal_id: str,
        profile_id: str,
        windows: tuple[LimitWindow, ...],
        *,
        observed_at: str | None = None,
    ) -> None:
        """Store what the provider said. An empty reading is not stored.

        Nothing is the honest answer for a provider that reports nothing, and
        writing an empty row would replace a real earlier reading with silence.
        """
        if not windows:
            return
        payload = json.dumps([window.to_dict() for window in windows], separators=(",", ":"))
        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_limit_windows
                    (owner_principal_id, profile_id, windows_json, observed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, profile_id) DO UPDATE SET
                    windows_json = excluded.windows_json,
                    observed_at = excluded.observed_at
                """,
                (owner_principal_id, profile_id, payload, observed_at or utc_now()),
            )

    def latest(self, owner_principal_id: str, profile_id: str) -> SubscriptionLimits | None:
        with self._store.connect() as connection:
            row = connection.execute(
                "SELECT windows_json, observed_at FROM provider_limit_windows "
                "WHERE owner_principal_id = ? AND profile_id = ?",
                (owner_principal_id, profile_id),
            ).fetchone()
        if row is None:
            return None
        try:
            raw = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(raw, list):
            return None
        windows: list[LimitWindow] = []
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            used = _percent(entry.get("used_percent"))
            if used is None:
                continue
            windows.append(
                LimitWindow(
                    label=str(entry.get("label", "Limit")),
                    used_percent=used,
                    window_minutes=_minutes(entry.get("window_minutes")),
                    resets_at=(
                        str(entry["resets_at"]) if entry.get("resets_at") is not None else None
                    ),
                )
            )
        if not windows:
            return None
        return SubscriptionLimits(windows=tuple(windows), observed_at=str(row[1]))

    def forget(self, owner_principal_id: str, profile_id: str) -> None:
        """Drop a reading — used when a subscription is disconnected."""
        with self._store.connect() as connection:
            connection.execute(
                "DELETE FROM provider_limit_windows "
                "WHERE owner_principal_id = ? AND profile_id = ?",
                (owner_principal_id, profile_id),
            )
