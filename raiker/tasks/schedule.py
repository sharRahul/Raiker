"""When a repeating task runs next, in the zone its owner chose (UX-TASK-02).

The scheduler used to step every cadence as a fixed number of seconds from the
slot before. That is right for "every twenty minutes" and "hourly", and wrong for
anything an owner reads off a wall clock: "daily at 09:00" became 10:00 the
morning after the clocks went back, and stayed there until spring. A person who
picked 09:00 picked 09:00 *where they live*, not 08:00 UTC.

So a schedule now carries three facts the old one did not:

* **its zone** — the IANA name the owner composed it in;
* **its anchor** — the first slot they picked, which every later slot is counted
  from, so a slot that DST pushed sideways does not drag the rest with it;
* **its bounds and its missed-run policy** — when it stops, and what a host that
  was asleep through a slot does about it.

Calendar cadences (daily, weekly, weekdays) step in local calendar days and keep
the local time of day. Interval cadences (continuous, hourly) stay absolute,
because "an hour from now" across a clock change is still an hour.

Two DST cases are decided here rather than left to arithmetic, and the Tasks
guide says the same thing to the owner:

* a local time that does not exist (the hour the clocks skip) runs at the same
  offset as before the change — 02:30 becomes 03:30 that day only;
* a local time that happens twice (the hour the clocks repeat) runs once, at the
  first of the two.

A schedule written before this existed has no zone and no anchor. It reads as
UTC anchored to its current slot, which is exactly how it behaved before, so no
existing routine moves when this ships.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Recurring cadences and the gap between one governed cycle and the next. A
# recurring task is re-armed after every cycle rather than closed, so a standing
# agent — "keep improving the landing page", "watch the build" — keeps working
# until the owner stops it. `continuous` is the shortest cadence offered: it is
# still one discrete governed turn per cycle, never an unbounded loop, so every
# cycle passes through policy, gates, and approvals exactly like a typed prompt.
#
# Telemetry delivery reads the same table as plain intervals; tasks read
# `daily` and `weekly` through `CALENDAR_STEP_DAYS` instead, below.
CONTINUOUS_INTERVAL = timedelta(minutes=20)
RECURRING_INTERVALS: dict[str, timedelta] = {
    "continuous": CONTINUOUS_INTERVAL,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}

#: Cadences a task steps in local calendar days, keeping its local time of day.
#: `weekdays` steps one day at a time and lands only on Monday to Friday.
CALENDAR_STEP_DAYS: dict[str, int] = {"daily": 1, "weekly": 7, "weekdays": 1}

#: Every cadence that re-arms a task after a cycle.
TASK_REPEATING = frozenset({*RECURRING_INTERVALS, *CALENDAR_STEP_DAYS})

#: What a routine does about a slot that passed while the host was not running.
#: ``run_once`` runs one late cycle and skips the rest — the behaviour every
#: routine had before this was a choice, and so the default. ``skip`` runs
#: nothing late: the routine waits for its next slot.
MISSED_RUN_POLICIES = ("run_once", "skip")
DEFAULT_MISSED_RUN_POLICY = "run_once"

#: How late a slot may be claimed and still count as on time. The host ticks
#: far more often than this; a slot claimed later than it was missed.
MISSED_RUN_GRACE = timedelta(minutes=15)

_MAX_STEPS = 800


def is_repeating(recurrence: str | None) -> bool:
    """Whether a task with this cadence re-arms after a cycle."""
    return (recurrence or "") in TASK_REPEATING


def zone(name: str | None) -> ZoneInfo:
    """The zone a schedule is read in. No name, or one this host lacks, is UTC."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def valid_zone(name: str) -> bool:
    """Whether *name* is an IANA zone this host can read."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def parse_instant(iso: str) -> datetime:
    """An ISO instant as an aware UTC datetime. A naive one is read as UTC."""
    value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_instant(value: datetime) -> str:
    """The wire form every task timestamp already uses."""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def next_occurrence(
    anchor_iso: str, recurrence: str, tz_name: str | None, after: datetime
) -> datetime:
    """The first slot of this schedule strictly after *after*.

    Every slot is counted from the anchor rather than from the slot before, so a
    run that DST moved, or one that ran late, never shifts the ones after it.
    Slots that have already passed are skipped rather than owed: a host that was
    asleep for a week does not wake up owing seven identical cycles.
    """
    anchor = parse_instant(anchor_iso)
    after = after.astimezone(UTC)
    interval = None if recurrence in CALENDAR_STEP_DAYS else RECURRING_INTERVALS.get(recurrence)
    if interval is not None:
        if anchor > after:
            return anchor
        steps = int((after - anchor) / interval) + 1
        candidate = anchor + interval * steps
        while candidate <= after:
            candidate += interval
        return candidate
    step_days = CALENDAR_STEP_DAYS.get(recurrence)
    if step_days is None:
        raise ValueError(f"not_a_repeating_cadence:{recurrence}")
    tz = zone(tz_name)
    local_anchor = anchor.astimezone(tz)
    wall = local_anchor.time().replace(tzinfo=None, fold=0)
    day = local_anchor.date()
    after_day = after.astimezone(tz).date()
    if after_day > day:
        # Jump close to *after* rather than walking from the anchor one step at
        # a time: a weekly routine a year old is fifty-two steps, not one.
        whole = (after_day - day).days // step_days
        day = day + timedelta(days=max(0, whole - 1) * step_days)
    for _ in range(_MAX_STEPS):
        if recurrence != "weekdays" or day.weekday() < 5:
            candidate = _local_slot(day, wall, tz)
            if candidate > after:
                return candidate
        day += timedelta(days=step_days)
    raise ValueError("schedule_has_no_next_slot")


def first_slot(anchor_iso: str, recurrence: str, tz_name: str | None) -> datetime:
    """The first slot at or after the anchor — a weekday schedule anchored on a
    Saturday first runs on the Monday, at the time the owner picked."""
    anchor = parse_instant(anchor_iso)
    if recurrence not in CALENDAR_STEP_DAYS:
        return anchor
    return next_occurrence(anchor_iso, recurrence, tz_name, anchor - timedelta(seconds=1))


def _local_slot(day: date, wall: object, tz: ZoneInfo) -> datetime:
    """A local date and wall time as a UTC instant, DST decided as documented.

    ``fold=0`` takes the first of a repeated hour. A wall time inside the hour
    the clocks skip does not exist; reading it with the offset that applied
    before the change is what moves it forward by the size of the gap.
    """
    local = datetime.combine(day, wall, tzinfo=tz)  # type: ignore[arg-type]
    return local.astimezone(UTC)


def missed(scheduled_at: str, now: datetime) -> bool:
    """Whether a slot claimed at *now* was missed rather than merely claimed."""
    return now.astimezone(UTC) - parse_instant(scheduled_at) > MISSED_RUN_GRACE


@dataclass(frozen=True)
class ScheduleTerms:
    """A schedule's terms as they will be stored, validated together."""

    first_run: str | None
    anchor: str | None
    timezone: str | None
    until: str | None
    missed_run_policy: str | None


def schedule_terms(
    *,
    recurrence: str | None,
    scheduled_at: str | None,
    timezone: str | None,
    run_until: str | None,
    missed_runs: str | None,
) -> ScheduleTerms:
    """Validate and normalise what a new task says about when it runs.

    An end or a missed-run policy on a task that does not repeat is refused
    rather than stored: it would be a promise nothing ever reads. A zone is kept
    on any scheduled task, so a one-off's card can say which 09:00 it meant.
    """
    tz_name = (timezone or "").strip() or None
    if tz_name is not None and not valid_zone(tz_name):
        raise ValueError(f"invalid_timezone:{tz_name}")
    repeating = is_repeating(recurrence)
    if not repeating and (run_until or missed_runs):
        raise ValueError("schedule_terms_need_a_repeating_task")
    if missed_runs is not None and missed_runs not in MISSED_RUN_POLICIES:
        raise ValueError(f"invalid_missed_run_policy:{missed_runs}")
    if not repeating or scheduled_at is None:
        return ScheduleTerms(None, None, tz_name if scheduled_at else None, None, None)
    try:
        anchor = format_instant(parse_instant(scheduled_at))
        until = format_instant(parse_instant(run_until)) if run_until else None
    except ValueError as exc:
        raise ValueError("invalid_schedule_time") from exc
    first = format_instant(first_slot(anchor, recurrence or "", tz_name))
    if until is not None and parse_instant(until) < parse_instant(first):
        raise ValueError("schedule_ends_before_first_run")
    return ScheduleTerms(
        first_run=first,
        anchor=anchor,
        timezone=tz_name,
        until=until,
        missed_run_policy=missed_runs or DEFAULT_MISSED_RUN_POLICY,
    )
