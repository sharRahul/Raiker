"""Several keys for one provider, rotated on rate limits and empty quota.

A provider connection may hold backup keys,
and a request whose key is rate limited (429) or out of quota moves to the next
key instead of failing the turn. A key that was refused is *benched* for a
while — a minute for a rate limit, an hour for an empty balance — so the next
request does not spend a round trip proving it again.

The bench is process state, not stored: a restart forgets it, which costs at
most one refused request per benched key. Nothing here ever reads or reports a
key's value; keys are referred to by their position (1 is the primary).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

#: Connection fields holding keys, primary first. Backups are optional.
KEY_FIELDS: tuple[str, ...] = ("api_key", "api_key_2", "api_key_3", "api_key_4")
BACKUP_KEY_FIELDS: tuple[str, ...] = KEY_FIELDS[1:]

#: How long a refused key sits out, by reason.
BENCH_SECONDS: dict[str, float] = {
    "rate_limited": 60.0,
    "quota_exhausted": 3600.0,
}


@dataclass(frozen=True)
class Bench:
    until: float
    reason: str


_lock = threading.Lock()
_benched: dict[tuple[str, int], Bench] = {}
_last_used: dict[str, int] = {}


def pooled_keys(connection: dict[str, str] | None) -> list[tuple[int, str]]:
    """``[(position, key), ...]`` for every key the connection holds, primary first."""
    values = connection or {}
    return [
        (position, values[field].strip())
        for position, field in enumerate(KEY_FIELDS, start=1)
        if values.get(field, "").strip()
    ]


def backup_count(connection: dict[str, str] | None) -> int:
    return max(0, len(pooled_keys(connection)) - 1)


def bench(profile_id: str, position: int, reason: str, *, now: float | None = None) -> None:
    clock = time.monotonic() if now is None else now
    with _lock:
        _benched[(profile_id, position)] = Bench(clock + BENCH_SECONDS.get(reason, 60.0), reason)


def attempt_order(
    profile_id: str, connection: dict[str, str] | None, *, now: float | None = None
) -> list[tuple[int, dict[str, str]]]:
    """The connections to try, one per key: rested keys in order, then the benched.

    Benched keys come last, soonest-rested first, so a pool whose every key is
    benched still makes one honest attempt rather than refusing without asking.
    A connection with one key (or none) is returned unchanged, once.
    """
    keys = pooled_keys(connection)
    if len(keys) <= 1:
        return [(1, dict(connection or {}))]
    clock = time.monotonic() if now is None else now
    with _lock:
        rested = [(p, k) for p, k in keys if _rest(profile_id, p, clock)]
        benched = sorted(
            ((p, k) for p, k in keys if not _rest(profile_id, p, clock)),
            key=lambda item: _benched[(profile_id, item[0])].until,
        )
    base = {key: value for key, value in (connection or {}).items() if key not in BACKUP_KEY_FIELDS}
    return [(position, {**base, "api_key": key}) for position, key in [*rested, *benched]]


def _rest(profile_id: str, position: int, clock: float) -> bool:
    held = _benched.get((profile_id, position))
    if held is None:
        return True
    if held.until <= clock:
        del _benched[(profile_id, position)]
        return True
    return False


def record_use(profile_id: str, position: int) -> None:
    with _lock:
        _last_used[profile_id] = position


def describe(profile_id: str, connection: dict[str, str] | None, *, now: float | None = None) -> str:
    """One sentence for the Models card, or ``""`` when there is nothing to say."""
    keys = pooled_keys(connection)
    if len(keys) <= 1:
        return ""
    clock = time.monotonic() if now is None else now
    with _lock:
        resting = [
            (position, _benched[(profile_id, position)])
            for position, _ in keys
            if not _rest(profile_id, position, clock)
        ]
        using = _last_used.get(profile_id)
    if not resting:
        return "" if using in (None, 1) else f"Using backup key {using}."
    text = "; ".join(
        f"key {position} {'rate limited' if held.reason == 'rate_limited' else 'out of quota'}"
        f" for about {max(1, round((held.until - clock) / 60))} min"
        for position, held in resting
    )
    if using not in (None, 1):
        return f"Using backup key {using}; {text}."
    return f"{text[0].upper()}{text[1:]}."


def forget() -> None:
    """Drop all bench and usage state. For tests."""
    with _lock:
        _benched.clear()
        _last_used.clear()
