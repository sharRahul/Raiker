"""DEC-14 step 7 — what became of a delivery, and the owner's review of one that did not arrive.

The receipt existed before send (FIXED-855). What remained: the platform's own
id for a delivered message, an idempotency key a receiver can deduplicate by,
a delivery the host stopped in the middle of settled as *outcome unknown* at
the next start rather than left queued for ever, and a dead-letter list the
owner can work through without anything being sent again.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.channels.adapters import TelegramAdapter, WebhookAdapter
from raiker.storage.sqlite import SQLiteStore
from tests.test_phase_4_channels import _action, _authority, _enable, _pairing, _ws


class _Answering(BaseHTTPRequestHandler):
    """A receiver that answers with its own id for what it accepted."""

    headers_seen: list[dict[str, str]] = []
    bodies: list[bytes] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        _Answering.bodies.append(self.rfile.read(length))
        _Answering.headers_seen.append(dict(self.headers.items()))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"id": "msg-7781", "echo": "the build is green"}')

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def answering_server() -> object:
    _Answering.headers_seen = []
    _Answering.bodies = []
    server = HTTPServer(("127.0.0.1", 0), _Answering)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server
    finally:
        server.shutdown()


def _outbound(ws: Path) -> list[dict[str, object]]:
    return [
        row
        for row in SQLiteStore(ws).list_channel_receipts("channel.webhook", limit=50)
        if row["direction"] == "outbound"
    ]


def test_a_delivered_message_keeps_the_receivers_id_and_carries_an_idempotency_key(
    tmp_path: Path, answering_server: HTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    port = answering_server.server_address[1]
    _pairing(ws, delivery_url=f"http://127.0.0.1:{port}/hook")
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", f"127.0.0.1:{port}")
    authority, principal = _authority(ws)
    action = _action(
        "external_channel_runtime", principal.principal_id,
        connector_id="channel.webhook", text="the build is green",
    )

    result = authority.route_action(action, principal)

    assert result.message == "executed"
    (receipt,) = _outbound(ws)
    assert receipt["provider_message_id"] == "msg-7781"
    # DEC-12 step 4 — the receipt id is the key a deduplicating receiver reads.
    assert _Answering.headers_seen[0]["Idempotency-Key"] == action.action_id
    assert json.loads(_Answering.bodies[0])["delivery_id"] == action.action_id
    # Only the id is kept from the answer: never what the receiver echoed.
    assert "the build is green" not in json.dumps(receipt)


def test_provider_ids_are_read_from_each_platforms_answer_and_nothing_else_is() -> None:
    assert TelegramAdapter().provider_message_id(
        b'{"ok": true, "result": {"message_id": 512, "text": "secret"}}'
    ) == "512"
    assert WebhookAdapter().provider_message_id(b'{"message_id": "abc-1"}') == "abc-1"
    # Not an id: a sentence, an object, an answer that is not JSON, nothing at all.
    assert WebhookAdapter().provider_message_id(b'{"id": "two words"}') is None
    assert WebhookAdapter().provider_message_id(b'{"id": {"nested": 1}}') is None
    assert WebhookAdapter().provider_message_id(b"ok") is None
    assert TelegramAdapter().provider_message_id(b"") is None
    assert WebhookAdapter().provider_message_id(json.dumps({"id": "x" * 129}).encode()) is None


def test_a_delivery_a_stopped_host_left_queued_is_settled_unknown_and_not_resent(
    tmp_path: Path,
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    store = SQLiteStore(ws)
    store.insert_channel_receipt(
        receipt_id="act_cut_off", connector_id="channel.webhook", pairing_id=None,
        direction="outbound", kind="message", stages={"queued_at": "2026-10-11T09:00:00Z"},
    )
    store.insert_channel_receipt(
        receipt_id="act_arrived", connector_id="channel.webhook", pairing_id=None,
        direction="outbound", kind="message",
        stages={"queued_at": "2026-10-11T09:00:00Z", "delivered_at": "2026-10-11T09:00:01Z"},
    )

    assert store.settle_unsettled_outbound_receipts() == 1
    assert store.settle_unsettled_outbound_receipts() == 0  # once only

    cut_off = store.load_channel_receipt("act_cut_off") or {}
    assert cut_off["outcome_unknown_at"] and cut_off["reason_code"] == "delivery_outcome_unknown"
    assert cut_off["delivered_at"] is None and cut_off["failed_at"] is None
    assert (store.load_channel_receipt("act_arrived") or {})["outcome_unknown_at"] is None
    review = [row["receipt_id"] for row in store.list_channel_deliveries_to_review("channel.webhook")]
    assert review == ["act_cut_off"]


def test_the_host_settles_unsettled_deliveries_when_it_starts(tmp_path: Path) -> None:
    from raiker.api.instance_runtime import InstanceRuntime

    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    store = SQLiteStore(ws)
    store.insert_channel_receipt(
        receipt_id="act_cut_off", connector_id="channel.webhook", pairing_id=None,
        direction="outbound", kind="message", stages={"queued_at": "2026-10-11T09:00:00Z"},
    )

    from types import SimpleNamespace

    app = SimpleNamespace(state=SimpleNamespace(workspace_root=ws))
    InstanceRuntime(app)._recover_abandoned_operations()  # type: ignore[arg-type]

    assert (store.load_channel_receipt("act_cut_off") or {})["outcome_unknown_at"]


def test_the_owner_marks_a_failed_delivery_reviewed_and_it_leaves_the_list(
    tmp_path: Path,
) -> None:
    from raiker.api.app import create_app
    from raiker.api.sessions import ApiSessionStore
    from raiker.control.dashboard import DashboardService

    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    service = DashboardService(ws)
    service.pair_channel("principal_owner", "channel.webhooks", "Webhooks", ["ops"])
    store = SQLiteStore(ws)
    store.insert_channel_receipt(
        receipt_id="act_refused", connector_id="channel.webhooks", pairing_id=None,
        direction="outbound", kind="message",
        stages={"queued_at": "2026-10-11T09:00:00Z", "failed_at": "2026-10-11T09:00:01Z"},
        reason_code="egress_denied:no_allowlist",
    )

    token, _ = ApiSessionStore(ws).create_session("principal_owner")
    client = TestClient(create_app(workspace_root=ws))
    h = {"Authorization": f"Bearer {token}"}

    def webhook() -> dict[str, Any]:
        profiles = client.get("/api/channels", headers=h).json()["profiles"]
        return next(p for p in profiles if p["connector_id"] == "channel.webhooks")

    (pending,) = webhook()["deliveries_to_review"]
    assert pending["receipt_id"] == "act_refused" and pending["failed_at"]

    answer = client.post("/api/channels/deliveries/act_refused/reviewed", headers=h)
    assert answer.status_code == 200, answer.text
    assert answer.json()["receipt_id"] == "act_refused" and answer.json()["reviewed_at"]
    assert webhook()["deliveries_to_review"] == []
    # Still failed: review changes the list, not what happened.
    receipt = store.load_channel_receipt("act_refused") or {}
    assert receipt["failed_at"] and receipt["reviewed_at"]
    # A receipt that is not an undelivered outbound one is not found.
    missing = client.post("/api/channels/deliveries/act_nothing/reviewed", headers=h)
    assert missing.status_code == 404
    assert missing.json()["detail"]["reason_code"] == "unknown_channel_delivery"


def test_only_an_undelivered_outbound_receipt_can_be_marked_reviewed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    store = SQLiteStore(ws)
    store.insert_channel_receipt(
        receipt_id="act_ok", connector_id="channel.webhook", pairing_id=None,
        direction="outbound", kind="message",
        stages={"queued_at": "2026-10-11T09:00:00Z", "delivered_at": "2026-10-11T09:00:01Z"},
    )
    store.insert_channel_receipt(
        receipt_id="rcv_in", connector_id="channel.webhook", pairing_id=None,
        direction="inbound", kind="message", stages={"failed_at": "2026-10-11T09:00:01Z"},
    )
    assert store.mark_channel_receipt_reviewed("act_ok") is False
    assert store.mark_channel_receipt_reviewed("rcv_in") is False
    assert store.mark_channel_receipt_reviewed("act_missing") is False
