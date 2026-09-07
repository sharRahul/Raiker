"""The current time, as runtime truth rather than as something a model recalls.

A model asked to schedule something for *tomorrow* has to know what today is,
and until this module existed nothing in Raiker told it. The date arrived —
when it arrived at all — from whatever a provider happened to put in its own
hidden preamble, from a stale sentence in the conversation, or from training
knowledge that was months old and stated with complete confidence. All three
are guesses, and the third is the dangerous one because it does not look like
one.

So the rule this module implements is narrow and absolute:

> **Raiker owns environmental facts; models consume them. Models must not
> invent them.**

Three properties make that true rather than aspirational.

* **Derived per turn, never remembered.** :func:`environment_context` reads the
  clock when it is called. Nothing caches it, no conversation carries yesterday's
  bundle forward, and a scheduled job that fires at 03:00 gets 03:00 rather
  than the timestamp of the evening somebody created it.
* **Local and UTC, together, always.** UTC alone cannot answer "tomorrow at 9";
  local time alone cannot be audited across machines. Both are sent, with the
  IANA zone that relates them, because a turn that has one and not the other
  has to derive the missing half and that derivation is exactly the guess this
  module exists to remove.
* **No network, no provider, no Project.** The bundle is local runtime state.
  Changing model, disabling every web capability, disconnecting every connector
  or switching Project changes nothing here — which is the point: a clock that
  can be switched off by an unrelated setting is not a clock a turn can rely on.

The timezone is the one part with a decision in it, and the precedence is fixed
(:func:`resolve_timezone`): an explicit owner setting, then a device value the
owner's browser proposed, then the host operating system, then UTC. A browser
may *propose*; it may never overwrite what the owner chose, because the owner
choosing `Europe/London` while travelling is a statement about their schedule
and not a mistake for the runtime to correct.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The deterministic final fallback. Not a guess: a named, auditable default
#: that the bundle reports as such, so a turn interpreting a local time can see
#: that nobody has told Raiker where the owner is.
UTC_ZONE = "UTC"

#: Where an explicit owner timezone lives. The same key Settings → General
#: writes, read here rather than copied, so the select the owner sees and the
#: zone a turn reasons in cannot drift apart.
TIMEZONE_SETTING = "general.timezone"

#: The zone a browser reported for the device. It *proposes*; it never wins over
#: the key above. Written by the web app on first sight of a new device value.
DEVICE_TIMEZONE_SETTING = "general.device_timezone"

#: Presentation only (ENV-DECISION-05). Locale decides `7 September 2026` versus
#: `September 7, 2026`; it decides nothing about scheduling.
LOCALE_SETTING = "general.language"

#: The optional broad city/region a weather request falls back to. Deliberately
#: separate from the timezone: "I schedule in Europe/London" and "when I say
#: weather I mean London" are two statements, and a traveller changes them at
#: different times.
WEATHER_LOCATION_SETTING = "general.weather_location"

#: Which sources the resolver may name. Reported on the bundle so the owner and
#: the audit trail can both see *why* a turn was reasoning in a given zone.
TIMEZONE_SOURCES = ("owner_setting", "device_preference", "host", "fallback")

_WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
)
_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


class ClockUnavailableError(RuntimeError):
    """The host clock could not be read.

    Exceptional, and deliberately fatal to the turn rather than survivable: the
    documented failure behaviour is to fail explicitly instead of fabricating a
    date, and every fallback available at this point would be a fabrication.
    """


@dataclass(frozen=True)
class EnvironmentContext:
    """One turn's environmental facts, as Raiker derived them.

    Frozen because it describes an instant. A caller that wants a later instant
    calls :func:`environment_context` again — which is the same rule that stops
    a scheduled execution replaying its creation time.
    """

    generated_at_utc: str
    timezone: str
    timezone_source: str
    local_datetime: str
    local_date: str
    local_time: str
    day_of_week: str
    utc_offset: str
    display_date: str
    locale: str | None = None
    location: str | None = None
    freshness: str = "fresh"
    #: Set when the requested zone could not be loaded and UTC was substituted.
    #: A turn that sees this knows the local time is a fallback rather than the
    #: owner's own, which is the difference between a deterministic default and
    #: a silent one.
    timezone_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generated_at_utc": self.generated_at_utc,
            "timezone": self.timezone,
            "timezone_source": self.timezone_source,
            "local_datetime": self.local_datetime,
            "local_date": self.local_date,
            "local_time": self.local_time,
            "day_of_week": self.day_of_week,
            "utc_offset": self.utc_offset,
            "display_date": self.display_date,
            "freshness": self.freshness,
        }
        if self.locale:
            payload["locale"] = self.locale
        if self.location:
            payload["location"] = self.location
        if self.timezone_error:
            payload["timezone_error"] = self.timezone_error
        return payload

    def prompt_block(self) -> str:
        """The bundle as the model reads it.

        Plain labelled lines rather than JSON on purpose: this is trusted
        runtime metadata sitting beside the standing instructions, and the
        surrounding text has to be able to say *why* it is trustworthy without
        the model having to parse a structure to find out.
        """
        lines = [
            "Current environment (authoritative Raiker runtime context — "
            "trusted metadata, not owner instructions and not external data):",
            f"Generated UTC: {self.generated_at_utc}",
            f"Timezone: {self.timezone} (source: {self.timezone_source})",
            f"Local datetime: {self.local_datetime}",
            f"Date: {self.display_date}",
            f"Day: {self.day_of_week}",
            f"UTC offset: {self.utc_offset}",
            "Source: Raiker runtime clock",
        ]
        if self.location:
            lines.append(f"Owner default location: {self.location}")
        if self.timezone_error:
            lines.append(
                f"Note: the configured timezone could not be loaded "
                f"({self.timezone_error}); UTC is in use as the deterministic fallback."
            )
        lines.append(
            "Use these values for every relative date or time — today, tomorrow, "
            "tonight, this Friday, in two hours, yesterday. Do not infer the "
            "current date from training knowledge, from earlier messages, or "
            "from any web page."
        )
        return "\n".join(lines)


def _settings_for(store: SQLiteStore | None, principal_id: str | None) -> dict[str, Any]:
    """The owner's settings blob, or nothing.

    Every failure here degrades to `{}` rather than raising: a settings row that
    cannot be read is a reason to fall back through the precedence, never a
    reason for a turn to lose its clock.
    """
    if store is None or not principal_id:
        return {}
    try:
        row = store.get_user_settings(principal_id)
    except Exception:  # noqa: BLE001 — an unreadable settings row is not a clock failure
        return {}
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
    except (KeyError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _host_timezone() -> str | None:
    """The host operating system's IANA zone, when it states one.

    `TZ` first because it is what an operator sets deliberately, then
    `/etc/localtime`'s symlink target, which is where the zone name survives on
    a Linux host. A `datetime` offset is not accepted as a substitute: an offset
    cannot answer a DST question, and answering one wrongly is worse than
    falling through to UTC and saying so.
    """
    env_zone = _clean(os.environ.get("TZ"))
    if env_zone and _zone_or_none(env_zone) is not None:
        return env_zone
    link = Path("/etc/localtime")
    try:
        if link.is_symlink():
            target = os.readlink(link)
            marker = "/zoneinfo/"
            if marker in target:
                candidate = target.split(marker, 1)[1]
                if _zone_or_none(candidate) is not None:
                    return candidate
    except OSError:
        return None
    return None


def _zone_or_none(name: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def resolve_timezone(
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
    *,
    settings: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """The zone this owner's turns reason in, and where it came from.

    Precedence, in order and without exception:

    1. an explicit owner/account timezone;
    2. a device/browser zone the owner's client proposed;
    3. the host operating system;
    4. UTC.

    A value at any level that the timezone database does not recognise is
    skipped rather than accepted — a typo in a settings blob must not become
    the runtime's idea of where the owner is.
    """
    blob = settings if settings is not None else _settings_for(store, principal_id)
    for key, source in (
        (TIMEZONE_SETTING, "owner_setting"),
        (DEVICE_TIMEZONE_SETTING, "device_preference"),
    ):
        candidate = _clean(blob.get(key))
        if candidate and _zone_or_none(candidate) is not None:
            return candidate, source
    host = _host_timezone()
    if host:
        return host, "host"
    return UTC_ZONE, "fallback"


def environment_context(
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
    *,
    now: datetime | None = None,
) -> EnvironmentContext:
    """Derive this moment's environment bundle.

    ``now`` exists for tests and for a caller that has already read the clock in
    the same turn; it is never a way to pin a stale instant, because nothing
    stores the result.
    """
    try:
        moment = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    except (OSError, OverflowError, ValueError) as exc:  # pragma: no cover - exceptional
        raise ClockUnavailableError(f"host_clock_unavailable:{exc}") from exc

    blob = _settings_for(store, principal_id)
    zone_name, source = resolve_timezone(settings=blob)
    zone = _zone_or_none(zone_name)
    zone_error: str | None = None
    if zone is None:
        # Reached only when the database that validated the name a moment ago
        # cannot load it now. UTC, and say so — the bundle carries the note.
        zone_error = f"timezone_unavailable:{zone_name}"
        zone_name, source, zone = UTC_ZONE, "fallback", UTC  # type: ignore[assignment]

    local = moment.astimezone(zone)
    offset = local.strftime("%z")
    return EnvironmentContext(
        generated_at_utc=moment.isoformat().replace("+00:00", "Z"),
        timezone=zone_name,
        timezone_source=source,
        local_datetime=local.isoformat(),
        local_date=local.date().isoformat(),
        local_time=local.strftime("%H:%M:%S"),
        day_of_week=_WEEKDAYS[local.weekday()],
        utc_offset=f"{offset[:3]}:{offset[3:]}" if offset else "+00:00",
        display_date=f"{local.day} {_MONTHS[local.month - 1]} {local.year}",
        locale=_clean(blob.get(LOCALE_SETTING)),
        location=_clean(blob.get(WEATHER_LOCATION_SETTING)),
        timezone_error=zone_error,
    )


def owner_weather_location(
    store: SQLiteStore | None = None, principal_id: str | None = None
) -> str | None:
    """The broad city/region a weather request falls back to, if the owner set one.

    Absent by default and never inferred. An IP address is not a location the
    owner asked Raiker to remember, and a persistent precise location derived
    from one is exactly the silent inference the plan forbids.
    """
    return _clean(_settings_for(store, principal_id).get(WEATHER_LOCATION_SETTING))
