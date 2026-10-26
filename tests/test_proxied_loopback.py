"""BUG-347 — which requests come from this computer, decided by the listener.

The first fix told a proxy apart by its forwarding headers; review found that a
proxy which sends none is, on the same socket, indistinguishable from this
computer's browser. The classification comes from the listener a connection
was accepted on:

* the local listener is local, and refuses any forwarded request;
* the remote listener (a proxy port or socket, or a private-network HTTPS
  address) is remote for every request, headers or not, and answers only HTTPS;
* a Unix-socket connection is never local.

The tests at the bottom run real uvicorn servers with both listeners, including
one serving TLS, because the guard relies on what uvicorn puts in the scope.
They also hold the restart fix found on the way: Restart returns exit status
75 and a SIGTERM lets the host return instead of dying by signal.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from raiker.api import serve, server_runner
from raiker.api.app import create_app
from raiker.api.proxy_guard import (
    HTTPS_REASON,
    PROXY_RATE_KEY,
    REFUSAL_REASON,
    REMOTE_SCOPE_KEY,
    ProxyGuardMiddleware,
    RemoteAccessRecord,
    RemoteListener,
    is_local_request,
)
from raiker.api.security import RateLimitMiddleware

HTTPS = {"X-Forwarded-Proto": "https"}
PROXY_PORT = 8766


def _clients(tmp_path: Path) -> tuple[TestClient, TestClient]:
    """The same app on its local listener (port 80) and on its proxy listener over HTTPS."""
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=PROXY_PORT))
    return TestClient(app), TestClient(app, base_url=f"https://testserver:{PROXY_PORT}", headers=HTTPS)


def _reason(response: Any) -> str:
    return str(response.json()["detail"]["reason_code"])


# --- the local listener --------------------------------------------------------


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
    assert "Remote access" in detail["message"] and "--proxy-port" in detail["message"]
    assert refused.headers.get("x-frame-options") == "DENY"
    page = client.get("/", headers={header: "203.0.113.9"})
    assert page.status_code == 403 and "reverse proxy" in page.text


def test_a_misleading_header_naming_this_computer_is_still_refused(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


def test_a_direct_local_request_is_unchanged(tmp_path: Path) -> None:
    local, _proxy = _clients(tmp_path)
    assert local.get("/api/health").status_code == 200
    assert "recovery_loopback_only" not in local.get("/api/recovery/backups").text


# --- the remote listener ------------------------------------------------------


def test_the_proxy_listener_is_remote_without_any_forwarding_header_but_https(tmp_path: Path) -> None:
    _local, proxy = _clients(tmp_path)
    assert proxy.get("/api/health").status_code == 200
    refused = proxy.get("/api/recovery/backups")
    assert refused.status_code == 403 and "recovery_loopback_only" in refused.text
    instance = proxy.post("/api/instances", json={"name": "second"})
    assert instance.status_code == 403 and "loopback_only" in instance.text


def test_a_header_on_the_proxy_listener_cannot_make_it_local(tmp_path: Path) -> None:
    _local, proxy = _clients(tmp_path)
    served = proxy.get("/api/recovery/backups", headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "::1"})
    assert served.status_code == 403 and "recovery_loopback_only" in served.text


def test_the_remote_listener_answers_only_https(tmp_path: Path) -> None:
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=PROXY_PORT))
    plain = TestClient(app, base_url=f"http://testserver:{PROXY_PORT}")
    refused = plain.get("/api/auth/session-state")
    assert refused.status_code == 403 and _reason(refused) == HTTPS_REASON
    assert plain.get("/", follow_redirects=False).status_code == 403
    # The one exception is the health probe a proxy uses.
    assert plain.get("/api/health").status_code == 200
    secure = TestClient(app, base_url=f"https://testserver:{PROXY_PORT}", headers=HTTPS).get("/api/health")
    assert secure.headers.get("strict-transport-security", "").startswith("max-age=")


def test_a_private_listener_needs_the_tls_scheme_not_a_header(tmp_path: Path) -> None:
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="private", host="10.0.0.5", port=8443))
    # A forwarded header proves nothing on a private listener.
    plain = TestClient(app, base_url="http://10.0.0.5:8443", headers=HTTPS)
    assert _reason(plain.get("/api/auth/session-state")) == HTTPS_REASON
    tls = TestClient(app, base_url="https://10.0.0.5:8443")
    assert tls.get("/api/auth/session-state").status_code == 200
    assert "recovery_loopback_only" in tls.get("/api/recovery/backups").text


def test_proxied_reads_are_rate_limited_in_their_own_bucket(tmp_path: Path) -> None:
    app = create_app(tmp_path, rate_limit_per_minute=3, proxy_listener=RemoteListener(kind="proxy", port=PROXY_PORT))
    local = TestClient(app)
    proxy = TestClient(app, base_url=f"https://testserver:{PROXY_PORT}", headers=HTTPS)
    codes = [proxy.get("/api/health").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert all(local.get("/api/health").status_code == 200 for _ in range(5))


def test_the_rate_key_of_a_proxied_request_is_not_the_reported_address() -> None:
    middleware = RateLimitMiddleware(app=lambda *_: None, loopback_only=True)  # type: ignore[arg-type]
    local = {"type": "http", "method": "GET", "client": ("127.0.0.1", 1), "server": ("127.0.0.1", 8765), "headers": []}
    forwarded = {**local, "headers": [(b"x-forwarded-for", b"203.0.113.9")]}
    proxied = {**local, REMOTE_SCOPE_KEY: True}
    private_peer = {**proxied, "client": ("10.0.0.9", 5)}
    assert middleware._safe_loopback_read(local) is True
    assert middleware._safe_loopback_read(forwarded) is False
    assert middleware._safe_loopback_read(proxied) is False
    assert middleware._client_key(proxied) == PROXY_RATE_KEY
    # A private-network listener sees the real peer and limits each one.
    assert middleware._client_key(private_peer) == "10.0.0.9"


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_ipv4_and_ipv6_loopback_are_local_only_on_the_local_listener(peer: str) -> None:
    listener = RemoteListener(kind="proxy", port=PROXY_PORT)
    local = {"type": "http", "client": (peer, 5000), "server": (peer, 8765), "headers": []}
    assert is_local_request(local) is True
    assert listener.accepted(local) is False
    assert listener.accepted({**local, "server": (peer, PROXY_PORT)}) is True


def test_a_unix_socket_connection_is_never_local() -> None:
    for server in (None, ("/run/raiker/proxy.sock", None)):
        scope: dict[str, Any] = {"type": "http", "client": None, "server": server, "headers": []}
        assert is_local_request(scope) is False
    assert RemoteListener(kind="proxy", socket_path="/run/raiker/proxy.sock").accepted({"server": ("/run/raiker/proxy.sock", None)})


def _guard(listener: RemoteListener) -> tuple[ProxyGuardMiddleware, list[dict[str, Any]], RemoteAccessRecord]:
    seen: list[dict[str, Any]] = []

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        seen.append(scope)
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})

    record = RemoteAccessRecord(loopback_only=True, listener=listener)
    return ProxyGuardMiddleware(app, loopback_only=True, record=record, listener=listener), seen, record  # type: ignore[arg-type]


def _run(guard: ProxyGuardMiddleware, scope: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(guard(scope, receive, send))  # type: ignore[arg-type]
    return sent


def test_websockets_follow_the_listener_too() -> None:
    listener = RemoteListener(kind="proxy", port=PROXY_PORT)
    guard, seen, record = _guard(listener)
    base = {"type": "websocket", "path": "/ws", "client": ("127.0.0.1", 1), "headers": [(b"x-forwarded-proto", b"https")]}
    assert _run(guard, {**base, "server": ("127.0.0.1", PROXY_PORT)}) == [{"type": "websocket.accept"}]
    assert seen[-1][REMOTE_SCOPE_KEY] is True and is_local_request(seen[-1]) is False
    count = len(seen)
    # Without HTTPS at the proxy: closed before the app sees it.
    plain = {**base, "headers": [], "server": ("127.0.0.1", PROXY_PORT)}
    assert _run(guard, plain) == [{"type": "websocket.close", "code": 1008}]
    # Forwarded on the local listener: closed too.
    local = {**base, "server": ("127.0.0.1", 8765), "headers": [(b"x-forwarded-for", b"203.0.113.9")]}
    assert _run(guard, local) == [{"type": "websocket.close", "code": 1008}]
    assert len(seen) == count
    # Turned off: closed at once.
    record.disable_now()
    assert _run(guard, {**base, "server": ("127.0.0.1", PROXY_PORT)}) == [{"type": "websocket.close", "code": 1008}]


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
    assert remote["https_seen"] is True and remote["mfa_ready"] is False
    plain = TestClient(create_app(tmp_path / "plain"))
    token = plain.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    view = plain.get("/api/diagnostics", headers={"Authorization": f"Bearer {token}"}).json()["remote_access"]
    assert view["mode"] == "loopback" and view["proxy_listener"] is None


# --- start options ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "env"),
    [
        (["--host", "10.0.0.5"], {}),  # the local listener stays on this computer
        (["--allow-public"], {}),  # retired
        (["--proxy-port", "8766", "--proxy-socket", "/tmp/r.sock"], {}),
        (["--private-port", "8443"], {}),  # without --private-host
        ([], {"RAIKER_TRUSTED_PROXY": "127.0.0.1"}),
    ],
)
def test_start_options_that_cannot_be_trusted_refuse_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], env: dict[str, str]
) -> None:
    monkeypatch.delenv("RAIKER_TRUSTED_PROXY", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("raiker.app.host_start.start_host", lambda *_a, **_k: pytest.fail("must not start"))
    assert serve.main(["--workspace", str(tmp_path), "--no-browser", *argv]) == 2


def test_the_server_never_lets_uvicorn_rewrite_the_peer() -> None:
    """uvicorn trusts X-Forwarded-For from 127.0.0.1 by default and rewrites the
    socket peer from it, which would make a header decide who the client is."""
    config = server_runner._config(None, host="127.0.0.1", port=0)
    assert config.proxy_headers is False
    assert config.forwarded_allow_ips == ""


# --- real servers ----------------------------------------------------------------


def _free_socket(host: str = "127.0.0.1") -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, 0))
    return sock


@contextmanager
def _serving(app: Any, local: socket.socket, remote: server_runner.RemoteSocket | None) -> Iterator[None]:
    """Run the real runner in a thread; it has no signals to install there."""
    errors: list[BaseException] = []

    def run() -> None:
        try:
            server_runner.serve(app, local, remote)
        except BaseException as error:  # noqa: BLE001 - surfaced below
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    host, port = local.getsockname()[:2]
    # Poll the address the local listener is actually bound to (it may be ::1).
    base = f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"
    deadline = time.monotonic() + 20
    while True:
        try:
            if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError(f"server did not start: {errors}")
        time.sleep(0.05)
    try:
        yield
    finally:
        app.state.request_stop()
        thread.join(timeout=20)
        local.close()
        if remote is not None:
            remote.sock.close()
    assert not errors, errors


def test_a_real_server_tells_its_listeners_apart(tmp_path: Path) -> None:
    local, proxy = _free_socket(), _free_socket()
    proxy_port = proxy.getsockname()[1]
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=proxy_port))
    with _serving(app, local, server_runner.RemoteSocket(sock=proxy)), httpx.Client(timeout=10) as http:
        local_url, proxy_url = f"http://127.0.0.1:{local.getsockname()[1]}", f"http://127.0.0.1:{proxy_port}"
        assert "recovery_loopback_only" not in http.get(local_url + "/api/recovery/backups").text
        stripped = http.get(proxy_url + "/api/recovery/backups", headers=HTTPS)
        assert stripped.status_code == 403 and "recovery_loopback_only" in stripped.text
        assert _reason(http.get(proxy_url + "/api/recovery/backups")) == HTTPS_REASON
        wrong = http.get(local_url + "/api/health", headers={"X-Forwarded-For": "203.0.113.9"})
        assert wrong.status_code == 403 and _reason(wrong) == REFUSAL_REASON
        spoofed = http.get(proxy_url + "/api/recovery/backups", headers={**HTTPS, "X-Forwarded-For": "127.0.0.1"})
        assert spoofed.status_code == 403 and "recovery_loopback_only" in spoofed.text


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX") or sys.platform == "win32", reason="Unix domain sockets")
def test_a_real_unix_socket_listener_is_remote(tmp_path: Path) -> None:
    import shutil
    import tempfile

    from raiker.app import remote_access as ra

    # A short directory: macOS refuses socket paths over 104 bytes.
    short = Path(tempfile.mkdtemp(dir="/tmp", prefix="rk"))
    path = short / "proxy.sock"
    config = ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=str(path))
    app = create_app(tmp_path / "ws", proxy_listener=config.listener())
    with _serving(app, _free_socket(), ra.open_listener(config)), httpx.Client(
        transport=httpx.HTTPTransport(uds=str(path)), timeout=10
    ) as http:
        assert http.get("http://raiker/api/health").status_code == 200
        refused = http.get("http://raiker/api/recovery/backups", headers=HTTPS)
        assert refused.status_code == 403 and "recovery_loopback_only" in refused.text
    shutil.rmtree(short, ignore_errors=True)


def test_a_real_tls_listener_serves_https_and_is_remote(tmp_path: Path) -> None:
    from tests.test_remote_access import _self_signed

    cert, key = _self_signed(tmp_path, host="127.0.0.1")
    local, remote = _free_socket(), _free_socket()
    port = remote.getsockname()[1]
    # The private-address rule is validation's; the runner and guard are what is under test.
    app = create_app(tmp_path / "ws", proxy_listener=RemoteListener(kind="private", host="127.0.0.1", port=port))
    with _serving(app, local, server_runner.RemoteSocket(sock=remote, tls_cert=str(cert), tls_key=str(key))):
        with httpx.Client(verify=False, timeout=10) as http:  # noqa: S501 - a self-signed test certificate
            secure = http.get(f"https://127.0.0.1:{port}/api/auth/session-state")
            assert secure.status_code == 200
            assert secure.headers.get("strict-transport-security", "").startswith("max-age=")
            assert "recovery_loopback_only" in http.get(f"https://127.0.0.1:{port}/api/recovery/backups").text
        with pytest.raises(httpx.HTTPError), httpx.Client(timeout=5) as plain:
            plain.get(f"http://127.0.0.1:{port}/api/health")
        # The local listener is still plain HTTP, and still local.
        assert httpx.get(f"http://127.0.0.1:{local.getsockname()[1]}/api/health").status_code == 200


def test_a_real_ipv6_loopback_listener_is_local(tmp_path: Path) -> None:
    try:
        local = _free_socket("::1")
    except OSError:
        pytest.skip("no IPv6 loopback on this host")
    proxy = _free_socket()
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=proxy.getsockname()[1]))
    with _serving(app, local, server_runner.RemoteSocket(sock=proxy)), httpx.Client(timeout=10) as http:
        direct = http.get(f"http://[::1]:{local.getsockname()[1]}/api/recovery/backups")
        assert "recovery_loopback_only" not in direct.text


# --- the restart fix ---------------------------------------------------------------


def test_restart_stops_the_server_gracefully_with_its_exit_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restart sets exit status 75 and asks the server itself to stop: no signal."""
    from raiker.app.service import ServiceRegistration

    monkeypatch.setattr(
        "raiker.api.routes_host.registration",
        lambda *_a, **_k: ServiceRegistration(supported=True, registered=True, mechanism="systemd", label="raiker", path="/x", note=""),
    )
    local = _free_socket()
    app = create_app(tmp_path)
    url = f"http://127.0.0.1:{local.getsockname()[1]}"
    with _serving(app, local, None), httpx.Client(timeout=10) as http:
        token = http.post(url + "/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        app.state.request_stop_called = False
        original = app.state.request_stop

        def tracking() -> None:
            app.state.request_stop_called = True
            original()

        app.state.request_stop = tracking
        answer = http.post(url + "/api/host/restart", json={"confirm": True}, headers=h)
        assert answer.status_code == 200, answer.text
        deadline = time.monotonic() + 10
        while not app.state.request_stop_called and time.monotonic() < deadline:
            time.sleep(0.05)
    assert app.state.exit_code == 75
    assert app.state.request_stop_called is True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_a_sigterm_lets_the_host_return_instead_of_dying(tmp_path: Path) -> None:
    """uvicorn re-raised the signal after shutting down, so the process died by
    SIGTERM (status 143) and never returned Restart's exit status."""
    import subprocess

    script = (
        "import os, signal, sys, threading, time\n"
        "from raiker.api import server_runner\n"
        "from raiker.api.app import create_app\n"
        f"app = create_app({str(tmp_path)!r})\n"
        "app.state.exit_code = 75\n"
        "sock = server_runner.bind_local('127.0.0.1', 0)\n"
        "threading.Timer(3, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()\n"
        "server_runner.serve(app, sock)\n"
        "sys.exit(app.state.exit_code)\n"
    )
    finished = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=120, check=False)  # noqa: S603
    assert finished.returncode == 75, finished.stderr.decode()[-2000:]


def test_the_runner_stops_both_listeners_together(tmp_path: Path) -> None:
    local, proxy = _free_socket(), _free_socket()
    proxy_port = proxy.getsockname()[1]
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=proxy_port))
    with _serving(app, local, server_runner.RemoteSocket(sock=proxy)):
        assert httpx.get(f"http://127.0.0.1:{proxy_port}/api/health").status_code == 200
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"http://127.0.0.1:{proxy_port}/api/health", timeout=2)

