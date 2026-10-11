"""DEC-14 step 3 — a destination typed by hand is proven before the channel goes on.

Raiker cannot discover a Telegram chat or check a webhook URL it was given, so
the setup checklist put *Test delivery* before *Turned on* — and the server
turned a channel on whatever the checklist said. Now a channel with a
configured destination is turned on only after a test to that destination was
delivered, and changing the destination forgets the test.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner, resolve_local_principal
from raiker.control.dashboard import DashboardService

WEBHOOKS = "channel.webhooks"
TELEGRAM = "channel.telegram"


@pytest.fixture()
def workspace(tmp_path: Path) -> Iterator[Path]:
    (tmp_path / "config").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    yield tmp_path


@pytest.fixture()
def owner(workspace: Path) -> str:
    principal, _ = resolve_local_principal(workspace, None)
    assert principal is not None
    return principal.principal_id


def _route(service: DashboardService, owner: str, pairing_id: str, sender: str) -> None:
    assert service.set_channel_routing(
        owner,
        pairing_id,
        routing_mode="new_turn",
        target_session_id=None,
        owner_sender_id=sender,
        approval_relay_enabled=False,
    ).ok


def test_a_webhook_with_an_untested_destination_stays_off(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    assert service.set_channel_destination(owner, pairing_id, "https://hooks.example.com/t").ok

    refused = service.set_channel_enabled(owner, pairing_id, True)

    assert refused.ok is False and refused.reason_code == "channel_test_required"
    stored = service.control._store.get_channel_pairing(pairing_id)
    assert stored is not None and stored["enabled"] in (0, False)


def test_a_failed_test_does_not_count(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    assert service.set_channel_destination(owner, pairing_id, "https://hooks.example.com/t").ok
    service.control._store.record_channel_pairing_test(pairing_id, ok=False, reason_code="http_error:500")

    assert service.set_channel_enabled(owner, pairing_id, True).reason_code == "channel_test_required"


def test_a_delivered_test_lets_it_on(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    assert service.set_channel_destination(owner, pairing_id, "https://hooks.example.com/t").ok
    service.control._store.record_channel_pairing_test(pairing_id, ok=True, reason_code=None)

    assert service.set_channel_enabled(owner, pairing_id, True).ok


def test_a_channel_with_nothing_to_deliver_to_has_nothing_to_prove(
    workspace: Path, owner: str
) -> None:
    """An inbound-only webhook is turned on as before."""
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]

    assert service.set_channel_enabled(owner, pairing_id, True).ok


def test_turning_off_never_needs_a_test(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    assert service.set_channel_enabled(owner, pairing_id, True).ok
    assert service.set_channel_destination(owner, pairing_id, "https://hooks.example.com/t").ok

    assert service.set_channel_enabled(owner, pairing_id, False).ok


def test_telegram_needs_a_test_to_the_owner_chosen(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, TELEGRAM, "Telegram", ["4242", "5151"]).data[
        "pairing_id"
    ]
    _route(service, owner, pairing_id, "4242")

    assert service.set_channel_enabled(owner, pairing_id, True).reason_code == "channel_test_required"
    service.control._store.record_channel_pairing_test(pairing_id, ok=True, reason_code=None)
    assert service.set_channel_enabled(owner, pairing_id, True).ok


def test_choosing_another_telegram_owner_forgets_the_test(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    store = service.control._store
    pairing_id = service.pair_channel(owner, TELEGRAM, "Telegram", ["4242", "5151"]).data[
        "pairing_id"
    ]
    _route(service, owner, pairing_id, "4242")
    store.record_channel_pairing_test(pairing_id, ok=True, reason_code=None)

    # Same owner, different route: the test still describes the destination.
    assert service.set_channel_routing(
        owner,
        pairing_id,
        routing_mode="record_only",
        target_session_id=None,
        owner_sender_id="4242",
        approval_relay_enabled=False,
    ).ok
    kept = store.get_channel_pairing(pairing_id)
    assert kept is not None and kept["last_test_ok"] == 1

    _route(service, owner, pairing_id, "5151")
    pairing = store.get_channel_pairing(pairing_id)
    assert pairing is not None
    assert pairing["last_test_ok"] is None and pairing["last_test_at"] is None
    assert service.set_channel_enabled(owner, pairing_id, True).reason_code == "channel_test_required"


def test_the_refusal_is_a_409_over_the_api(workspace: Path, owner: str) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    assert service.set_channel_destination(owner, pairing_id, "https://hooks.example.com/t").ok
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    response = client.put(f"/api/channels/pairings/{pairing_id}/enabled", json={"enabled": True})

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["reason_code"] == "channel_test_required"
