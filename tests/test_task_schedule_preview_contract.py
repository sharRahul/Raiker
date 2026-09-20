"""REM-TASK-01 — the schedule preview is the scheduler's arithmetic, or it lies.

The task composer shows an owner the next runs a repeating schedule would
produce, so a cadence and a first run stop being two abstractions and become
three timestamps they can check. That preview is computed in the browser, and a
browser cannot import :mod:`raiker.tasks.scheduler` — so the intervals are
written down a second time in ``web/src/lib/taskComposer.ts``.

This is the check that keeps the second copy honest. It reads the web module
rather than duplicating its numbers, so a cadence added or re-timed on one side
and not the other fails here instead of on an owner's calendar.
"""
from __future__ import annotations

import re
from pathlib import Path

from raiker.tasks.scheduler import RECURRING_INTERVALS

TASK_COMPOSER = Path("web/src/lib/taskComposer.ts")

_TABLE = re.compile(
    r"export const RECURRENCE_INTERVAL_MS: Record<string, number> = \{(.*?)\};", re.S
)
_ENTRY = re.compile(r"^\s*([a-z_]+):\s*([0-9_ *+]+),", re.M)


def _preview_intervals() -> dict[str, float]:
    """``{cadence: seconds}`` as the composer's preview declares them."""
    body = _TABLE.search(TASK_COMPOSER.read_text(encoding="utf-8"))
    assert body is not None, "The preview's interval table is not where the test expects it."
    entries: dict[str, float] = {}
    for name, expression in _ENTRY.findall(body.group(1)):
        # Arithmetic only — `20 * 60_000` — so it is read rather than executed.
        assert re.fullmatch(r"[0-9_ *+]+", expression), expression
        entries[name] = eval(expression.replace("_", "")) / 1000  # noqa: S307
    return entries


def test_the_preview_offers_exactly_the_cadences_the_scheduler_honours() -> None:
    assert set(_preview_intervals()) == set(RECURRING_INTERVALS)


def test_every_previewed_run_is_spaced_the_way_the_scheduler_spaces_it() -> None:
    preview = _preview_intervals()
    for cadence, interval in RECURRING_INTERVALS.items():
        assert preview[cadence] == interval.total_seconds(), cadence
