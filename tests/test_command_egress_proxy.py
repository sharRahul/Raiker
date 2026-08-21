from __future__ import annotations

import pytest

from raiker.execution.commands.egress_policy import EgressPolicy
from raiker.execution.commands.egress_proxy import (
    EgressProxyController,
    _parse_authority,
    _proxy_credential,
)


class Socket:
    def __init__(self, *, fails: bool = False) -> None:
        self.closed = False
        self.fails = fails

    def close(self) -> None:
        self.closed = True
        if self.fails:
            raise OSError("injected")


def test_revoke_closes_only_one_runs_live_sockets_and_refuses_new_connections() -> None:
    controller = EgressProxyController()
    policy = EgressPolicy(("api.example.com",), (443,))
    controller.activate("run_a", policy)
    controller.activate("run_b", policy)
    first = Socket()
    second = Socket()
    controller.register_socket("run_a", first)
    controller.register_socket("run_b", second)

    assert controller.revoke("run_a") == 1
    assert first.closed is True
    assert second.closed is False
    assert controller.state("run_a") == "revoked"
    assert controller.authorize(
        "run_b", "api.example.com", 443, ("93.184.216.34",)
    ).verdict == "allowed"
    with pytest.raises(ValueError, match="egress_grant_not_active"):
        controller.authorize("run_a", "api.example.com", 443, ("93.184.216.34",))


def test_failed_socket_cleanup_blocks_the_grant() -> None:
    controller = EgressProxyController()
    controller.activate("run_a", EgressPolicy(("api.example.com",), (443,)))
    controller.register_socket("run_a", Socket(fails=True))
    with pytest.raises(ValueError, match="egress_socket_cleanup_failed"):
        controller.revoke("run_a")
    assert controller.state("run_a") == "cleanup_failed"


def test_standard_basic_proxy_credentials_carry_the_scoped_run_without_a_header() -> None:
    import base64

    encoded = base64.b64encode(b"run_a:signed.token").decode()
    assert _proxy_credential(f"Basic {encoded}", "") == ("run_a", "signed.token")
    with pytest.raises(ValueError, match="egress_token_scope_mismatch"):
        _proxy_credential(f"Basic {encoded}", "run_b")


def test_connect_authority_parser_rejects_missing_and_invalid_ports() -> None:
    assert _parse_authority("api.example.com:443") == ("api.example.com", 443)
    assert _parse_authority("[2001:db8::1]:443") == ("2001:db8::1", 443)
    for value in ("api.example.com", "api.example.com:0", "api.example.com:65536"):
        with pytest.raises(ValueError, match="egress_authority_invalid"):
            _parse_authority(value)
