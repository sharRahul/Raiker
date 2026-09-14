"""RR-MCP-02 — where a remote MCP server may live.

The defect these cover: adding a remote server was one scheme check, so the
owner's own laptop, a box on their LAN, a public endpoint, a public *name* that
answers with a private address, and a cloud metadata service were the same
thing to Raiker and carried the same label on the card.

The posture matters as much as the refusals, so both are asserted here: a
loopback server over plain http is the ordinary case and stays allowed, a LAN
address is the owner's own choice and stays allowed, and what is refused is the
narrow set where the destination is not the thing the owner typed.
"""
from __future__ import annotations

import pytest

from raiker.runtime.mcp_endpoint_policy import (
    LOOPBACK,
    PRIVATE_NETWORK,
    PUBLIC,
    endpoint_refusal_message,
    evaluate_endpoint,
    network_class_label,
    stated_network_class,
)

# ── what the owner legitimately chose stays allowed ──────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:3000/mcp",
        "http://localhost:8080/mcp",
        "http://[::1]:8080/mcp",
        "https://localhost/mcp",
    ],
)
def test_loopback_is_allowed_over_plain_http(url: str) -> None:
    """A local MCP server is the ordinary case, not a threat. Requiring TLS on
    localhost would mean nobody could run one."""
    trust = evaluate_endpoint(url)
    assert trust.allowed
    assert trust.network_class == LOOPBACK
    # No pin: there is no name to be re-resolved between the check and the socket.
    assert trust.pin is None


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.20:3000/mcp",
        "http://10.0.0.5/mcp",
        "https://172.16.4.9/mcp",
        "http://nas.internal/mcp",
        "http://tools.home.arpa/mcp",
    ],
)
def test_owners_own_network_is_allowed(url: str) -> None:
    """A NAS or a workstation running a tool server is a thing owners have."""
    trust = evaluate_endpoint(url)
    assert trust.allowed
    assert trust.network_class == PRIVATE_NETWORK


def test_public_https_endpoint_is_allowed_and_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "raiker.runtime.mcp_endpoint_policy._resolve_public",
        lambda host, port: ["203.0.113.10"],
    )
    trust = evaluate_endpoint("https://tools.example.com/mcp")
    assert trust.allowed
    assert trust.network_class == PUBLIC
    # The address the transport must dial, so the name cannot be re-resolved
    # into somewhere else between the check and the socket.
    assert trust.pin == "203.0.113.10"
    assert trust.origin == "https://tools.example.com:443"


# ── what is refused, and why each one is not the owner's choice ──────────────


def test_public_name_answering_privately_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """The standard shape of a server-side request forgery. Nobody chose this
    destination: the name says one thing and the resolver answers another."""
    monkeypatch.setattr(
        "raiker.runtime.mcp_endpoint_policy._resolve_public", lambda host, port: []
    )
    trust = evaluate_endpoint("https://tools.example.com/mcp")
    assert not trust.allowed
    assert trust.reason == "mcp_remote_host_not_public"


def test_public_endpoint_must_use_https() -> None:
    """An owner typing a hostname did not choose to put their token on the wire
    in clear text."""
    trust = evaluate_endpoint("http://tools.example.com/mcp")
    assert not trust.allowed
    assert trust.reason == "mcp_remote_requires_https"


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://169.254.169.254/latest/meta-data/", "mcp_remote_link_local"),
        ("http://metadata.google.internal/mcp", "mcp_remote_metadata_endpoint"),
        ("http://[fe80::1]/mcp", "mcp_remote_link_local"),
        ("http://224.0.0.1/mcp", "mcp_remote_address_forbidden"),
    ],
)
def test_credential_services_are_never_a_tool_server(url: str, reason: str) -> None:
    trust = evaluate_endpoint(url)
    assert not trust.allowed
    assert trust.reason == reason


def test_ipv4_mapped_loopback_is_read_as_loopback() -> None:
    """`::ffff:127.0.0.1` reports itself as a v6 address whose payload is the
    loopback. Reading only the outer form is a documented way past this kind of
    check; here it means the class is right rather than that access is granted."""
    assert evaluate_endpoint("http://[::ffff:127.0.0.1]:3000/mcp").network_class == LOOPBACK


def test_credentials_in_the_url_are_refused() -> None:
    trust = evaluate_endpoint("https://user:secret@tools.example.com/mcp")
    assert not trust.allowed
    assert trust.reason == "mcp_remote_endpoint_credentials"


@pytest.mark.parametrize(
    "url", ["", "not a url", "ftp://tools.example.com/mcp", "https:///mcp", "file:///etc/passwd"]
)
def test_non_endpoints_are_refused(url: str) -> None:
    trust = evaluate_endpoint(url)
    assert not trust.allowed
    assert trust.reason == "mcp_remote_invalid_endpoint"


def test_unresolvable_name_is_told_apart_from_a_refused_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A machine that is offline and a destination Raiker will not go to are
    different things to read."""
    monkeypatch.setattr(
        "raiker.runtime.mcp_endpoint_policy._resolve_public", lambda host, port: None
    )
    trust = evaluate_endpoint("https://tools.example.com/mcp")
    assert trust.reason == "mcp_remote_host_unresolved"


def test_add_time_check_does_not_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refusing the URL an owner is typing because the machine happens to be
    offline would be a worse answer than classifying it when it is used."""

    def _never(host: str, port: int) -> list[str]:
        raise AssertionError("add-time classification must not resolve")

    monkeypatch.setattr("raiker.runtime.mcp_endpoint_policy._resolve_public", _never)
    assert evaluate_endpoint("https://tools.example.com/mcp", resolve=False).allowed


# ── what the owner reads ────────────────────────────────────────────────────


def test_every_refusal_has_a_sentence_the_owner_can_act_on() -> None:
    reasons = [
        "mcp_remote_invalid_endpoint",
        "mcp_remote_endpoint_credentials",
        "mcp_remote_requires_https",
        "mcp_remote_metadata_endpoint",
        "mcp_remote_link_local",
        "mcp_remote_address_forbidden",
        "mcp_remote_host_not_public",
        "mcp_remote_host_unresolved",
        "mcp_remote_redirect_untrusted",
        "mcp_remote_too_many_redirects",
    ]
    for reason in reasons:
        message = endpoint_refusal_message(reason)
        assert message != "That MCP endpoint was refused.", reason
        assert message.endswith("."), reason


def test_refusal_message_survives_a_detailed_reason_code() -> None:
    """The transport appends the hop's own reason after a colon."""
    assert endpoint_refusal_message(
        "mcp_remote_redirect_untrusted:mcp_remote_host_not_public"
    ) == endpoint_refusal_message("mcp_remote_redirect_untrusted")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:3000/mcp", LOOPBACK),
        ("http://localhost/mcp", LOOPBACK),
        ("https://192.168.0.4/mcp", PRIVATE_NETWORK),
        ("http://nas.lan/mcp", PRIVATE_NETWORK),
        ("https://tools.example.com/mcp", PUBLIC),
        ("ftp://tools.example.com/mcp", None),
    ],
)
def test_stated_class_needs_no_lookup(url: str, expected: str | None) -> None:
    """What a stored server's card renders: never blocks on DNS, never changes
    while the page is open, exactly as honest as the string the owner typed."""
    assert stated_network_class(url) == expected


def test_the_card_no_longer_calls_everything_remote_https() -> None:
    assert network_class_label(LOOPBACK, encrypted=False) == "This machine (unencrypted HTTP)"
    assert network_class_label(PRIVATE_NETWORK, encrypted=False) == "Your network (unencrypted HTTP)"
    assert network_class_label(PUBLIC, encrypted=True) == "Remote (HTTPS)"
    assert network_class_label(None, encrypted=True) == "Remote (unrecognised endpoint)"
