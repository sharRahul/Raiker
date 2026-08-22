"""Channels have an owner surface now (BUG-225).

The outbound executor, the inbound receiver, the `external_channel_runtime`
capability and the channel egress boundary were all built. What was missing was
any way for the owner to *pair* a connector — so `list_channel_pairings` stayed
empty, both executors refused, and the Channels tab reported that channels did
not exist. The transport was unreachable because there was no surface, which is a
different problem with a different fix.

These tests hold that surface to the contract in `docs/CHANNELS_SPEC.md` →
*What a channel message is in a turn*. Rule 5 is the one most of them are about:
**nothing is implicit.** Linked is not enabled; enabled is not trusted; and a
channel that is all three still delivers nothing until the owner allowlists the
destination host.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner, resolve_local_principal
from raiker.control.dashboard import DashboardService

WEBHOOKS = "channel.webhooks"


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


def _profile(service: DashboardService, owner_id: str, connector_id: str = WEBHOOKS) -> dict:
    view = service.list_channels(owner_id)
    match = [row for row in view["profiles"] if row["connector_id"] == connector_id]
    assert match, f"{connector_id} missing from the connector registry"
    return match[0]


# ── The surface reports facts, not a single "ready" flag ─────────────────────


def test_every_connector_profile_is_listed_with_what_it_needs(workspace: Path, owner: str) -> None:
    view = DashboardService(workspace).list_channels(owner)

    assert view["error"] is None
    assert len(view["profiles"]) >= 10
    row = _profile(DashboardService(workspace), owner)
    assert row["transport"] == "signed_http_callback"
    assert row["requires_pairing"] is True
    assert row["requires_sender_allowlist"] is True
    assert row["requires_network"] is True


def test_the_three_things_that_gate_delivery_are_reported_separately(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each has a different remedy — a capability the owner sets in Permissions, an
    # environment allowlist, and an inbound secret — so collapsing them into one
    # flag is what left this surface unable to say anything useful.
    monkeypatch.delenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", raising=False)
    monkeypatch.delenv("RAIKER_CHANNEL_INBOUND_SECRET", raising=False)

    view = DashboardService(workspace).list_channels(owner)

    assert view["outbound"]["capability"] == "external_channel_runtime"
    assert view["outbound"]["egress_configured"] is False
    assert view["inbound"]["secret_configured"] is False
    # The contract, stated rather than implied.
    assert view["inbound"]["quarantined"] is True
    assert view["inbound"]["instructions_inert"] is True


def test_egress_and_inbound_are_reported_from_the_environment(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "hooks.example.com,127.0.0.1:*")
    monkeypatch.setenv("RAIKER_CHANNEL_INBOUND_SECRET", "s3cret")

    view = DashboardService(workspace).list_channels(owner)

    assert view["outbound"]["egress_configured"] is True
    assert view["outbound"]["egress_host_count"] == 2
    assert view["inbound"]["secret_configured"] is True


# ── Rule 5: linked is not enabled, enabled is not trusted ────────────────────


def test_pairing_does_not_enable(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)

    result = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"])

    assert result.ok
    assert result.data["enabled"] is False
    row = _profile(service, owner)
    assert row["linked"] is True
    assert row["enabled"] is False


def test_a_profile_that_requires_senders_cannot_be_paired_without_one(
    workspace: Path, owner: str
) -> None:
    # The profile *declares* `requires_sender_allowlist`. Refusing here is what
    # turns that declaration into enforcement rather than documentation.
    result = DashboardService(workspace).pair_channel(owner, WEBHOOKS, "Webhooks", [])

    assert result.ok is False
    assert result.reason_code == "sender_allowlist_required"
    assert DashboardService(workspace).store.list_channel_pairings() == []


def test_a_connector_can_only_be_paired_once(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    assert service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).ok

    again = service.pair_channel(owner, WEBHOOKS, "Second", ["ops"])

    # Two pairings would make "is this channel linked" a question with two
    # answers, and every enforcement point that reads the pairing would guess.
    assert again.ok is False
    assert again.reason_code == "channel_already_paired"


def test_an_unknown_connector_is_refused_by_name(workspace: Path, owner: str) -> None:
    result = DashboardService(workspace).pair_channel(owner, "channel.invented", "X", ["ops"])

    assert result.ok is False
    assert result.reason_code == "unknown_connector:channel.invented"


def test_turning_a_channel_on_and_off_is_its_own_decision(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]

    assert service.set_channel_enabled(owner, pairing_id, True).ok
    assert _profile(service, owner)["enabled"] is True
    assert service.set_channel_enabled(owner, pairing_id, False).ok
    assert _profile(service, owner)["enabled"] is False


def test_disabling_keeps_the_sender_allowlist(workspace: Path, owner: str) -> None:
    # Off is a pause, not a reset: the owner should not have to retype who is
    # allowed in order to resume.
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops", "oncall"]).data[
        "pairing_id"
    ]
    service.set_channel_enabled(owner, pairing_id, True)
    service.set_channel_enabled(owner, pairing_id, False)

    assert _profile(service, owner)["sender_count"] == 2


def test_the_sender_allowlist_is_the_owners_to_replace(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]

    assert service.set_channel_senders(owner, pairing_id, ["oncall", "ops", "  "]).ok

    stored = service.store.get_channel_pairing(pairing_id)
    assert stored is not None
    assert json.loads(stored["sender_allowlist_json"]) == ["oncall", "ops"]


# ── Unpairing is what actually stops a channel ───────────────────────────────


def test_unpairing_removes_the_row_the_runtime_reads(workspace: Path, owner: str) -> None:
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    service.set_channel_enabled(owner, pairing_id, True)

    assert service.unpair_channel(owner, pairing_id).ok

    # Both executors and the inbound receiver read this table, so the deletion is
    # the stop — there is no state where the page says unpaired and a message
    # still gets through.
    assert service.store.list_channel_pairings() == []
    assert _profile(service, owner)["linked"] is False


def test_unpairing_something_that_is_not_paired_is_refused_by_name(
    workspace: Path, owner: str
) -> None:
    result = DashboardService(workspace).unpair_channel(owner, "chp_missing")

    assert result.ok is False
    assert result.reason_code == "unknown_channel_pairing"


# ── Delivery goes through the gate, never around it ──────────────────────────


def test_a_test_delivery_is_refused_when_the_capability_is_off(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "hooks.example.com")
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    service.set_channel_enabled(owner, pairing_id, True)
    turned_off = service.control.set_capability_state(
        "external_channel_runtime", "disabled", owner, "closing the gate for this test"
    )
    assert turned_off.ok, turned_off.reason_code

    result = service.deliver_channel_test(
        owner, WEBHOOKS, "https://hooks.example.com/x", "hello"
    )

    # A REST endpoint that POSTed the webhook itself would have "worked" here,
    # and proved nothing about the path a real delivery takes. This one cannot:
    # the owner's gate is above it.
    assert result.ok is False
    assert result.reason_code == "disabled_by_capability_gate"


def test_a_test_delivery_never_leaves_for_an_unallowlisted_host(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", raising=False)
    service = DashboardService(workspace)
    pairing_id = service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"]).data["pairing_id"]
    service.set_channel_enabled(owner, pairing_id, True)

    result = service.deliver_channel_test(
        owner, WEBHOOKS, "https://somewhere.invalid/x", "hello"
    )

    # Refused at the egress boundary, before a socket is opened: the allowlist is
    # empty by default, and empty means deny rather than allow-all.
    assert result.ok is False
    assert "egress_denied" in (result.reason_code or "")


def test_a_disabled_pairing_delivers_nothing_even_with_egress_open(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "somewhere.invalid")
    service = DashboardService(workspace)
    service.pair_channel(owner, WEBHOOKS, "Webhooks", ["ops"])  # left off

    result = service.deliver_channel_test(
        owner, WEBHOOKS, "https://somewhere.invalid/x", "hello"
    )

    # Refused for the pairing, before egress is even consulted — so the order of
    # the two boundaries is itself part of the contract.
    assert result.ok is False
    assert result.reason_code == "channel_not_paired_or_disabled"


def test_the_surface_reports_the_gate_the_owner_actually_set(
    workspace: Path, owner: str
) -> None:
    service = DashboardService(workspace)
    assert service.control.set_capability_state(
        "external_channel_runtime", "disabled", owner, "off for now"
    ).ok

    view = service.list_channels(owner)

    # A page that showed only pairings would say a channel was on while the
    # owner's own gate refused every delivery it attempted.
    assert view["outbound"]["gate_state"] == "disabled"
    assert view["outbound"]["runtime_enabled"] is False


# ── The surface must not be able to say the opposite of the truth ────────────


def test_a_boolean_under_a_secret_looking_key_survives_the_api(
    workspace: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A boolean cannot carry a credential, so redacting one protects nothing.

    Worse than lossy: the replacement is a non-empty string, so a client testing
    the field for truthiness reads the **opposite** of the truth. That is what
    happened here — the receiver was refusing every message and the Channels tab
    read "Secret set", because `inbound.secret_configured` came back as
    `"***REDACTED***"`.
    """
    from raiker.api.redaction import redact_response_body

    monkeypatch.delenv("RAIKER_CHANNEL_INBOUND_SECRET", raising=False)
    view = DashboardService(workspace).list_channels(owner)

    served = redact_response_body(view)

    assert served["inbound"]["secret_configured"] is False
    # And a real credential under the same kind of key is still discarded whole.
    assert redact_response_body({"api_secret": "sk-live-abcdef"})["api_secret"] != "sk-live-abcdef"
