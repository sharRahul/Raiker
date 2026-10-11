"""DEC-14 step 7 — an outbound delivery has its record before it is sent.

Only an owner's test delivery left a receipt, written after it had settled; a
real delivery — a reply or a notice sent over a paired channel — left none, so
Messaging could say what arrived and never what went out. Now the executor
writes the receipt as *queued* before anything is sent and settles it as
*delivered* or *failed* with the reason, whichever path the delivery ends on.
"""

from __future__ import annotations

import json
from http.server import HTTPServer
from pathlib import Path

import pytest

from raiker.storage.sqlite import SQLiteStore
from tests.test_phase_4_channels import (
    _action,
    _authority,
    _enable,
    _pairing,
    _Sink,
    _ws,
    loopback_server,  # noqa: F401 - the fixture
)


def _outbound(ws: Path) -> list[dict[str, object]]:
    return [
        row
        for row in SQLiteStore(ws).list_channel_receipts("channel.webhook", limit=50)
        if row["direction"] == "outbound"
    ]


def test_a_delivered_message_is_queued_then_delivered(
    tmp_path: Path, loopback_server: HTTPServer, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    port = loopback_server.server_address[1]
    _pairing(ws, delivery_url=f"http://127.0.0.1:{port}/hook")
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", f"127.0.0.1:{port}")
    authority, principal = _authority(ws)
    action = _action(
        "external_channel_runtime", principal.principal_id,
        connector_id="channel.webhook", text="the build is green",
    )

    result = authority.route_action(action, principal)

    assert result.message == "executed" and _Sink.received
    (receipt,) = _outbound(ws)
    assert receipt["receipt_id"] == action.action_id
    assert receipt["kind"] == "message"
    assert receipt["queued_at"] and receipt["delivered_at"] and receipt["failed_at"] is None
    # A receipt holds stages and a reason, never what was said or where to.
    assert "the build is green" not in json.dumps(receipt) and str(port) not in json.dumps(receipt)


def test_a_delivery_the_destination_refused_is_failed_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _pairing(ws, delivery_url="https://example.com/hook")
    monkeypatch.delenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", raising=False)
    authority, principal = _authority(ws)

    authority.route_action(
        _action("external_channel_runtime", principal.principal_id,
                connector_id="channel.webhook", text="hi"),
        principal,
    )

    (receipt,) = _outbound(ws)
    assert receipt["queued_at"] and receipt["failed_at"] and receipt["delivered_at"] is None
    assert str(receipt["reason_code"]).startswith("egress_denied")


def test_a_reply_too_long_for_the_channel_is_recorded_as_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _pairing(ws, delivery_url="https://example.com/hook")
    authority, principal = _authority(ws)

    authority.route_action(
        _action("external_channel_runtime", principal.principal_id,
                connector_id="channel.webhook", text="x" * 40_000),
        principal,
    )

    (receipt,) = _outbound(ws)
    assert receipt["failed_at"] and receipt["reason_code"] == "channel_message_too_long"


def test_an_owner_test_is_one_receipt_marked_as_a_test(
    tmp_path: Path, loopback_server: HTTPServer, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """The control service no longer writes a second receipt over the executor's."""
    from raiker.control.service import RuntimeControlService

    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    port = loopback_server.server_address[1]
    _pairing(ws, enabled=False, delivery_url=f"http://127.0.0.1:{port}/hook")
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", f"127.0.0.1:{port}")

    result = RuntimeControlService(ws).deliver_channel_test(None, "channel.webhook", "test")

    assert result.ok, result.reason_code
    (receipt,) = _outbound(ws)
    assert receipt["kind"] == "test_delivery" and receipt["delivered_at"]
