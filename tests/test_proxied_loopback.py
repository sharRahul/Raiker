"""BUG-347 — a reverse proxy in front of a loopback-bound Raiker.

The first fix told a proxy apart by its forwarding headers; review found that a
proxy which sends none is, on the same socket, indistinguishable from this
computer's browser. The classification now comes from the listener a
connection was accepted on:

* the loopback listener is local, and refuses any forwarded request;
* the proxy listener (``--proxy-port`` / ``--proxy-socket``) is remote for
  every request, headers or not;
* a Unix-socket connection is never local.

The tests at the bottom run a real uvicorn server with both listeners, because
the guard relies on what uvicorn puts in ``scope["server"]``.
"""

from __future__ import annotations

import asyncio
import os
import socket
import stat
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from raiker.api import serve
from raiker.api.app import create_app
from raiker.api.proxy_guard import (
    PROXIED_SCOPE_KEY,
    PROXY_RATE_KEY,
    REFUSAL_REASON,
    ProxyGuardMiddleware,
    ProxyListener,
    RemoteAccessRecord,
    is_local_request,
)
from raiker.api.security import RateLimitMiddleware

FORWARDED = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}
PROXY_PORT = 8766


def _clients(tmp_path: Path) -> tuple[TestClient, TestClient]:
    """The same app reached on its local listener (port 80) and its proxy listener."""
    app = create_app(tmp_path, proxy_listener=ProxyListener(port=PROXY_PORT))
    return TestClient(app), TestClient(app, base_url=f"http://testserver:{PROXY_PORT}")


# --- the loopback listener -------------------------------------------------


@pytest.mark.parametrize(
    "header",
    ["Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Real-IP"],
)
def test_any_forwarding_header_is_refused_on_the_local_listener(tmp_path: Path, header: str) -> None:
    client = TestClient(create_app(tmp_path))
    refused = client.get("/api/health", headers={header: "203.0.113.9"})
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["reason_code"] == REFUSAL_REASON
    assert "--proxy-port" in detail["message"] and "--allow-public" in detail["message"]
    # The refusal still carries the security headers.
    assert refused.headers.get("x-frame-options") == "DENY"
    page = client.get("/", headers={header: "203.0.113.9"})
    assert page.status_code == 403
    assert "reverse proxy" in page.text


def test_a_misleading_header_naming_this_computer_is_still_refused(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


def test_a_direct_local_request_is_unchanged(tmp_path: Path) -> None:
    local, _proxy = _clients(tmp_path)
    assert local.get("/api/health").status_code == 200
    assert "recovery_loopback_only" not in local.get("/api/recovery/backups").text


# --- the proxy listener ----------------------------------------------------


def test_the_proxy_listener_is_remote_without_any_forwarding_header(tmp_path: Path) -> None:
    """The case the header check could not see: a proxy that sends nothing."""
    _local, proxy = _clients(tmp_path)
    assert proxy.get("/api/health").status_code == 200
    refused = proxy.get("/api/recovery/backups")
    assert refused.status_code == 403
    assert "recovery_loopback_only" in refused.text
    instance = proxy.post("/api/instances", json={"name": "second"})
    assert instance.status_code == 403 and "loopback_only" in instance.text


def test_a_header_on_the_proxy_listener_cannot_make_it_local(tmp_path: Path) -> None:
    _local, proxy = _clients(tmp_path)
    served = proxy.get("/api/recovery/backups", headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "::1"})
    assert served.status_code == 403
    assert "recovery_loopback_only" in served.text


def test_the_proxy_listener_adds_hsts_only_when_the_proxy_received_https(tmp_path: Path) -> None:
    _local, proxy = _clients(tmp_path)
    secure = proxy.get("/api/health", headers=FORWARDED)
    assert secure.headers.get("strict-transport-security", "").startswith("max-age=")
    assert "strict-transport-security" not in proxy.get("/api/health").headers


def test_proxied_reads_are_rate_limited_in_their_own_bucket(tmp_path: Path) -> None:
    app = create_app(tmp_path, rate_limit_per_minute=3, proxy_listener=ProxyListener(port=PROXY_PORT))
    local = TestClient(app)
    proxy = TestClient(app, base_url=f"http://testserver:{PROXY_PORT}")
    codes = [proxy.get("/api/health").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    # This computer's reads stay exempt and are not charged to the proxy's bucket.
    assert all(local.get("/api/health").status_code == 200 for _ in range(5))


def test_the_rate_key_of_a_proxied_request_is_not_the_reported_address() -> None:
    middleware = RateLimitMiddleware(app=lambda *_: None, loopback_only=True)  # type: ignore[arg-type]
    local = {"type": "http", "method": "GET", "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 8765), "headers": []}
    forwarded = {**local, "headers": [(b"x-forwarded-for", b"203.0.113.9")]}
    proxied = {**local, PROXIED_SCOPE_KEY: True}
    assert middleware._safe_loopback_read(local) is True
    assert middleware._safe_loopback_read(forwarded) is False
    assert middleware._safe_loopback_read(proxied) is False
    assert middleware._client_key(proxied) == PROXY_RATE_KEY


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_ipv4_and_ipv6_loopback_are_local_only_on_the_local_listener(peer: str) -> None:
    listener = ProxyListener(port=PROXY_PORT)
    local = {"type": "http", "client": (peer, 5000), "server": (peer, 8765), "headers": []}
    on_proxy = {**local, "server": (peer, PROXY_PORT)}
    assert is_local_request(local) is True
    assert listener.accepted(local) is False
    assert listener.accepted(on_proxy) is True


def test_a_unix_socket_connection_is_never_local() -> None:
    for server in (None, ("/run/raiker/proxy.sock", None)):
        scope: dict[str, Any] = {"type": "http", "client": None, "server": server, "headers": []}
        assert is_local_request(scope) is False
    assert ProxyListener(socket_path="/run/raiker/proxy.sock").accepted(
        {"server": ("/run/raiker/proxy.sock", None)}
    )


def _probe() -> tuple[list[dict[str, Any]], Any]:
    seen: list[dict[str, Any]] = []

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        seen.append(scope)
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})

    return seen, app


def _run(guard: ProxyGuardMiddleware, scope: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(guard(scope, receive, send))  # type: ignore[arg-type]
    return sent


def test_websockets_follow_the_listener_too() -> None:
    seen, app = _probe()
    listener = ProxyListener(port=PROXY_PORT)
    guard = ProxyGuardMiddleware(
        app, loopback_only=True, record=RemoteAccessRecord(loopback_only=True, listener=listener), listener=listener
    )
    base = {"type": "websocket", "path": "/ws", "client": ("127.0.0.1", 1), "headers": []}
    # On the proxy listener, with no header: accepted, and marked remote.
    assert _run(guard, {**base, "server": ("127.0.0.1", PROXY_PORT)}) == [{"type": "websocket.accept"}]
    assert seen[-1][PROXIED_SCOPE_KEY] is True and is_local_request(seen[-1]) is False
    # On the local listener with a forwarding header: closed before the app sees it.
    count = len(seen)
    closed = _run(guard, {**base, "server": ("127.0.0.1", 8765), "headers": [(b"x-forwarded-for", b"203.0.113.9")]})
    assert closed == [{"type": "websocket.close", "code": 1008}]
    assert len(seen) == count


# --- Diagnostics and start-up ---------------------------------------------


def test_diagnostics_names_the_listener_and_the_refusals(tmp_path: Path) -> None:
    local, proxy = _clients(tmp_path)
    token = local.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    local.get("/api/health", headers={"X-Forwarded-For": "203.0.113.9"})
    proxy.get("/api/health")
    remote = local.get("/api/diagnostics", headers=h).json()["remote_access"]
    assert remote["mode"] == "proxy_listener"
    assert remote["proxy_listener"] == f"127.0.0.1:{PROXY_PORT}"
    assert remote["proxied_requests_refused"] == 1
    assert remote["proxied_requests_served"] >= 1
    plain = TestClient(create_app(tmp_path / "plain"))
    token = plain.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    view = plain.get("/api/diagnostics", headers={"Authorization": f"Bearer {token}"}).json()["remote_access"]
    assert view["mode"] == "loopback" and view["proxy_listener"] is None


@pytest.mark.parametrize(
    ("argv", "env"),
    [
        (["--proxy-port", "8766"], {}),  # no owner token
        (["--proxy-port", "8765"], {"RAIKER_OWNER_TOKEN": "x" * 40}),  # same as --port
        (["--proxy-port", "8766", "--proxy-socket", "/tmp/r.sock"], {"RAIKER_OWNER_TOKEN": "x" * 40}),
        (["--proxy-port", "8766", "--host", "10.0.0.5", "--allow-public"], {"RAIKER_OWNER_TOKEN": "x" * 40}),
        ([], {"RAIKER_TRUSTED_PROXY": "127.0.0.1"}),  # the first fix's setting is refused, not read
    ],
)
def test_a_proxy_listener_that_cannot_be_trusted_refuses_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], env: dict[str, str]
) -> None:
    monkeypatch.delenv("RAIKER_OWNER_TOKEN", raising=False)
    monkeypatch.delenv("RAIKER_TRUSTED_PROXY", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("uvicorn.run", lambda *_a, **_k: pytest.fail("must not start"))
    assert serve.main(["--workspace", str(tmp_path), "--no-browser", *argv]) == 2


def test_the_server_never_lets_uvicorn_rewrite_the_peer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """uvicorn trusts X-Forwarded-For from 127.0.0.1 by default and rewrites the
    socket peer from it, which would make a header decide who the client is."""
    seen: dict[str, object] = {}

    def fake_run(_app: object, **kwargs: object) -> None:
        seen.update(kwargs)

    monkeypatch.delenv("RAIKER_TRUSTED_PROXY", raising=False)
    monkeypatch.setattr("uvicorn.run", fake_run)
    assert serve.main(["--workspace", str(tmp_path), "--no-browser", "--port", "8799"]) in (0, None)
    assert seen["proxy_headers"] is False
    assert seen["forwarded_allow_ips"] == ""
    source = (Path(__file__).resolve().parents[1] / "raiker" / "app" / "launcher.py").read_text(encoding="utf-8")
    assert "proxy_headers=False" in source


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix domain sockets")
def test_the_proxy_socket_replaces_only_a_stale_socket_and_is_not_world_open(tmp_path: Path) -> None:
    path = tmp_path / "proxy.sock"
    first = serve._bind_proxy_listener(ProxyListener(socket_path=str(path)))
    first.close()
    assert stat.S_ISSOCK(path.lstat().st_mode)
    second = serve._bind_proxy_listener(ProxyListener(socket_path=str(path)))  # stale socket replaced
    try:
        assert stat.S_IMODE(os.stat(path).st_mode) & 0o007 == 0
        second.listen(1)
        with pytest.raises(OSError, match="in use"):  # a live socket is never taken over
            serve._bind_proxy_listener(ProxyListener(socket_path=str(path)))
    finally:
        second.close()
    path.unlink()
    path.write_text("not a socket")
    with pytest.raises(OSError):
        serve._bind_proxy_listener(ProxyListener(socket_path=str(path)))
    assert path.read_text() == "not a socket"


# --- a real server with both listeners ------------------------------------


def _free_socket(host: str = "127.0.0.1") -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, 0))
    return sock


@contextmanager
def _serve(app: Any, sockets: list[socket.socket]) -> Iterator[None]:
    config = uvicorn.Config(app, proxy_headers=False, forwarded_allow_ips="", log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": sockets}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("server did not start")
        time.sleep(0.05)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        for sock in sockets:
            sock.close()


@pytest.fixture()
def served(tmp_path: Path) -> Iterator[dict[str, Any]]:
    local = _free_socket()
    proxy = _free_socket()
    proxy_port = proxy.getsockname()[1]
    app = create_app(tmp_path, proxy_listener=ProxyListener(port=proxy_port))
    with _serve(app, [local, proxy]):
        yield {"local": f"http://127.0.0.1:{local.getsockname()[1]}", "proxy": f"http://127.0.0.1:{proxy_port}"}


def test_a_real_server_tells_its_listeners_apart(served: dict[str, Any]) -> None:
    with httpx.Client(timeout=10) as http:
        # This computer, directly: local.
        assert "recovery_loopback_only" not in http.get(served["local"] + "/api/recovery/backups").text
        # A proxy that forwards with no header at all: remote.
        stripped = http.get(served["proxy"] + "/api/recovery/backups")
        assert stripped.status_code == 403 and "recovery_loopback_only" in stripped.text
        # A proxy pointed at the local listener that says it is one: refused.
        wrong = http.get(served["local"] + "/api/health", headers={"X-Forwarded-For": "203.0.113.9"})
        assert wrong.status_code == 403 and wrong.json()["detail"]["reason_code"] == REFUSAL_REASON
        # A header claiming this computer on the proxy listener changes nothing.
        spoofed = http.get(served["proxy"] + "/api/recovery/backups", headers={"X-Forwarded-For": "127.0.0.1"})
        assert spoofed.status_code == 403 and "recovery_loopback_only" in spoofed.text


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Unix domain sockets")
def test_a_real_unix_socket_listener_is_remote(tmp_path: Path) -> None:
    path = tmp_path / "proxy.sock"
    listener = ProxyListener(socket_path=str(path))
    app = create_app(tmp_path / "ws", proxy_listener=listener)
    local = _free_socket()
    uds = serve._bind_proxy_listener(listener)
    transport = httpx.HTTPTransport(uds=str(path))
    with _serve(app, [local, uds]), httpx.Client(transport=transport, timeout=10) as http:
        assert http.get("http://raiker/api/health").status_code == 200
        refused = http.get("http://raiker/api/recovery/backups")
        assert refused.status_code == 403 and "recovery_loopback_only" in refused.text


def test_a_real_ipv6_loopback_listener_is_local(tmp_path: Path) -> None:
    try:
        local = _free_socket("::1")
    except OSError:
        pytest.skip("no IPv6 loopback on this host")
    proxy = _free_socket()
    app = create_app(tmp_path, proxy_listener=ProxyListener(port=proxy.getsockname()[1]))
    with _serve(app, [local, proxy]), httpx.Client(timeout=10) as http:
        direct = http.get(f"http://[::1]:{local.getsockname()[1]}/api/recovery/backups")
        assert "recovery_loopback_only" not in direct.text
