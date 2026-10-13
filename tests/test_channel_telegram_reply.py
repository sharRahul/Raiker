"""BUG-315 — a Telegram turn's answer goes back over Telegram.

Owner decision, 2026-10-13: when the owner messages Raiker over Telegram, the
answer is sent back to their chat without asking — *unless it carries
sensitive information*, in which case it is held on *Deliveries to review* and
sent only when the owner presses Send. Either way the reply goes through the
governed channel executor, so the capability gate, a paused channel, the egress
allowlist and the reply limit still decide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.contracts.models import AgentResponse
from raiker.storage.sqlite import SQLiteStore
from tests.test_channel_inbound_dedup import HEADERS, TELEGRAM, _route_new_turns, _update
from tests.test_phase_4_channels import _enable, _telegram_pairing, _ws


class _Sent:
    bodies: list[dict[str, Any]] = []


def _fake_post_url(url: str, body: bytes, **_kwargs: object) -> dict[str, Any]:
    assert url.startswith("https://api.telegram.org/bot")
    _Sent.bodies.append(json.loads(body))
    return {
        "sent_bytes": len(body),
        "status": 200,
        "body": b'{"ok": true, "result": {"message_id": 77}}',
    }


@pytest.fixture()
def telegram(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, TestClient]:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _telegram_pairing(ws, senders=["4242", "5151"])
    _route_new_turns(ws)
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")
    monkeypatch.setenv("RAIKER_TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "api.telegram.org")
    monkeypatch.setattr("raiker.runtime.executors.channels.post_url", _fake_post_url)
    _Sent.bodies = []
    return ws, TestClient(create_app(ws))


def _answer(monkeypatch: pytest.MonkeyPatch, text: str, status: str = "completed") -> None:
    async def submit(self: object, envelope: Any) -> AgentResponse:
        store = SQLiteStore(self.workspace_root)  # type: ignore[attr-defined]
        store.create_session(envelope.session_id, str(self.workspace_root))  # type: ignore[attr-defined]
        store.insert_turn(envelope.session_id, envelope.turn_id, envelope.prompt.text)
        store.complete_turn(envelope.turn_id, status, text)
        return AgentResponse(
            request_id=envelope.request_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            status=status,
            message=text,
        )

    monkeypatch.setattr(
        "raiker.gateway.agent_gateway.AgentGateway.submit_prompt_async", submit
    )


def _receipts(ws: Path) -> list[dict[str, Any]]:
    return SQLiteStore(ws).list_channel_receipts("channel.telegram", limit=20)


def test_the_answer_to_the_owners_message_goes_back_to_their_chat(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    ws, client = telegram
    _answer(monkeypatch, "Your next meeting is at 3pm.")

    answer = client.post(TELEGRAM, headers=HEADERS, json=_update(1, "when is my next meeting?"))

    assert answer.status_code == 200, answer.text
    assert answer.json()["reply_delivery"] == "delivered"
    assert _Sent.bodies == [{"chat_id": "4242", "text": "Your next meeting is at 3pm."}]
    receipts = {row["direction"]: row for row in _receipts(ws)}
    inbound, outbound = receipts["inbound"], receipts["outbound"]
    assert inbound["delivered_at"] and inbound["reply_queued_at"]
    assert outbound["delivered_at"] and outbound["provider_message_id"] == "77"
    assert outbound["reply_to_receipt_id"] == inbound["receipt_id"]
    assert outbound["turn_id"] == answer.json()["turn_id"]
    # Receipts hold no message text.
    assert "3pm" not in json.dumps(receipts)


def test_an_answer_with_sensitive_information_is_held_until_the_owner_sends_it(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    ws, client = telegram
    _answer(monkeypatch, "The staging key is sk-ant-api03-" + "x" * 40)

    answer = client.post(TELEGRAM, headers=HEADERS, json=_update(2, "what is the staging key?"))

    assert answer.status_code == 200, answer.text
    assert answer.json()["reply_delivery"] == "held"
    assert _Sent.bodies == []
    store = SQLiteStore(ws)
    (held,) = store.list_channel_deliveries_to_review("channel.telegram")
    assert held["held_at"] and held["reason_code"] == "reply_held_sensitive"
    assert held["delivered_at"] is None and held["failed_at"] is None
    # A restart does not settle a held reply as "outcome unknown": it was never sent.
    store.settle_unsettled_outbound_receipts()
    assert (store.load_channel_receipt(held["receipt_id"]) or {})["outcome_unknown_at"] is None

    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    sent = client.post(
        f"/api/channels/deliveries/{held['receipt_id']}/send",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert sent.status_code == 200, sent.text
    assert sent.json()["delivered"] is True and sent.json()["receipt_id"] == held["receipt_id"]
    assert len(_Sent.bodies) == 1 and _Sent.bodies[0]["text"].startswith("The staging key is")
    assert store.list_channel_deliveries_to_review("channel.telegram") == []
    # Once sent, it cannot be sent twice.
    again = client.post(
        f"/api/channels/deliveries/{held['receipt_id']}/send",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 404


def test_marking_a_held_reply_reviewed_discards_it_without_sending(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    ws, client = telegram
    _answer(monkeypatch, "Write to me at owner@example.com.")
    assert client.post(TELEGRAM, headers=HEADERS, json=_update(3, "my email?")).json()[
        "reply_delivery"
    ] == "held"
    (held,) = SQLiteStore(ws).list_channel_deliveries_to_review("channel.telegram")
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    assert client.post(f"/api/channels/deliveries/{held['receipt_id']}/reviewed", headers=h).status_code == 200
    assert client.post(f"/api/channels/deliveries/{held['receipt_id']}/send", headers=h).status_code == 404
    assert _Sent.bodies == []


def test_a_closed_gate_still_refuses_the_reply(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.control.service import RuntimeControlService

    ws, client = telegram
    assert RuntimeControlService(ws).set_capability_state(
        "external_channel_runtime", "disabled", None, "test", confirmation_token="confirm"
    ).ok
    _answer(monkeypatch, "Done.")

    answer = client.post(TELEGRAM, headers=HEADERS, json=_update(4, "hello"))

    assert answer.status_code == 200
    assert answer.json()["reply_delivery"] == "failed"
    assert _Sent.bodies == []
    (pending,) = SQLiteStore(ws).list_channel_deliveries_to_review("channel.telegram")
    assert pending["failed_at"]


def test_another_senders_message_gets_no_reply_over_the_channel(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    ws, client = telegram
    store = SQLiteStore(ws)
    pairing = store.get_channel_pairing_by_connector("channel.telegram")
    assert pairing is not None
    store.set_channel_pairing_routing(
        str(pairing["pairing_id"]),
        routing_mode="side_question",
        target_session_id="sess_target",
        owner_sender_id="4242",
        approval_relay_enabled=False,
    )
    _answer(monkeypatch, "An answer.")

    answer = client.post(TELEGRAM, headers=HEADERS, json=_update(5, "a question", sender=5151))

    assert answer.status_code == 200, answer.text
    assert "reply_delivery" not in answer.json()
    assert _Sent.bodies == []


def test_a_turn_still_waiting_on_an_approval_sends_nothing_yet(
    telegram: tuple[Path, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    _ws_path, client = telegram
    _answer(monkeypatch, "I need your approval to write that file.", status="needs_approval")

    answer = client.post(TELEGRAM, headers=HEADERS, json=_update(6, "write a file"))

    assert answer.status_code == 200
    assert "reply_delivery" not in answer.json()
    assert _Sent.bodies == []


def test_what_counts_as_sensitive() -> None:
    from raiker.control.service import RuntimeControlService

    sensitive = RuntimeControlService.channel_reply_is_sensitive
    assert sensitive("token: ghp_" + "a" * 36)
    assert sensitive("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----")
    assert sensitive("mail owner@example.com")
    assert not sensitive("Your next meeting is at 3pm with the design team.")
