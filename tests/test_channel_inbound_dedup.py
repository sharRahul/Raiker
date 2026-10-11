"""DEC-14 steps 4 and 8 — a re-sent event is one message, and every scope has a budget.

Telegram re-sends an update it got no 2xx for, and a routed turn can outlast
its patience; before the provider's event id was kept, each re-send was a
second message and started a second turn. Separately, the only inbound budget
was per sender, so a channel with many allowlisted senders, or many channels
at once, had no bound.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.storage.sqlite import SQLiteStore
from tests.test_phase_4_channels import _enable, _pairing, _telegram_pairing, _ws

TELEGRAM = "/api/channels/channel.telegram/telegram"
WEBHOOK = "/api/channels/channel.webhook/inbound"


def _update(update_id: int, text: str = "hi", sender: int = 4242) -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {"from": {"id": sender}, "chat": {"id": sender, "type": "private"}, "text": text},
    }


def _route_new_turns(ws: Path) -> None:
    store = SQLiteStore(ws)
    pairing = store.get_channel_pairing_by_connector("channel.telegram")
    assert pairing is not None
    store.set_channel_pairing_routing(
        str(pairing["pairing_id"]),
        routing_mode="new_turn",
        target_session_id=None,
        owner_sender_id="4242",
        approval_relay_enabled=False,
    )


@pytest.fixture()
def telegram(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, TestClient]:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _telegram_pairing(ws, senders=["4242", "5151", "6161"])
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")
    return ws, TestClient(create_app(ws))


HEADERS = {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}


def test_a_resent_telegram_update_starts_no_second_turn(
    telegram: tuple[Path, TestClient],
) -> None:
    ws, client = telegram
    _route_new_turns(ws)

    first = client.post(TELEGRAM, headers=HEADERS, json=_update(901))
    again = client.post(TELEGRAM, headers=HEADERS, json=_update(901))

    assert first.status_code == 200 and again.status_code == 200, again.text
    assert first.json()["routed"] is True
    repeat = again.json()
    assert repeat["reason_code"] == "duplicate_event"
    assert repeat["routed"] is False
    # The repeat is answered with the first message's receipt and its conversation.
    assert repeat["channel_message_id"] == first.json()["channel_message_id"]
    assert repeat["session_id"] == first.json()["session_id"]
    # One message happened, so one receipt.
    assert len(SQLiteStore(ws).list_channel_receipts("channel.telegram", limit=50)) == 1


def test_a_different_update_with_the_same_words_is_a_new_message(
    telegram: tuple[Path, TestClient],
) -> None:
    ws, client = telegram

    one = client.post(TELEGRAM, headers=HEADERS, json=_update(1, "status?"))
    two = client.post(TELEGRAM, headers=HEADERS, json=_update(2, "status?"))

    assert one.status_code == two.status_code == 200
    assert "reason_code" not in two.json() or two.json()["reason_code"] != "duplicate_event"
    assert one.json()["channel_message_id"] != two.json()["channel_message_id"]


def test_a_repeat_does_not_spend_the_senders_budget(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise Telegram's third re-send of one message would be rate limited."""
    _, client = telegram
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "2")

    codes = [client.post(TELEGRAM, headers=HEADERS, json=_update(7)).status_code for _ in range(5)]
    fresh = client.post(TELEGRAM, headers=HEADERS, json=_update(8))

    assert codes == [200] * 5
    assert fresh.status_code == 200 and "duplicate_event" not in fresh.text


def test_a_refused_message_can_be_retried_under_the_same_id(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A message refused by a budget was not accepted; its retry is a fresh try."""
    from raiker.api import routes_channels

    _, client = telegram
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "1")

    assert client.post(TELEGRAM, headers=HEADERS, json=_update(10)).status_code == 200
    refused = client.post(TELEGRAM, headers=HEADERS, json=_update(11))
    assert refused.status_code == 429
    routes_channels._inbound_hits.clear()
    routes_channels._channel_hits.clear()
    routes_channels._global_hits.clear()

    retried = client.post(TELEGRAM, headers=HEADERS, json=_update(11))
    assert retried.status_code == 200
    assert retried.json().get("reason_code") != "duplicate_event"


def test_a_webhook_caller_names_its_retries_with_an_idempotency_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _pairing(ws, senders=["alice"])
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")
    client = TestClient(create_app(ws))
    headers = {"X-Raiker-Channel-Secret": "s3cret", "Idempotency-Key": "evt-000123"}
    body = {"sender_id": "alice", "text": "deploy finished"}

    first = client.post(WEBHOOK, headers=headers, json=body)
    again = client.post(WEBHOOK, headers=headers, json=body)
    unkeyed = client.post(WEBHOOK, headers={"X-Raiker-Channel-Secret": "s3cret"}, json=body)

    assert first.status_code == again.status_code == unkeyed.status_code == 200
    assert again.json()["reason_code"] == "duplicate_event"
    assert again.json()["channel_message_id"] == first.json()["channel_message_id"]
    # Without a key nothing can be told apart, and nothing is assumed.
    assert unkeyed.json().get("reason_code") != "duplicate_event"


def test_a_malformed_idempotency_key_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _pairing(ws, senders=["alice"])
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")
    client = TestClient(create_app(ws))

    response = client.post(
        WEBHOOK,
        headers={"X-Raiker-Channel-Secret": "s3cret", "Idempotency-Key": "a b"},
        json={"sender_id": "alice", "text": "hi"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "idempotency_key_invalid"


def test_a_repeat_is_recorded_in_the_audit_log(telegram: tuple[Path, TestClient]) -> None:
    ws, client = telegram
    client.post(TELEGRAM, headers=HEADERS, json=_update(55))
    client.post(TELEGRAM, headers=HEADERS, json=_update(55))

    from raiker.events.query import EventViewer

    viewer = EventViewer(SQLiteStore(ws))
    rejected = [
        json.dumps(viewer.read_event_payload(index["event_id"]) or {})
        for index in viewer.list_events(limit=200)
        if index.get("event_type") == "channel_message_rejected"
    ]
    assert any('"duplicate_event"' in payload for payload in rejected)


# ── DEC-14 step 8 — the channel's and the host's budgets ─────────────────────


def test_a_channel_is_bounded_across_all_its_senders(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, client = telegram
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "10")
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_CHANNEL_RATE", "2")

    first = client.post(TELEGRAM, headers=HEADERS, json=_update(1, sender=4242))
    second = client.post(TELEGRAM, headers=HEADERS, json=_update(2, sender=5151))
    third = client.post(TELEGRAM, headers=HEADERS, json=_update(3, sender=6161))

    assert first.status_code == second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"]["reason_code"] == "channel_rate_limited"


def test_a_message_the_channel_refused_does_not_spend_the_senders_budget(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.api import routes_channels

    _, client = telegram
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "1")
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_CHANNEL_RATE", "1")

    assert client.post(TELEGRAM, headers=HEADERS, json=_update(1, sender=4242)).status_code == 200
    refused = client.post(TELEGRAM, headers=HEADERS, json=_update(2, sender=5151))
    assert refused.json()["detail"]["reason_code"] == "channel_rate_limited"

    # The channel's window empties; 5151 never spent its own.
    routes_channels._channel_hits.clear()
    routes_channels._global_hits.clear()
    assert client.post(TELEGRAM, headers=HEADERS, json=_update(3, sender=5151)).status_code == 200


def test_the_host_is_bounded_across_every_channel(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, client = telegram
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "10")
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_GLOBAL_RATE", "1")

    assert client.post(TELEGRAM, headers=HEADERS, json=_update(1)).status_code == 200
    refused = client.post(TELEGRAM, headers=HEADERS, json=_update(2))

    assert refused.status_code == 429
    assert refused.json()["detail"]["reason_code"] == "inbound_rate_limited"


def test_the_wider_budgets_default_to_multiples_of_the_senders(monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.api.routes_channels import (
        channel_inbound_channel_limit,
        channel_inbound_global_limit,
    )

    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_RATE", "5")
    monkeypatch.delenv("RAIKER_CHANNEL_INBOUND_CHANNEL_RATE", raising=False)
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_GLOBAL_RATE", "0")

    assert channel_inbound_channel_limit() == 20
    # "0" is a mistake, not a request for no bound.
    assert channel_inbound_global_limit() == 50


# ── DEC-14 step 3 — who an allowed sender is, as their own messages say ──────


def test_an_allowed_sender_is_named_as_they_name_themselves(
    telegram: tuple[Path, TestClient],
) -> None:
    from raiker.channels.adapters import adapter_for

    ws, client = telegram
    update = _update(70)
    update["message"]["from"]["username"] = "alex"  # type: ignore[index]
    assert client.post(TELEGRAM, headers=HEADERS, json=update).status_code == 200

    pairing = SQLiteStore(ws).get_channel_pairing_by_connector("channel.telegram")
    assert pairing is not None
    assert json.loads(pairing["sender_labels_json"]) == {"4242": "@alex"}
    adapter = adapter_for("telegram")
    assert adapter is not None
    named = adapter.parse_inbound(
        {"message": {"from": {"id": 1, "first_name": "Sam", "last_name": "Lee"}, "chat": {"id": 1}, "text": "hi"}}
    )
    assert named is not None and named.sender_label == "Sam Lee"


def test_a_refused_sender_leaves_no_name_behind(telegram: tuple[Path, TestClient]) -> None:
    ws, client = telegram
    update = _update(71, sender=9999)
    update["message"]["from"]["username"] = "stranger"  # type: ignore[index]
    assert client.post(TELEGRAM, headers=HEADERS, json=update).status_code == 403

    pairing = SQLiteStore(ws).get_channel_pairing_by_connector("channel.telegram")
    assert pairing is not None and not pairing.get("sender_labels_json")


def test_a_label_is_cleaned_bounded_and_forgotten_with_the_sender(tmp_path: Path) -> None:
    from raiker.storage.sqlite import SQLiteStore as Store

    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _telegram_pairing(ws, senders=["4242", "5151"])
    store = Store(ws)
    pairing = store.get_channel_pairing_by_connector("channel.telegram")
    assert pairing is not None
    pairing_id = str(pairing["pairing_id"])

    assert store.record_channel_sender_label(pairing_id, "4242", "  Al\x00ex\n  " + "x" * 200)
    assert store.record_channel_sender_label(pairing_id, "5151", "Sam")
    labelled = store.get_channel_pairing(pairing_id)
    assert labelled is not None
    labels = json.loads(labelled["sender_labels_json"])
    assert labels["4242"].startswith("Alex x") and len(labels["4242"]) == 64
    # The same name again writes nothing; an id off the allowlist is never named.
    assert not store.record_channel_sender_label(pairing_id, "5151", "Sam")
    assert not store.record_channel_sender_label(pairing_id, "9999", "Mallory")

    store.set_channel_pairing_allowlist(pairing_id, json.dumps(["5151"]))
    view_labels = _labels_in_view(ws)
    assert view_labels == {"5151": "Sam"}


def _labels_in_view(ws: Path) -> dict[str, str]:
    from raiker.cli.principal_resolver import resolve_local_principal
    from raiker.control.dashboard import DashboardService

    principal, _ = resolve_local_principal(ws, None)
    assert principal is not None
    view = DashboardService(ws).list_channels(principal.principal_id)
    (row,) = [p for p in view["profiles"] if p["connector_id"] == "channel.telegram"]
    return dict(row.get("sender_labels", {}))
