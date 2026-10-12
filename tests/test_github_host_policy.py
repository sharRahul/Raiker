"""ADD-27 GH-25 — Git transport, API and sign-in traffic answer to separate rules."""

from __future__ import annotations

import pytest

from raiker.github.hosts import api_allowed, control_plane_allowed, transport_allowed
from raiker.github.http import GitHubHttp, GitHubHttpError


def test_allowing_the_api_does_not_allow_git_transport() -> None:
    allowlist = frozenset({"api.github.com"})
    assert api_allowed("api.github.com", allowlist)
    assert not transport_allowed("github.com", allowlist)


def test_allowing_git_transport_does_not_allow_the_api() -> None:
    allowlist = frozenset({"github.com"})
    assert transport_allowed("github.com", allowlist)
    assert not api_allowed("api.github.com", allowlist)


def test_a_wildcard_never_widens_git_transport() -> None:
    """Transport is matched exactly: a glob the API honours is not a Git host."""
    allowlist = frozenset({"*", "*.github.com"})
    assert api_allowed("api.github.com", allowlist)
    assert not transport_allowed("github.com", allowlist)
    assert not transport_allowed("gitlab.com", frozenset({"gitlab.com"}))


def test_the_api_rule_admits_only_the_api_host() -> None:
    assert not api_allowed("uploads.github.com", frozenset({"*"}))


def test_control_plane_requests_reach_only_the_two_fixed_hosts() -> None:
    assert control_plane_allowed("github.com") and control_plane_allowed("api.github.com")
    assert not control_plane_allowed("evil.example.com")
    calls: list[str] = []

    def transport(method, url, headers, body):  # type: ignore[no-untyped-def]
        calls.append(url)
        return 200, {}, b"{}"

    client = GitHubHttp(transport)
    with pytest.raises(GitHubHttpError) as caught:
        client.get_json("https://evil.example.com/user")
    assert caught.value.reason == "github_host_not_allowed:evil.example.com"
    with pytest.raises(GitHubHttpError):
        client.get_json("http://api.github.com/user")
    assert calls == []


def test_a_redirect_is_refused_rather_than_followed() -> None:
    def transport(method, url, headers, body):  # type: ignore[no-untyped-def]
        return 302, {"Location": "https://evil.example.com/"}, b""

    with pytest.raises(GitHubHttpError) as caught:
        GitHubHttp(transport).get_json("https://api.github.com/user", token="t")
    assert caught.value.reason == "github_redirect_refused"


def test_the_token_travels_only_in_the_header_and_is_not_kept() -> None:
    seen: dict[str, object] = {}

    def transport(method, url, headers, body):  # type: ignore[no-untyped-def]
        seen.update(url=url, headers=dict(headers))
        return 200, {"X-OAuth-Scopes": "repo", "Set-Cookie": "drop"}, b'{"login": "octo"}'

    response = GitHubHttp(transport).get_json("https://api.github.com/user", token="ghp_secret")
    assert seen["headers"]["Authorization"] == "Bearer ghp_secret"  # type: ignore[index]
    assert "ghp_secret" not in str(seen["url"])
    assert response.data == {"login": "octo"}
    assert response.headers == {"x-oauth-scopes": "repo"}
