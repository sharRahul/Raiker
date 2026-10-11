"""DEC-14 step 5 — "verify signature, timestamp/nonce, account and pairing before routing."

The reference webhook took a bare shared secret in a header: anyone who saw one
request could replay it for ever, and the secret itself travelled with every
message. A sender may now sign instead — HMAC over the timestamp and the exact
body, keyed by the inbound secret, which then never goes on the wire — and the
receiver checks the signature, refuses a timestamp more than five minutes from
its clock, and refuses the same signed message a second time. An owner can
require signatures, after which an unsigned message is refused.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from tests.test_phase_4_channels import _enable, _pairing, _ws

WEBHOOK = "/api/channels/channel.webhook/inbound"
SECRET = "s3cret-inbound"


def _signed(body: dict[str, object], *, at: int | None = None, secret: str = SECRET) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    stamp = str(at if at is not None else int(time.time()))
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Raiker-Timestamp": stamp,
        "X-Raiker-Signature": f"sha256={digest}",
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    ws = _ws(tmp_path)
    _enable(ws, "external_channel_runtime")
    _pairing(ws, senders=["alice"])
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", SECRET)
    return TestClient(create_app(ws))


def test_a_signed_message_is_accepted_without_the_secret_on_the_wire(client: TestClient) -> None:
    raw, headers = _signed({"sender_id": "alice", "text": "status?"})
    answer = client.post(WEBHOOK, content=raw, headers=headers)
    assert answer.status_code == 200, answer.text
    assert answer.json().get("reason_code") != "duplicate_event"


def test_the_same_signed_message_twice_is_a_repeat(client: TestClient) -> None:
    raw, headers = _signed({"sender_id": "alice", "text": "status?"})
    first = client.post(WEBHOOK, content=raw, headers=headers)
    again = client.post(WEBHOOK, content=raw, headers=headers)
    assert again.status_code == 200
    assert again.json()["reason_code"] == "duplicate_event"
    assert again.json()["channel_message_id"] == first.json()["channel_message_id"]


@pytest.mark.parametrize(
    ("tamper", "code"),
    [
        ("body", "channel_signature_invalid"),
        ("secret", "channel_signature_invalid"),
        ("old", "channel_signature_expired"),
        ("future", "channel_signature_expired"),
        ("shape", "channel_signature_invalid"),
    ],
)
def test_a_forged_altered_or_stale_message_is_refused_before_routing(
    client: TestClient, tamper: str, code: str
) -> None:
    body: dict[str, object] = {"sender_id": "alice", "text": "status?"}
    now = int(time.time())
    raw, headers = _signed(
        body,
        at=now - 600 if tamper == "old" else now + 600 if tamper == "future" else None,
        secret="wrong" if tamper == "secret" else SECRET,
    )
    if tamper == "body":
        raw = json.dumps({"sender_id": "alice", "text": "delete everything"}).encode()
    if tamper == "shape":
        headers["X-Raiker-Signature"] = "md5=abc"
    answer = client.post(WEBHOOK, content=raw, headers=headers)
    assert answer.status_code == 401
    assert answer.json()["detail"]["reason_code"] == code


def test_when_signatures_are_required_the_bare_secret_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_REQUIRE_SIGNATURE", "1")
    bare = client.post(
        WEBHOOK, json={"sender_id": "alice", "text": "hi"}, headers={"X-Raiker-Channel-Secret": SECRET}
    )
    assert bare.status_code == 401
    assert bare.json()["detail"]["reason_code"] == "channel_signature_required"
    raw, headers = _signed({"sender_id": "alice", "text": "hi"})
    assert client.post(WEBHOOK, content=raw, headers=headers).status_code == 200


def test_the_messaging_page_says_whether_signatures_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.dashboard import DashboardService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_REQUIRE_SIGNATURE", "true")
    view = DashboardService(tmp_path).list_channels("principal_owner")
    assert view["inbound"]["signature_required"] is True
