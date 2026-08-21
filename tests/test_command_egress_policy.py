from __future__ import annotations

import time
from pathlib import Path

import pytest

from raiker.execution.commands.egress_policy import (
    EgressPolicy,
    domain_matches,
    normalize_domain,
)
from raiker.execution.commands.egress_tokens import EgressTokenAuthority, EgressTokenClaims
from raiker.execution.commands.models import CommandRequest
from raiker.execution.commands.store import CommandStore
from raiker.storage.sqlite import SQLiteStore


def test_idna_and_wildcard_matching_are_boundary_aware() -> None:
    assert normalize_domain("BÜCHER.example.") == "xn--bcher-kva.example"
    assert domain_matches("*.example.com", "api.example.com")
    assert not domain_matches("*.example.com", "example.com")
    assert not domain_matches("*.example.com", "badexample.com")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fe80::1", "224.0.0.1"],
)
def test_private_link_local_loopback_and_multicast_answers_fail_closed(address: str) -> None:
    policy = EgressPolicy(("api.example.com",), (443,))
    with pytest.raises(ValueError, match="egress_address_not_public"):
        policy.permits("api.example.com", 443, (address,))


def test_policy_binds_exact_port_and_public_address_set() -> None:
    policy = EgressPolicy(("api.example.com",), (443,))
    assert policy.permits("api.example.com", 443, ("93.184.216.34",)) == (
        "93.184.216.34",
    )
    with pytest.raises(ValueError, match="egress_destination_denied"):
        policy.permits("api.example.com", 80, ("93.184.216.34",))


def test_token_is_expiring_single_use_and_bound_to_owner_profile_and_run() -> None:
    authority = EgressTokenAuthority(b"k" * 32)
    claims = EgressTokenClaims(
        "owner_a", "profile_a", "run_a", "grant_digest", "nonce_a", int(time.time()) + 60
    )
    token = authority.issue(claims)
    assert authority.consume(
        token, owner_principal_id="owner_a", profile_id="profile_a", run_id="run_a"
    ) == claims
    # Data-plane verification may be reused by an HTTP client opening another
    # CONNECT tunnel; one-shot control-plane consumption still rejects replay.
    assert authority.verify(
        token, owner_principal_id="owner_a", profile_id="profile_a", run_id="run_a"
    ) == claims
    with pytest.raises(ValueError, match="egress_token_replayed"):
        authority.consume(
            token, owner_principal_id="owner_a", profile_id="profile_a", run_id="run_a"
        )

    other = authority.issue(
        EgressTokenClaims("owner_a", "profile_a", "run_b", "digest", "nonce_b", 10)
    )
    with pytest.raises(ValueError, match="egress_token_scope_mismatch"):
        authority.consume(
            other,
            owner_principal_id="owner_b",
            profile_id="profile_a",
            run_id="run_b",
            now=1,
        )
    with pytest.raises(ValueError, match="egress_token_expired"):
        authority.consume(
            other,
            owner_principal_id="owner_a",
            profile_id="profile_a",
            run_id="run_b",
            now=10,
        )


def test_durable_grant_lifecycle_is_compare_and_swap(tmp_path: Path) -> None:
    store = CommandStore(SQLiteStore(tmp_path))
    request = CommandRequest(
        "run_a", "owner_a", "agent_a", "session_a", "turn_a", "action_a", None,
        tmp_path, ".", "", ("git", "status"), "git status", (), False, False,
        False, 30, 100_000, "profile_a", None,
    )
    store.create(request)
    policy = EgressPolicy(("api.example.com",), (443,))
    store.create_egress_grant(
        grant_id="grant_a",
        owner_principal_id="owner_a",
        run_id="run_a",
        environment_profile_id="profile_a",
        domains=policy.domains,
        ports=policy.ports,
        grant_digest=policy.digest,
        expires_at="2099-01-01T00:00:00Z",
    )
    assert store.transition_egress_grant(
        "owner_a", "run_a", expected="pending", target="active"
    )
    assert not store.transition_egress_grant(
        "owner_a", "run_a", expected="pending", target="active"
    )
    grant = store.egress_grant("owner_a", "run_a")
    assert grant is not None
    assert grant["state"] == "active"
