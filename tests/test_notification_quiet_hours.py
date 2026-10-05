"""DEC-21a — quiet hours are quiet unless the owner chooses an exception.

The owner accepted the decision on 2026-10-05: quiet hours are opt-in; once on,
no notice interrupts during the interval — approvals, failed routines and
security notices included — while the bell, the record and the approval queue
stay as they are. Critical exceptions are off by default, enumerated, and per
channel. These tests pin the policy, the stored decision, the end-of-interval
summary, the per-category preferences and the test notice that goes through the
same path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.notify import delivery_policy as policy
from raiker.notify.approval_notifier import os_notification_outcome
from raiker.storage.sqlite import SQLiteStore

OVERNIGHT = {
    policy.ENABLED_KEY: True,
    policy.START_KEY: "22:00",
    policy.END_KEY: "07:00",
    policy.TIMEZONE_KEY: "Europe/London",
}


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


# ── The policy ────────────────────────────────────────────────────────────


def test_quiet_hours_are_off_until_the_owner_turns_them_on() -> None:
    decision = policy.decide({}, kind="approval_pending", now=_at("2026-10-05T23:30:00+01:00"), fallback_zone="UTC")
    assert (decision.in_app, decision.desktop, decision.quiet_until) == ("interrupt", "interrupt", None)


def test_an_overnight_interval_holds_every_kind_including_approvals() -> None:
    late = _at("2026-10-05T23:30:00+01:00")  # 23:30 in London (BST)
    for kind in ("approval_pending", "task_paused", "security_alert", "made_up_kind"):
        decision = policy.decide(OVERNIGHT, kind=kind, now=late, fallback_zone="UTC")
        assert decision.in_app == "quiet_hours" and decision.desktop == "quiet_hours", kind
        # 07:00 London the next morning, as an instant.
        assert decision.quiet_until == "2026-10-06T06:00:00Z"


def test_the_interval_is_read_on_the_owners_wall_clock() -> None:
    # 06:30 UTC is 07:30 in London in October: the interval is over there,
    # though a UTC reading of 22:00–07:00 would still call it quiet.
    morning = _at("2026-10-06T06:30:00+00:00")
    assert policy.decide(OVERNIGHT, kind="task_finished", now=morning, fallback_zone="UTC").in_app == "interrupt"


def test_the_account_zone_is_used_when_quiet_hours_name_none() -> None:
    settings = {key: value for key, value in OVERNIGHT.items() if key != policy.TIMEZONE_KEY}
    late_in_kolkata = _at("2026-10-05T23:00:00+05:30")
    assert (
        policy.decide(settings, kind="task_finished", now=late_in_kolkata, fallback_zone="Asia/Kolkata").in_app
        == "quiet_hours"
    )
    assert (
        policy.decide(settings, kind="task_finished", now=late_in_kolkata, fallback_zone="UTC").in_app
        == "interrupt"
    )


@pytest.mark.parametrize(
    ("instant", "expected_end"),
    [
        # Spring forward in London: 2026-03-29 01:00 → 02:00. A 01:30 end does
        # not exist that morning and resolves to the moment the clock jumps.
        ("2026-03-29T00:30:00+00:00", "2026-03-29T01:00:00Z"),
        # Autumn back: 2026-10-25 02:00 BST → 01:00 GMT. A 01:30 end resolves
        # to its first occurrence.
        ("2026-10-25T00:10:00+01:00", "2026-10-25T00:30:00Z"),
    ],
)
def test_both_dst_transitions_give_a_real_end(instant: str, expected_end: str) -> None:
    settings = {**OVERNIGHT, policy.START_KEY: "00:00", policy.END_KEY: "01:30"}
    decision = policy.decide(settings, kind="task_finished", now=_at(instant), fallback_zone="UTC")
    assert decision.in_app == "quiet_hours"
    assert decision.quiet_until == expected_end


def test_critical_exceptions_are_per_channel_and_only_for_enumerated_kinds() -> None:
    late = _at("2026-10-05T23:30:00+01:00")
    settings = {**OVERNIGHT, policy.CRITICAL_DESKTOP_KEY: True}
    contained = policy.decide(settings, kind="capability_contained", now=late, fallback_zone="UTC")
    assert (contained.in_app, contained.desktop) == ("quiet_hours", "critical_exception")
    # An approval, however urgent its copy, is not a critical security event.
    approval = policy.decide(settings, kind="critical_approval_pending", now=late, fallback_zone="UTC")
    assert approval.desktop == "quiet_hours"


def test_a_muted_category_is_recorded_and_never_interrupts() -> None:
    settings = {policy.category_key("work"): False}
    decision = policy.decide(settings, kind="task_finished", now=_at("2026-10-05T12:00:00+00:00"), fallback_zone="UTC")
    assert (decision.in_app, decision.desktop) == ("muted", "muted")
    # Decisions cannot be muted: there is no switch for them.
    assert "decisions" not in policy.MUTABLE_CATEGORIES
    assert policy.decide(
        {policy.category_key("decisions"): False},
        kind="approval_pending",
        now=_at("2026-10-05T12:00:00+00:00"),
        fallback_zone="UTC",
    ).in_app == "interrupt"


@pytest.mark.parametrize(
    ("settings", "reason"),
    [
        ({policy.START_KEY: "25:00"}, "invalid_quiet_hours_time"),
        ({policy.START_KEY: "07:00", policy.END_KEY: "07:00"}, "quiet_hours_empty"),
        ({policy.TIMEZONE_KEY: "Mars/Olympus"}, "invalid_quiet_hours_timezone"),
        ({policy.ENABLED_KEY: "yes"}, "invalid_quiet_hours_switch"),
        ({policy.category_key("work"): 0}, "invalid_interrupt_switch"),
    ],
)
def test_values_the_policy_cannot_evaluate_are_refused(settings: dict[str, object], reason: str) -> None:
    assert policy.validate(settings) == reason


def test_rows_older_than_the_policy_keep_interrupting() -> None:
    assert policy.interrupts(None)
    assert policy.interrupts("critical_exception")
    assert not policy.interrupts("quiet_hours")
    assert not policy.interrupts("muted")


# ── The store and the routes ──────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _owner(client: TestClient) -> tuple[dict[str, str], str]:
    body = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    principal = client.get("/api/account/deletion-preview", headers=headers)
    assert principal.status_code == 200
    store = SQLiteStore(client.app.state.workspace_root)  # type: ignore[attr-defined]
    owner = store.original_account_principal_id()
    assert owner is not None
    return headers, owner


def _save(client: TestClient, headers: dict[str, str], extra: dict[str, object]) -> None:
    settings = client.get("/api/settings", headers=headers).json()["settings"]
    response = client.put("/api/settings", json={"settings": {**settings, **extra}}, headers=headers)
    assert response.status_code == 200, response.text


def test_a_notice_written_in_quiet_hours_is_recorded_held_and_not_lost(client: TestClient) -> None:
    headers, owner = _owner(client)
    _save(client, headers, OVERNIGHT)
    store = SQLiteStore(client.app.state.workspace_root)  # type: ignore[attr-defined]
    store.insert_notification(
        principal_id=owner, kind="task_finished", title="Done", body="It ran.",
        now=_at("2026-10-05T23:30:00+01:00"),
    )
    [row] = client.get("/api/notifications", headers=headers).json()
    assert row["read"] is False
    assert row["in_app_presentation"] == "quiet_hours"
    assert row["desktop_presentation"] == "quiet_hours"
    assert row["quiet_until"] == "2026-10-06T06:00:00Z"


def test_the_summary_lists_what_is_still_relevant_once(client: TestClient) -> None:
    headers, owner = _owner(client)
    _save(client, headers, OVERNIGHT)
    store = SQLiteStore(client.app.state.workspace_root)  # type: ignore[attr-defined]
    night = _at("2026-10-01T23:30:00+01:00")
    kept = store.insert_notification(principal_id=owner, kind="task_finished", title="Done", body="x", now=night)
    # An approval notice whose approval no longer exists as pending is not relevant.
    store.insert_notification(
        principal_id=owner, kind="approval_pending", title="Approval needed", body="y",
        subject_id="apr_gone", now=night,
    )
    morning = client.get("/api/notifications/delivery", headers=headers).json()
    # The real clock is past 2026-10-02 07:00 London, so the interval is over.
    assert [item["notification_id"] for item in morning["held"]] == [kept]
    ack = client.post(
        "/api/notifications/held/acknowledge", json={"notification_ids": [kept, "ntf_not_mine"]}, headers=headers
    )
    assert ack.json() == {"acknowledged": 1}
    again = client.get("/api/notifications/delivery", headers=headers).json()
    assert again["held"] == []
    # Seeing the summary is not reading the notices.
    assert [row["read"] for row in client.get("/api/notifications", headers=headers).json()] == [False, False]


def test_delivery_reports_the_terms_and_the_categories(client: TestClient) -> None:
    headers, _owner_id = _owner(client)
    off = client.get("/api/notifications/delivery", headers=headers).json()
    assert off["quiet_hours"]["enabled"] is False
    assert off["quiet_hours"]["critical_in_app"] is False and off["quiet_hours"]["critical_desktop"] is False
    assert off["decisions_interrupt"] is True
    assert {item["category"] for item in off["categories"]} == set(policy.MUTABLE_CATEGORIES)
    _save(client, headers, {**OVERNIGHT, policy.category_key("extensions"): False})
    on = client.get("/api/notifications/delivery", headers=headers).json()
    assert on["quiet_hours"]["enabled"] is True and on["quiet_hours"]["timezone"] == "Europe/London"
    assert on["quiet_hours"]["ends_at"] or on["quiet_hours"]["next_starts_at"]
    assert {item["category"]: item["interrupts"] for item in on["categories"]}["extensions"] is False


def test_a_settings_save_the_policy_cannot_read_is_refused(client: TestClient) -> None:
    headers, _owner_id = _owner(client)
    settings = client.get("/api/settings", headers=headers).json()["settings"]
    bad = client.put(
        "/api/settings", json={"settings": {**settings, policy.END_KEY: "7am"}}, headers=headers
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_quiet_hours_time"


def test_the_test_notice_goes_through_the_same_policy(client: TestClient) -> None:
    headers, _owner_id = _owner(client)
    sent = client.post("/api/notifications/test", headers=headers).json()["notification"]
    assert sent["kind"] == "test_notice" and sent["in_app_presentation"] == "interrupt"
    # Quiet all day, in the server's own zone: the test notice is held like any other.
    _save(client, headers, {
        policy.ENABLED_KEY: True, policy.START_KEY: "00:00", policy.END_KEY: "23:59",
        policy.TIMEZONE_KEY: "UTC",
    })
    now = datetime.now(UTC)
    if now.hour == 23 and now.minute == 59:
        pytest.skip("the one minute of the day outside this interval")
    held = client.post("/api/notifications/test", headers=headers).json()["notification"]
    assert held["in_app_presentation"] == "quiet_hours"
    assert held["quiet_until"] is not None


def test_the_os_command_obeys_the_stored_desktop_decision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, owner = _owner(client)
    _save(client, headers, OVERNIGHT)
    store = SQLiteStore(client.app.state.workspace_root)  # type: ignore[attr-defined]
    monkeypatch.setenv("RAIKER_OS_NOTIFY_CMD", "true")
    held = store.insert_notification(
        principal_id=owner, kind="task_paused", title="Paused", body="x", now=_at("2026-10-05T23:30:00+01:00")
    )
    shown = store.insert_notification(
        principal_id=owner, kind="task_paused", title="Paused", body="x", now=_at("2026-10-05T12:00:00+01:00")
    )
    assert os_notification_outcome("t", "b", store=store, notification_id=held) == "held"
    assert os_notification_outcome("t", "b", store=store, notification_id=shown) == "sent"
