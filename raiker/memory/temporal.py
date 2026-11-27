"""The time leg of recall, after Hindsight's temporal search.

Hindsight runs four searches in parallel: meaning, keywords, the entity graph
and *time*. Raiker had the first three. A question such as "what did I tell you
last week?" shares no word with the memory it wants, so only its time can find
it. This reads the few time phrases people actually use and turns them into a
window of when a memory was learned; deterministic, no model call, and silent
when the query names no time.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

_MONTHS = {
    name: index
    for index, names in enumerate(
        (
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_LAST_N = re.compile(r"\b(?:last|past)\s+(\d{1,3})\s+(day|week|month)s?\b")
_IN_MONTH = re.compile(r"\b(?:in|during|from)\s+(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b")
_ISO_DAY = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_ISO_MONTH = re.compile(r"\b(\d{4})-(\d{2})\b")


def _day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_window(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC)
    return start, end


def query_window(query: str, now: datetime | None = None) -> tuple[datetime, datetime] | None:
    """The ``[start, end)`` a query's time phrase names, or ``None``."""
    text = query.lower()
    now = now or datetime.now(UTC)
    today = _day(now)
    if match := _ISO_DAY.search(text):
        try:
            start = datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=UTC)
        except ValueError:
            return None
        return start, start + timedelta(days=1)
    if (match := _ISO_MONTH.search(text)) and 1 <= int(match[2]) <= 12:
        return _month_window(int(match[1]), int(match[2]))
    if match := _LAST_N.search(text):
        count = int(match[1])
        days = {"day": 1, "week": 7, "month": 30}[match[2]] * count
        return today - timedelta(days=days), now
    if "yesterday" in text:
        return today - timedelta(days=1), today
    if re.search(r"\btoday\b", text):
        return today, now
    if re.search(r"\bthis week\b", text):
        return today - timedelta(days=today.weekday()), now
    if re.search(r"\blast week\b", text):
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=7)
    if re.search(r"\bthis month\b", text):
        return _month_window(now.year, now.month)[0], now
    if re.search(r"\blast month\b", text):
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        return _month_window(year, month)
    if re.search(r"\b(recently|lately|the other day)\b", text):
        return today - timedelta(days=14), now
    if match := _IN_MONTH.search(text):
        month = _MONTHS[match[1]]
        year = now.year if month <= now.month else now.year - 1
        return _month_window(year, month)
    return None


def in_window(created_at: str, window: tuple[datetime, datetime]) -> bool:
    try:
        moment = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return window[0] <= moment < window[1]
