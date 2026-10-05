"""When a notice may interrupt the owner, decided once, on the server (DEC-21a).

Quiet hours are an *attention* preference, not a permission decision. They
decide whether a notice is put in front of the owner — the docked notice inside
Raiker, the browser's desktop notification, the owner-configured OS command —
and never whether it is recorded, whether an approval waits, or whether work
runs. The bell, the record and the approval queue are untouched by anything
here.

The decision is made **at the moment a notice is written** and stored on its
row (``in_app_presentation`` / ``desktop_presentation``), apart from ``read``.
That is the property a browser timer could not give: every tab, a restart and
the OS command read the same answer, and a notice held for quiet hours is not
replayed as a toast when a second tab opens at 07:01. What is offered instead,
once the interval is over, is one summary of the held notices that are still
relevant (:func:`held_notifications`), acknowledged on the server so it is
offered once.

Three rules the owner accepted on 2026-10-05 (DEC-21a), and where they hold:

* **Opt-in.** Nothing is quiet until the owner turns quiet hours on; an
  existing account gets no invented schedule (:data:`DEFAULTS`).
* **Critical exceptions are off by default and enumerated.** Only the kinds in
  :data:`CRITICAL_KINDS` — security findings and containment — can break quiet
  hours, and only on a channel the owner switched the exception on for. The
  set is the kind a *subsystem* wrote, never a word in a title: a model that
  writes "URGENT" into a task title changes nothing here.
* **Muting a category is not approving.** Decisions (approvals) cannot be
  muted outside quiet hours: they hold work up, and the switch that would hide
  them is the switch that makes work stall unseen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

Presentation = Literal["interrupt", "critical_exception", "quiet_hours", "muted"]

#: The presentations that put a notice in front of the owner. Anything else is
#: recorded and counted by the bell, and nothing more.
INTERRUPTING: frozenset[str] = frozenset({"interrupt", "critical_exception"})

ENABLED_KEY = "notification.quiet_hours.enabled"
START_KEY = "notification.quiet_hours.start"
END_KEY = "notification.quiet_hours.end"
TIMEZONE_KEY = "notification.quiet_hours.timezone"
CRITICAL_IN_APP_KEY = "notification.quiet_hours.critical_in_app"
CRITICAL_DESKTOP_KEY = "notification.quiet_hours.critical_desktop"

#: What an account that has never touched these settings reads. Quiet hours
#: off and both exceptions off is the accepted upgrade behaviour: nothing an
#: owner relied on before this change is suppressed by it.
DEFAULTS: dict[str, Any] = {
    ENABLED_KEY: False,
    START_KEY: "22:00",
    END_KEY: "07:00",
    CRITICAL_IN_APP_KEY: False,
    CRITICAL_DESKTOP_KEY: False,
}

#: Security findings and containment — the enumerated critical events. A kind
#: is written by the subsystem that raised the notice (`security/monitoring`,
#: `security/containment`, `security/mcp_monitor`, `approval_notifier`), so
#: nothing a model says can add to this set.
CRITICAL_KINDS: frozenset[str] = frozenset(
    {"security_alert", "anomaly", "capability_contained", "integrity_deviation"}
)

#: Which owner-facing group each kind belongs to. A category the owner can
#: mute has an entry in :data:`MUTABLE_CATEGORIES`; an unknown kind is
#: ``other``, which interrupts outside quiet hours and is never critical.
CATEGORIES: dict[str, str] = {
    "approval_pending": "decisions",
    "critical_approval_pending": "decisions",
    "task_finished": "work",
    "task_paused": "work",
    "telemetry_delivery": "work",
    "security_alert": "security",
    "security_recovered": "security",
    "anomaly": "security",
    "capability_contained": "security",
    "capability_resumed": "security",
    "integrity_deviation": "security",
    "mcp_tools_held": "extensions",
    "connection_resumed": "extensions",
    "test_notice": "test",
    "search_index_damaged": "work",
}

#: The categories with an *Interrupt me* switch, and what each is called. Not
#: ``decisions`` (see the module docstring) and not ``test`` — a test notice
#: that a preference silently swallowed would test nothing.
MUTABLE_CATEGORIES: dict[str, str] = {
    "work": "Background work finished or paused",
    "security": "Security findings and containment",
    "extensions": "Extensions and MCP servers",
}


def instant(moment: datetime) -> str:
    """``moment`` in the store's timestamp shape, so stored instants compare as text."""
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def category_key(category: str) -> str:
    return f"notification.interrupt.{category}"


def category_of(kind: str) -> str:
    return CATEGORIES.get(kind, "other")


_CLOCK = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_clock(value: object) -> time | None:
    if not isinstance(value, str):
        return None
    match = _CLOCK.match(value.strip())
    if match is None:
        return None
    return time(int(match.group(1)), int(match.group(2)))


def _zone(name: object) -> ZoneInfo | None:
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def validate(settings: dict[str, Any]) -> str | None:
    """The reason code a settings save is refused for, or ``None``.

    Only the keys this module owns are read, and only when present: a save
    from a page that never heard of quiet hours is unaffected.
    """
    for key in (ENABLED_KEY, CRITICAL_IN_APP_KEY, CRITICAL_DESKTOP_KEY):
        if key in settings and not isinstance(settings[key], bool):
            return "invalid_quiet_hours_switch"
    for key in MUTABLE_CATEGORIES:
        if category_key(key) in settings and not isinstance(settings[category_key(key)], bool):
            return "invalid_interrupt_switch"
    for key in (START_KEY, END_KEY):
        if key in settings and _parse_clock(settings[key]) is None:
            return "invalid_quiet_hours_time"
    if START_KEY in settings or END_KEY in settings:
        start = _parse_clock(settings.get(START_KEY, DEFAULTS[START_KEY]))
        end = _parse_clock(settings.get(END_KEY, DEFAULTS[END_KEY]))
        if start == end:
            # Zero length is not "always quiet" and not "never": it is a
            # schedule with no meaning, refused rather than guessed at.
            return "quiet_hours_empty"
    if (
        TIMEZONE_KEY in settings
        and settings[TIMEZONE_KEY] not in (None, "")
        and _zone(settings[TIMEZONE_KEY]) is None
    ):
        return "invalid_quiet_hours_timezone"
    return None


def _resolve_wall(candidate: datetime, zone: ZoneInfo) -> datetime:
    """The instant a local wall-clock reading names, including one that does not exist.

    A reading inside a spring-forward gap has no instant of its own; it is
    resolved to the instant the clock jumps over it — the first moment the
    owner's clock reads that time or later. A repeated reading (autumn) is its
    first occurrence (``fold=0``).
    """
    first = candidate.replace(fold=0).astimezone(UTC)
    if first.astimezone(zone).replace(tzinfo=None) == candidate.replace(tzinfo=None):
        return first
    # In a gap: fold=1 reads it with the offset after the jump, which lands
    # before the jump; step forward to the jump itself.
    moment = candidate.replace(fold=1).astimezone(UTC).replace(second=0, microsecond=0)
    wall = candidate.replace(tzinfo=None)
    for _ in range(0, 24 * 60):
        if moment.astimezone(zone).replace(tzinfo=None) >= wall:
            return moment
        moment += timedelta(minutes=1)
    return first


@dataclass(frozen=True)
class QuietHours:
    """The owner's quiet-hours terms, read from settings with the defaults."""

    enabled: bool
    start: time
    end: time
    timezone: str
    critical_in_app: bool
    critical_desktop: bool

    @classmethod
    def from_settings(cls, settings: dict[str, Any], fallback_zone: str) -> QuietHours:
        def flag(key: str) -> bool:
            value = settings.get(key, DEFAULTS[key])
            return value if isinstance(value, bool) else bool(DEFAULTS[key])

        start = _parse_clock(settings.get(START_KEY)) or _parse_clock(DEFAULTS[START_KEY])
        end = _parse_clock(settings.get(END_KEY)) or _parse_clock(DEFAULTS[END_KEY])
        assert start is not None and end is not None
        zone_name = settings.get(TIMEZONE_KEY)
        timezone = (
            str(zone_name).strip() if _zone(zone_name) is not None else fallback_zone
        )
        return cls(
            enabled=flag(ENABLED_KEY) and start != end,
            start=start,
            end=end,
            timezone=timezone,
            critical_in_app=flag(CRITICAL_IN_APP_KEY),
            critical_desktop=flag(CRITICAL_DESKTOP_KEY),
        )

    def _zoneinfo(self) -> ZoneInfo:
        return _zone(self.timezone) or ZoneInfo("UTC")

    def _within(self, wall: time) -> bool:
        if self.start < self.end:
            return self.start <= wall < self.end
        # Overnight, e.g. 22:00 → 07:00.
        return wall >= self.start or wall < self.end

    def active(self, now: datetime) -> bool:
        """True when ``now`` falls inside the interval, on the owner's wall clock.

        Wall clock on purpose: a quiet hour that starts at 22:00 starts at 22:00
        on both sides of a DST change, which is what the owner set.
        """
        if not self.enabled:
            return False
        wall = now.astimezone(self._zoneinfo()).time().replace(tzinfo=None)
        return self._within(wall)

    def _next_wall(self, now: datetime, wall: time) -> datetime:
        """The next instant after ``now`` at which the owner's clock reads ``wall``.

        A wall time inside a spring-forward gap does not exist; it resolves to
        the instant the clock jumps past it. A repeated autumn hour resolves to
        its first occurrence. Both are the reading a person would give.
        """
        zone = self._zoneinfo()
        local_today: date = now.astimezone(zone).date()
        for offset in range(0, 3):
            candidate = datetime.combine(local_today + timedelta(days=offset), wall, tzinfo=zone)
            moment = _resolve_wall(candidate, zone)
            if moment > now.astimezone(UTC):
                return moment
        return (now + timedelta(days=1)).astimezone(UTC)

    def ends_at(self, now: datetime) -> datetime | None:
        """When the current interval ends, or ``None`` outside one."""
        return self._next_wall(now, self.end) if self.active(now) else None

    def next_starts_at(self, now: datetime) -> datetime | None:
        """When the next interval starts, or ``None`` when quiet hours are off/active."""
        if not self.enabled or self.active(now):
            return None
        return self._next_wall(now, self.start)


@dataclass(frozen=True)
class PresentationDecision:
    """What one notice may do, per channel, decided when it was written."""

    in_app: Presentation
    desktop: Presentation
    #: The end of the quiet interval a held notice waits for. ``None`` unless at
    #: least one channel is ``quiet_hours``.
    quiet_until: str | None


def interrupts_enabled(settings: dict[str, Any], category: str) -> bool:
    if category not in MUTABLE_CATEGORIES:
        return True
    value = settings.get(category_key(category), True)
    return value if isinstance(value, bool) else True


def decide(
    settings: dict[str, Any], *, kind: str, now: datetime, fallback_zone: str
) -> PresentationDecision:
    """The one delivery policy. Test notices and real ones both come through here."""
    category = category_of(kind)
    if not interrupts_enabled(settings, category):
        return PresentationDecision("muted", "muted", None)
    quiet = QuietHours.from_settings(settings, fallback_zone)
    if not quiet.active(now):
        return PresentationDecision("interrupt", "interrupt", None)
    critical = kind in CRITICAL_KINDS
    in_app: Presentation = (
        "critical_exception" if critical and quiet.critical_in_app else "quiet_hours"
    )
    desktop: Presentation = (
        "critical_exception" if critical and quiet.critical_desktop else "quiet_hours"
    )
    ends = quiet.ends_at(now)
    held = "quiet_hours" in (in_app, desktop)
    return PresentationDecision(
        in_app, desktop, instant(ends) if held and ends else None
    )


def interrupts(presentation: str | None) -> bool:
    """True when a stored presentation lets a notice interrupt.

    ``None`` is a row written before this policy existed; it keeps the
    behaviour it was written under, which was to interrupt.
    """
    return presentation is None or presentation in INTERRUPTING
