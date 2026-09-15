"""The runtime, not the model, is the source of the clock.

The failure these close is quiet and completely convincing: asked what day it
is, a model answers from training knowledge, from a provider's hidden preamble,
or from a stale sentence earlier in the conversation, and every one of those
reads exactly like a fact. `Remind me tomorrow at 9` then lands on the wrong
day, and nothing in the transcript says why.

So the property under test throughout is one sentence:

> **No model, provider, Project or external webpage is the source of truth for
> Raiker's current clock, date, day or timezone.**

Each test below is one way that could stop being true — a Project change, a
provider change, a disabled web capability, a replayed scheduled timestamp, a
browser overwriting an owner's explicit choice — and pins it shut.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.runtime.environment import (
    DEVICE_TIMEZONE_SETTING,
    TIMEZONE_SETTING,
    WEATHER_LOCATION_SETTING,
    EnvironmentContext,
    environment_context,
    owner_weather_location,
    resolve_timezone,
)
from raiker.storage.sqlite import SQLiteStore


def test_timezone_data_is_available_without_a_host_database() -> None:
    """Windows has no system IANA database; installed Raiker must supply it."""
    result = subprocess.run(
        [sys.executable, "-c", (
            "from datetime import datetime; from zoneinfo import ZoneInfo; "
            "print(datetime(2026, 7, 1, tzinfo=ZoneInfo('Europe/London')).strftime('%z'))"
        )],
        env={**os.environ, "PYTHONTZPATH": ""},
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout.strip() == "+0100"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "env"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _settings(store: SQLiteStore, **values: str) -> None:
    store.put_user_settings("principal_owner", json.dumps(values), utc_now())


@pytest.fixture(autouse=True)
def _no_host_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test states its own precedence; none inherits the runner's zone."""
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr("raiker.runtime.environment._host_timezone", lambda: None)


class TestBundleShape:
    """What a turn is handed, and that it is both clocks."""

    def test_bundle_carries_utc_and_owner_local_together(
        self, store: SQLiteStore
    ) -> None:
        _settings(store, **{TIMEZONE_SETTING: "Europe/London"})
        moment = datetime(2026, 9, 7, 9, 6, 21, tzinfo=UTC)

        context = environment_context(store, "principal_owner", now=moment)

        # UTC alone cannot answer "tomorrow at 9"; local alone cannot be
        # audited across machines. Both, with the zone that relates them.
        assert context.generated_at_utc == "2026-09-07T09:06:21Z"
        assert context.local_datetime == "2026-09-07T10:06:21+01:00"
        assert context.timezone == "Europe/London"
        assert context.utc_offset == "+01:00"
        assert context.local_date == "2026-09-07"
        assert context.day_of_week == "Monday"
        assert context.display_date == "7 September 2026"

    def test_prompt_block_states_its_own_provenance(self, store: SQLiteStore) -> None:
        _settings(store, **{TIMEZONE_SETTING: "Europe/London"})
        block = environment_context(store, "principal_owner").prompt_block()

        assert "Raiker runtime clock" in block
        assert "trusted metadata" in block
        # The instruction that makes the bundle *used* rather than merely
        # present. A model told the date and not told to prefer it will still
        # reach for training knowledge on a relative-time question.
        assert "Do not infer the current date from training knowledge" in block

    def test_each_call_reads_the_clock_again(self, store: SQLiteStore) -> None:
        """The mechanism that stops a scheduled run replaying its creation."""
        first = environment_context(store, "principal_owner", now=datetime(2026, 9, 7, tzinfo=UTC))
        second = environment_context(store, "principal_owner", now=datetime(2026, 9, 8, tzinfo=UTC))

        assert first.local_date == "2026-09-07"
        assert second.local_date == "2026-09-08"

    def test_nothing_is_cached_between_calls(self, store: SQLiteStore) -> None:
        live_one = environment_context(store, "principal_owner")
        live_two = environment_context(store, "principal_owner")
        assert live_one.generated_at_utc <= live_two.generated_at_utc


class TestTimezonePrecedence:
    """One source of truth, in a fixed order."""

    def test_explicit_owner_setting_wins_over_device(self, store: SQLiteStore) -> None:
        _settings(
            store,
            **{
                TIMEZONE_SETTING: "Europe/London",
                DEVICE_TIMEZONE_SETTING: "America/Denver",
            },
        )
        zone, source = resolve_timezone(store, "principal_owner")

        # A traveller's browser proposing Denver is not a correction to make.
        assert (zone, source) == ("Europe/London", "owner_setting")

    def test_device_value_initialises_when_no_explicit_choice_exists(
        self, store: SQLiteStore
    ) -> None:
        _settings(store, **{DEVICE_TIMEZONE_SETTING: "Asia/Kolkata"})
        assert resolve_timezone(store, "principal_owner") == (
            "Asia/Kolkata",
            "device_preference",
        )

    def test_host_is_used_only_after_explicit_and_device(
        self, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "raiker.runtime.environment._host_timezone", lambda: "America/New_York"
        )
        assert resolve_timezone(store, "principal_owner") == ("America/New_York", "host")

        _settings(store, **{DEVICE_TIMEZONE_SETTING: "Asia/Tokyo"})
        assert resolve_timezone(store, "principal_owner") == (
            "Asia/Tokyo",
            "device_preference",
        )

    def test_utc_is_the_final_deterministic_fallback(self, store: SQLiteStore) -> None:
        assert resolve_timezone(store, "principal_owner") == ("UTC", "fallback")

    def test_an_unrecognised_zone_is_skipped_rather_than_adopted(
        self, store: SQLiteStore
    ) -> None:
        """A typo in a settings blob must not become where the owner is."""
        _settings(
            store,
            **{
                TIMEZONE_SETTING: "Europe/Lundun",
                DEVICE_TIMEZONE_SETTING: "Europe/Berlin",
            },
        )
        assert resolve_timezone(store, "principal_owner") == (
            "Europe/Berlin",
            "device_preference",
        )

    def test_dst_is_resolved_by_the_timezone_database(self, store: SQLiteStore) -> None:
        _settings(store, **{TIMEZONE_SETTING: "Europe/London"})
        summer = environment_context(
            store, "principal_owner", now=datetime(2026, 7, 1, 12, tzinfo=UTC)
        )
        winter = environment_context(
            store, "principal_owner", now=datetime(2026, 12, 1, 12, tzinfo=UTC)
        )

        # The same named zone, two offsets. An offset stored instead of a zone
        # could not do this, which is why the contract requires an IANA name.
        assert summer.utc_offset == "+01:00"
        assert winter.utc_offset == "+00:00"

    def test_tomorrow_resolves_from_owner_local_date_not_utc(
        self, store: SQLiteStore
    ) -> None:
        """The case where the two calendars disagree is the whole point."""
        _settings(store, **{TIMEZONE_SETTING: "Asia/Kolkata"})
        # 23:00 UTC is already the next day in Kolkata (+05:30).
        context = environment_context(
            store, "principal_owner", now=datetime(2026, 9, 7, 23, 0, tzinfo=UTC)
        )
        assert context.generated_at_utc.startswith("2026-09-07")
        assert context.local_date == "2026-09-08"
        assert context.day_of_week == "Tuesday"


class TestIndependence:
    """ENV-DECISION-02 — nothing unrelated may take the clock away."""

    def test_no_account_still_yields_a_bundle(self) -> None:
        context = environment_context(None, None)
        assert context.timezone == "UTC"
        assert context.timezone_source == "fallback"
        assert context.generated_at_utc.endswith("Z")

    def test_the_bundle_needs_no_network_and_no_provider(
        self, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A disabled web capability must not cost a turn its date."""

        def _explode(*args: object, **kwargs: object) -> None:
            raise AssertionError("environment context reached the network")

        monkeypatch.setattr("raiker.runtime.web_access._fetch", _explode)
        _settings(store, **{TIMEZONE_SETTING: "Europe/London"})
        assert environment_context(store, "principal_owner").timezone == "Europe/London"

    def test_an_unreadable_settings_row_falls_through_rather_than_failing(
        self, store: SQLiteStore
    ) -> None:
        store.put_user_settings("principal_owner", "{not json", utc_now())
        assert environment_context(store, "principal_owner").timezone_source == "fallback"


class TestWeatherLocationPreference:
    """A default place, held separately from the timezone."""

    def test_absent_by_default(self, store: SQLiteStore) -> None:
        assert owner_weather_location(store, "principal_owner") is None

    def test_read_from_its_own_key(self, store: SQLiteStore) -> None:
        _settings(
            store,
            **{
                TIMEZONE_SETTING: "Europe/London",
                WEATHER_LOCATION_SETTING: "Edinburgh, United Kingdom",
            },
        )
        assert (
            owner_weather_location(store, "principal_owner")
            == "Edinburgh, United Kingdom"
        )
        # And it reaches the bundle, so a turn knows the default exists without
        # having to call the weather tool to find out.
        assert environment_context(store, "principal_owner").location == (
            "Edinburgh, United Kingdom"
        )

    def test_timezone_and_weather_location_are_independent(
        self, store: SQLiteStore
    ) -> None:
        _settings(store, **{WEATHER_LOCATION_SETTING: "Lisbon, Portugal"})
        # Setting a weather location says nothing about where the owner
        # schedules from. Inferring one from the other is the conflation
        # ENV-DECISION-05 forbids in the other direction too.
        assert resolve_timezone(store, "principal_owner") == ("UTC", "fallback")


class TestSerialisation:
    def test_optional_fields_are_omitted_rather_than_null(self) -> None:
        payload = EnvironmentContext(
            generated_at_utc="2026-09-07T09:00:00Z",
            timezone="UTC",
            timezone_source="fallback",
            local_datetime="2026-09-07T09:00:00+00:00",
            local_date="2026-09-07",
            local_time="09:00:00",
            day_of_week="Monday",
            utc_offset="+00:00",
            display_date="7 September 2026",
        ).to_dict()

        assert "locale" not in payload
        assert "location" not in payload
        assert payload["freshness"] == "fresh"
