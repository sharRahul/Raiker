"""SSRF — no outbound helper follows a redirect to a host it was not given (BUG-350).

Reproduces the bug record's own evidence: two loopback servers, the first on
the allowlist answering ``302`` to the second, which is not. Before the fix,
``get_url`` followed it and the second server received the owner's
``Authorization`` header. Each helper now refuses the redirect by name and the
second server receives nothing.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from raiker.runtime.executors.sandbox import SandboxError, get_url, post_json_url, post_url


class _Target(BaseHTTPRequestHandler):
    hits: list[str] = []

    def _any(self) -> None:
        _Target.hits.append(self.headers.get("Authorization", ""))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    do_GET = do_POST = do_PATCH = _any

    def log_message(self, *args: object) -> None:
        return None


def _serve(handler: type[BaseHTTPRequestHandler]) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def servers(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str]]:
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    _Target.hits = []
    target = _serve(_Target)
    target_url = f"http://127.0.0.1:{target.server_port}/stolen"

    class _Redirect(BaseHTTPRequestHandler):
        def _any(self) -> None:
            self.send_response(302)
            self.send_header("Location", target_url)
            self.end_headers()

        do_GET = do_POST = do_PATCH = _any

        def log_message(self, *args: object) -> None:
            return None

    first = _serve(_Redirect)
    try:
        yield f"127.0.0.1:{first.server_port}", f"http://127.0.0.1:{first.server_port}/api"
    finally:
        first.shutdown()
        target.shutdown()


def test_get_url_refuses_a_redirect_and_the_token_goes_nowhere(servers: tuple[str, str]) -> None:
    host, url = servers
    with pytest.raises(SandboxError, match="redirect_refused:302"):
        get_url(url, egress_allowlist=frozenset({host}), headers={"Authorization": "Bearer tok"})
    assert _Target.hits == []


def test_post_url_refuses_a_redirect(servers: tuple[str, str]) -> None:
    host, url = servers
    with pytest.raises(SandboxError, match="redirect_refused:302"):
        post_url(url, b"{}", egress_allowlist=frozenset({host}), headers={"Authorization": "Bearer tok"})
    assert _Target.hits == []


def test_post_json_url_refuses_a_redirect(servers: tuple[str, str]) -> None:
    host, url = servers
    with pytest.raises(SandboxError, match="redirect_refused:302"):
        post_json_url(url, {}, egress_allowlist=frozenset({host}), headers={"Authorization": "Bearer tok"}, method="PATCH")
    assert _Target.hits == []


@pytest.mark.parametrize(
    ("host", "public"),
    [
        ("github.com", True),
        ("docs.python.org", True),
        ("xn--bcher-kva.example.de", True),
        ("intranet", False),
        ("wiki.corp", False),
        ("db.internal", False),
        ("nas.lan", False),
        ("printer.local", False),
        ("router.home.arpa", False),
        ("10.0.0.5", False),
        ("bad_label.com", False),
    ],
)
def test_only_public_shaped_names_may_take_the_proxy(host: str, public: bool) -> None:
    from raiker.runtime.web_policy import public_shaped_name

    assert public_shaped_name(host) is public


def test_an_internal_name_is_refused_not_proxied(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSRF — the owner's proxy may resolve internal names Raiker cannot check."""
    from raiker.runtime import web_policy

    monkeypatch.setattr(web_policy, "resolve_public_addresses", lambda host, port=443: [])
    monkeypatch.setattr(web_policy, "resolves_at_all", lambda host, port=443: False)
    monkeypatch.setattr(web_policy, "web_proxy_for", lambda scheme, host, port=None: "http://127.0.0.1:3128")
    monkeypatch.setattr(web_policy, "resolve_via_proxy", lambda host, proxy: ["140.82.112.3"])
    internal = web_policy.evaluate_host("wiki.corp", (), allow_proxy=True, flag_owner_rules=True)
    assert not internal.allowed and internal.reason_code.startswith("web_host_unresolved")
    public = web_policy.evaluate_host("github.com", (), allow_proxy=True, flag_owner_rules=True)
    assert public.allowed and public.route == "proxy"


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "0.0.0.0", "224.0.0.1", "192.0.0.1", "198.18.0.1",
        "::1", "fd00::1", "fe80::1", "::ffff:10.0.0.1", "64:ff9b::a00:1", "2002:a00:1::",
    ],
)
def test_the_address_guard_refuses_every_non_public_address(address: str) -> None:
    """SSRF — loopback, private, link-local, metadata, CGNAT and embedded IPv4 forms."""
    import ipaddress

    from raiker.runtime.web_policy import address_is_reachable

    assert address_is_reachable(ipaddress.ip_address(address)) is False


def test_a_proxied_name_is_looked_up_and_its_answers_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSRF (owner's decision, 2026-10-26): DNS over HTTPS through the proxy, fail closed."""
    from raiker.runtime import web_policy

    monkeypatch.setattr(web_policy, "resolve_public_addresses", lambda host, port=443: [])
    monkeypatch.setattr(web_policy, "resolves_at_all", lambda host, port=443: False)
    monkeypatch.setattr(web_policy, "web_proxy_for", lambda scheme, host, port=None: "http://127.0.0.1:3128")
    answers: dict[str, list[str] | None] = {
        "rebind.example.org": ["10.0.0.5"],
        "mixed.example.org": ["140.82.112.3", "169.254.169.254"],
        "gone.example.org": [],
        "unchecked.example.org": None,
        "fine.example.org": ["140.82.112.3"],
    }
    monkeypatch.setattr(web_policy, "resolve_via_proxy", lambda host, proxy: answers[host])

    def reason(host: str) -> str:
        decision = web_policy.evaluate_host(host, (), allow_proxy=True, flag_owner_rules=True)
        return "allowed" if decision.allowed else decision.reason_code.split(":")[0]

    assert reason("rebind.example.org") == "web_host_not_public"
    assert reason("mixed.example.org") == "web_host_not_public"
    assert reason("gone.example.org") == "web_host_unresolved"
    assert reason("unchecked.example.org") == "web_host_unverified"
    assert reason("fine.example.org") == "allowed"


def test_the_lookup_reads_a_and_aaaa_answers_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import json

    from raiker.runtime import web_policy

    replies = {
        "A": {"Status": 0, "Answer": [{"type": 5, "data": "alias.example.org."}, {"type": 1, "data": "140.82.112.3"}]},
        "AAAA": {"Status": 0, "Answer": [{"type": 28, "data": "2606:50c0:8000::153"}]},
    }
    seen: list[str] = []

    class _Opener:
        def open(self, request: object, timeout: float) -> io.BytesIO:
            url = request.full_url  # type: ignore[attr-defined]
            seen.append(url)
            kind = url.rsplit("type=", 1)[1]
            return io.BytesIO(json.dumps(replies[kind]).encode())

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: _Opener())
    monkeypatch.delenv(web_policy.DOH_ENDPOINT_ENV, raising=False)
    assert web_policy.resolve_via_proxy("github.com", "http://127.0.0.1:3128") == ["140.82.112.3", "2606:50c0:8000::153"]
    assert all(url.startswith("https://cloudflare-dns.com/dns-query?name=github.com") for url in seen)
    replies["A"] = {"Status": 2}
    assert web_policy.resolve_via_proxy("github.com", "http://127.0.0.1:3128") is None
    monkeypatch.setenv(web_policy.DOH_ENDPOINT_ENV, "http://resolver.lan/dns-query")
    assert web_policy.resolve_via_proxy("github.com", "http://127.0.0.1:3128") is None
