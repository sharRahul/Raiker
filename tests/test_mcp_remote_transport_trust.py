"""RR-MCP-02 — the boundary is at the socket, not at the form.

Classifying an endpoint when the owner types it is worth doing and proves
nothing: a server answers, and then moves the session. These cover what happens
between the check and the bytes.

* A redirect is a new destination, so it is classified again — a server cannot
  send a session somewhere the endpoint itself would have been refused.
* The owner's token is for the server the owner gave it to, so it does not
  travel across an origin change.
* A public name is dialled at an address that already passed the guard, so the
  name cannot be re-resolved into somewhere private between the check and the
  connect.
"""
from __future__ import annotations

from typing import Any

import pytest

from raiker.runtime.executors import sandbox
from raiker.runtime.executors.sandbox import SandboxError, post_json_rpc


class _Response:
    """Enough of an HTTP response for the transport to read."""

    def __init__(self, status: int, body: str, headers: dict[str, str]) -> None:
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = headers

    def read(self, size: int) -> bytes:
        return self._body[:size]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Transport:
    """Records every hop, and answers each with a scripted response."""

    def __init__(self, script: list[_Response]) -> None:
        self._script = script
        self.hops: list[tuple[str, dict[str, str], str | None]] = []

    def opener(self, trust: Any) -> Any:
        transport = self

        class _Opener:
            def open(self, request: Any, timeout: float) -> _Response:
                transport.hops.append(
                    (request.full_url, dict(request.header_items()), trust.pin)
                )
                if not transport._script:
                    raise AssertionError("more hops than the script has answers")
                return transport._script.pop(0)

        return _Opener()


def _ok(body: str = '{"jsonrpc":"2.0","id":1,"result":{}}') -> _Response:
    return _Response(200, body, {"Content-Type": "application/json"})


def _redirect(location: str) -> _Response:
    return _Response(307, "", {"Location": location})


@pytest.fixture
def public_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every public name in these tests answers with one documentation address."""
    monkeypatch.setattr(
        "raiker.runtime.mcp_endpoint_policy._resolve_public",
        lambda host, port: ["203.0.113.10"],
    )


def test_a_redirect_into_private_space_is_refused(
    monkeypatch: pytest.MonkeyPatch, public_resolution: None
) -> None:
    transport = _Transport([_redirect("http://169.254.169.254/latest/meta-data/")])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    with pytest.raises(SandboxError) as refusal:
        post_json_rpc("https://tools.example.com/mcp", {"jsonrpc": "2.0"})

    # Named as the server moving the session, not as a property of the URL the
    # owner typed — two different things for an owner to read.
    assert str(refusal.value).startswith("mcp_remote_redirect_untrusted:")
    assert "mcp_remote_link_local" in str(refusal.value)
    assert len(transport.hops) == 1, "the refused hop must not be dialled"


def test_the_owner_token_does_not_follow_a_redirect_to_another_origin(
    monkeypatch: pytest.MonkeyPatch, public_resolution: None
) -> None:
    transport = _Transport([_redirect("https://other.example.net/mcp"), _ok()])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    post_json_rpc(
        "https://tools.example.com/mcp",
        {"jsonrpc": "2.0"},
        headers={"Authorization": "Bearer owner-token"},
    )

    first, second = transport.hops
    assert first[1]["Authorization"] == "Bearer owner-token"
    assert "Authorization" not in second[1]
    assert second[0] == "https://other.example.net/mcp"


def test_a_redirect_within_one_origin_keeps_the_token(
    monkeypatch: pytest.MonkeyPatch, public_resolution: None
) -> None:
    """Path normalisation is what a real deployment does, and it is the same
    server: refusing it would break servers that are behaving correctly."""
    transport = _Transport([_redirect("/mcp/v1"), _ok()])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    post_json_rpc(
        "https://tools.example.com/mcp",
        {"jsonrpc": "2.0"},
        headers={"Authorization": "Bearer owner-token"},
    )

    second = transport.hops[1]
    assert second[0] == "https://tools.example.com/mcp/v1"
    assert second[1]["Authorization"] == "Bearer owner-token"


def test_a_redirect_loop_ends_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch, public_resolution: None
) -> None:
    transport = _Transport([_redirect("https://tools.example.com/mcp")] * 8)
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    with pytest.raises(SandboxError) as refusal:
        post_json_rpc("https://tools.example.com/mcp", {"jsonrpc": "2.0"})

    assert str(refusal.value) == "mcp_remote_too_many_redirects"
    assert len(transport.hops) == 4, "three redirects followed, then stop"


def test_a_public_endpoint_is_dialled_at_the_address_that_passed(
    monkeypatch: pytest.MonkeyPatch, public_resolution: None
) -> None:
    """Validating a name and then handing that name to the HTTP client resolves
    it a second time, and the second answer does not have to match the first."""
    transport = _Transport([_ok()])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    post_json_rpc("https://tools.example.com/mcp", {"jsonrpc": "2.0"})

    assert transport.hops[0][2] == "203.0.113.10"


def test_a_local_server_is_not_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    """On loopback the owner's own resolver is the authority, and pinning would
    only break split-horizon DNS for no boundary gained."""
    transport = _Transport([_ok()])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    post_json_rpc("http://127.0.0.1:8931/mcp", {"jsonrpc": "2.0"})

    assert transport.hops[0][2] is None


def test_a_refused_endpoint_never_reaches_the_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _Transport([_ok()])
    monkeypatch.setattr(sandbox, "_mcp_opener", transport.opener)

    with pytest.raises(SandboxError) as refusal:
        post_json_rpc("http://metadata.google.internal/mcp", {"jsonrpc": "2.0"})

    assert str(refusal.value) == "mcp_remote_metadata_endpoint"
    assert transport.hops == []


def test_ending_a_session_goes_through_the_same_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A courtesy DELETE is still a request carrying the owner's token."""
    called: list[str] = []

    def _record(trust: Any) -> Any:
        called.append(trust.host)
        return _Transport([]).opener(trust)

    monkeypatch.setattr(sandbox, "_mcp_opener", _record)

    assert sandbox.delete_mcp_session("http://169.254.169.254/mcp") == 0
    assert called == [], "a refused destination is not opened"


def test_the_real_transport_does_not_follow_a_redirect_itself() -> None:
    """The tests above replace the opener, which proves the decision and not the
    machinery. This one runs a real socket: a local server answers 307 pointing
    at the cloud metadata address, and the refusal has to come from Raiker
    rather than from the connection failing somewhere out on the link-local
    network.

    ``urllib`` follows a redirect by itself unless something stops it, and what
    stops it is a handler that must actually be installed on the opener — a
    property no amount of substituting the opener can check.
    """
    import http.server
    import threading

    class _Redirecting(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - the name the base class dispatches on
            self.send_response(307)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), _Redirecting)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
        with pytest.raises(SandboxError) as refusal:
            post_json_rpc(url, {"jsonrpc": "2.0"}, timeout=5.0)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert str(refusal.value).startswith("mcp_remote_redirect_untrusted:")
