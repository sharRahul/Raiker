# SPDX-License-Identifier: Apache-2.0
"""BUG-352 — a card's route follows the endpoint the owner saved."""

from __future__ import annotations

from types import SimpleNamespace

from raiker.control.dashboard_parts.models import _effective_endpoint_kind


def _profile(kind: str = "local_machine") -> SimpleNamespace:
    return SimpleNamespace(raw={"endpoint_kind": kind, "endpoint": "http://127.0.0.1:8000/v1"})


def test_a_saved_internet_endpoint_reads_as_hosted() -> None:
    saved = {"endpoint": "https://models.raiker-live.example/v1"}
    assert _effective_endpoint_kind(_profile(), saved) == "remote_hosted"


def test_a_saved_lan_endpoint_reads_as_private_network() -> None:
    assert _effective_endpoint_kind(_profile(), {"endpoint": "http://192.168.1.20:8000/v1"}) == "private_network"


def test_no_saved_endpoint_keeps_the_shipped_kind() -> None:
    assert _effective_endpoint_kind(_profile("remote_hosted"), None) == "remote_hosted"
    assert _effective_endpoint_kind(_profile(), {"api_key": "x"}) == "local_machine"


def test_an_unreadable_saved_endpoint_keeps_the_shipped_kind() -> None:
    assert _effective_endpoint_kind(_profile(), {"endpoint": "ftp://nowhere"}) == "local_machine"
