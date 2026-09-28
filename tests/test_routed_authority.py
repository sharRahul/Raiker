"""CR-03 — a governed service skips its own gate only for the router's live token.

The skip used to be ``enforce_modes=False``: a boolean any caller could pass.
These tests hold the replacement to the finding's acceptance line — the skip
cannot be supplied from an action payload, and a direct call cannot skip
authorization — by trying every way a caller other than the router might ask.
"""
from __future__ import annotations

import inspect
import threading
from pathlib import Path
from typing import Any

import pytest

from raiker.runtime import advisor, connectors, web_access
from raiker.runtime.authority.routed import (
    RoutedAuthority,
    current_routed_authority,
    is_routed,
    routed_dispatch,
)
from raiker.storage.sqlite import SQLiteStore

_GOVERNED_SERVICES = (
    connectors.GithubConnectorService,
    connectors.GmailConnectorService,
    connectors.GcalConnectorService,
    connectors.SlackConnectorService,
    web_access.WebAccessService,
    advisor.AdvisorService,
)


def test_no_governed_service_accepts_a_boolean_skip() -> None:
    for service in _GOVERNED_SERVICES:
        for name, method in inspect.getmembers(service, inspect.isfunction):
            params = inspect.signature(method).parameters
            assert "enforce_modes" not in params, f"{service.__name__}.{name}"


def test_a_token_cannot_be_built_by_naming_the_class() -> None:
    with pytest.raises(TypeError):
        RoutedAuthority("web_fetch", "act_1", _issuer=object())


def test_the_token_is_live_only_inside_its_dispatch() -> None:
    with routed_dispatch("web_fetch", "act_1") as token:
        assert is_routed(token, "web_fetch")
        assert current_routed_authority("act_1") is token
        # Another action's id asks for a token it was never issued.
        assert current_routed_authority("act_2") is None
        # A token for one capability does not skip another capability's gate.
        assert not is_routed(token, "connector_github_runtime")
    # Kept past the end of its dispatch, it is just an object.
    assert not is_routed(token, "web_fetch")
    assert current_routed_authority("act_1") is None


@pytest.mark.parametrize("claim", [False, True, None, "routed", {"capability": "web_fetch"}])
def test_nothing_but_the_token_counts(claim: Any) -> None:
    with routed_dispatch("web_fetch", "act_1"):
        assert not is_routed(claim, "web_fetch")


def test_nested_dispatch_restores_the_outer_token() -> None:
    with routed_dispatch("web_fetch", "act_outer") as outer:
        with routed_dispatch("advisor_model_runtime", "act_inner") as inner:
            assert is_routed(inner, "advisor_model_runtime")
            assert not is_routed(outer, "web_fetch")
        assert is_routed(outer, "web_fetch")


def test_a_token_does_not_travel_to_another_thread() -> None:
    seen: list[bool] = []
    with routed_dispatch("web_fetch", "act_1") as token:
        worker = threading.Thread(target=lambda: seen.append(is_routed(token, "web_fetch")))
        worker.start()
        worker.join()
    assert seen == [False]


@pytest.fixture
def github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> connectors.GithubConnectorService:
    monkeypatch.setenv(connectors.GITHUB_TOKEN_ENV, "ghp_test")
    monkeypatch.setattr(
        "raiker.runtime.connectors.connector_egress_allowlist", lambda: {connectors.GITHUB_HOST}
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    store = SQLiteStore(workspace)
    store.bootstrap()
    body = '{"title": "t", "state": "open", "body": "b"}'
    return connectors.GithubConnectorService(
        workspace,
        store,
        principal_id="principal_owner",
        fetch_fn=lambda url, headers: {"body_text": body, "truncated": False},
    )


def test_a_direct_call_meets_the_gate_whatever_it_passes(
    github: connectors.GithubConnectorService,
) -> None:
    # No gate row is persisted for this principal, so governance refuses. The
    # point is that every one of these callers reaches that refusal.
    for claim in (None, False, True, "routed"):
        outcome = github.read("issue", "octo/repo", 1, authority=claim)
        assert outcome["status"] != "success"
        assert outcome["error"]["type"] == "connector_gate_disabled", claim


def test_only_the_live_token_passes_the_gate(github: connectors.GithubConnectorService) -> None:
    with routed_dispatch("connector_github_runtime", "act_1") as token:
        allowed = github.read("issue", "octo/repo", 1, authority=token)
    assert allowed["status"] == "success", allowed
    stale = github.read("issue", "octo/repo", 1, authority=token)
    assert stale["error"]["type"] == "connector_gate_disabled"
