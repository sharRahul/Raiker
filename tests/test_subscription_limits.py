"""BUG-254 — what a subscription says is left, in the provider's own words.

The rule under test is the one that keeps this honest: read only what the
provider volunteers as part of a turn, never poll a portal, and never infer. So
the tests that matter most are the ones asserting what is *not* produced — a
provider that says nothing leaves nothing, and a malformed field is dropped
rather than guessed at.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.models.subscription_limits import (
    LimitWindow,
    SubscriptionLimitStore,
    parse_windows,
)
from raiker.storage.sqlite import SQLiteStore

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


def test_a_turns_named_windows_are_read_shortest_first() -> None:
    windows = parse_windows(
        {
            "secondary": {"used_percent": 12, "window_minutes": 10080, "resets_in_seconds": 3600},
            "primary": {"used_percent": 68.4, "window_minutes": 300},
        },
        now=NOW,
    )
    # Shortest first: it is the one about to bite.
    assert [window.label for window in windows] == ["5-hour", "Weekly"]
    assert windows[0].used_percent == 68.4
    assert windows[0].resets_at is None
    assert windows[1].resets_at == "2026-09-03T13:00:00Z"


def test_both_spellings_are_read_because_both_are_sent() -> None:
    windows = parse_windows([{"usedPercent": 5, "windowMinutes": 60, "resetsInSeconds": 60}])
    assert len(windows) == 1
    assert windows[0].label == "Hourly"


def test_a_provider_that_says_nothing_leaves_nothing() -> None:
    assert parse_windows(None) == ()
    assert parse_windows({}) == ()
    assert parse_windows("68%") == ()
    # A window with no stated usage is not a window worth showing.
    assert parse_windows({"primary": {"window_minutes": 300}}) == ()


def test_one_malformed_field_does_not_take_the_reading_with_it() -> None:
    windows = parse_windows(
        {
            "primary": {"used_percent": 42, "window_minutes": "not-a-number"},
            "broken": {"used_percent": 250},
            "also_broken": {"used_percent": True},
        }
    )
    assert len(windows) == 1
    assert windows[0].used_percent == 42
    # Unreadable, so left out rather than guessed.
    assert windows[0].window_minutes is None


def test_a_reading_is_stored_and_read_back_whole(store: SQLiteStore) -> None:
    limits = SubscriptionLimitStore(store)
    limits.record(
        "prin_owner",
        "prof_chatgpt",
        parse_windows({"primary": {"used_percent": 68.4, "window_minutes": 300}}, now=NOW),
        observed_at="2026-09-03T12:00:00Z",
    )
    read = limits.latest("prin_owner", "prof_chatgpt")
    assert read is not None
    assert read.windows[0].label == "5-hour"
    assert read.windows[0].used_percent == 68.4
    assert read.is_stale(NOW) is False
    assert read.to_dict(NOW)["source"] == "provider_turn"


def test_an_old_reading_says_it_is_old_rather_than_passing_as_current(
    store: SQLiteStore,
) -> None:
    limits = SubscriptionLimitStore(store)
    limits.record(
        "prin_owner",
        "prof_chatgpt",
        (LimitWindow(label="Weekly", used_percent=10, window_minutes=10080, resets_at=None),),
        observed_at="2026-09-01T12:00:00Z",
    )
    read = limits.latest("prin_owner", "prof_chatgpt")
    assert read is not None
    assert read.is_stale(NOW) is True
    assert read.is_stale(NOW - timedelta(days=2)) is False


def test_an_empty_reading_never_replaces_a_real_one(store: SQLiteStore) -> None:
    limits = SubscriptionLimitStore(store)
    limits.record(
        "prin_owner",
        "prof_chatgpt",
        (LimitWindow(label="Weekly", used_percent=10, window_minutes=10080, resets_at=None),),
    )
    limits.record("prin_owner", "prof_chatgpt", ())
    read = limits.latest("prin_owner", "prof_chatgpt")
    assert read is not None, "silence must not overwrite what the provider did say"
    assert read.windows[0].used_percent == 10


def test_nothing_is_reported_for_a_profile_that_never_spoke(store: SQLiteStore) -> None:
    assert SubscriptionLimitStore(store).latest("prin_owner", "prof_never") is None


def test_readings_do_not_leak_between_owners(store: SQLiteStore) -> None:
    limits = SubscriptionLimitStore(store)
    limits.record(
        "prin_a",
        "prof_chatgpt",
        (LimitWindow(label="Weekly", used_percent=90, window_minutes=10080, resets_at=None),),
    )
    assert limits.latest("prin_b", "prof_chatgpt") is None


def test_disconnecting_forgets_what_the_subscription_said(store: SQLiteStore) -> None:
    limits = SubscriptionLimitStore(store)
    limits.record(
        "prin_owner",
        "prof_chatgpt",
        (LimitWindow(label="Weekly", used_percent=10, window_minutes=10080, resets_at=None),),
    )
    limits.forget("prin_owner", "prof_chatgpt")
    assert limits.latest("prin_owner", "prof_chatgpt") is None
