"""Per-run egress proxy: allow-listed CONNECT only, checked before any lookup."""

from __future__ import annotations

import base64
import socket
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from raiker.execution.commands import egress_proxy
from raiker.execution.commands.egress_runtime import (
    CommandEgressSettings,
    EgressRun,
    EgressSink,
    load_settings,
    save_settings,
)
from raiker.execution.commands.runner import MemoryCommandSink

pytestmark = pytest.mark.skipif(
    sys.platform.startswith("linux"), reason="Linux serves the proxy on a Unix socket"
)


def _connect(url: str, target: str, *, credential: bool = True) -> bytes:
    parts = urlsplit(url)
    client = socket.create_connection((parts.hostname or "", parts.port or 0), timeout=5)
    lines = [f"CONNECT {target} HTTP/1.1", f"Host: {target}"]
    if credential:
        raw = f"{parts.username}:{parts.password}".encode()
        lines.append("Proxy-Authorization: Basic " + base64.b64encode(raw).decode())
    client.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    reply = client.recv(4096)
    if reply.startswith(b"HTTP/1.1 200"):
        client.sendall(b"ping")
        reply += client.recv(4)
    client.close()
    return reply


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """A local stand-in for the destination, and a record of every lookup."""
    lookups: list[str] = []
    server = socket.create_server(("127.0.0.1", 0))

    def serve() -> None:
        while True:
            try:
                connection, _ = server.accept()
            except OSError:
                return
            if connection.recv(4) == b"ping":
                connection.sendall(b"pong")
            connection.close()

    threading.Thread(target=serve, daemon=True).start()

    def resolve(host: str, port: int) -> tuple[str, ...]:
        lookups.append(host)
        return ("93.184.216.34",)

    def connect(_addresses: tuple[str, ...], _port: int) -> socket.socket:
        return socket.create_connection(server.getsockname(), timeout=5)

    monkeypatch.setattr(egress_proxy, "_resolve_public", resolve)
    monkeypatch.setattr(egress_proxy, "_connect_pinned", connect)
    yield lookups
    server.close()


def _run(domains: tuple[str, ...] = ("pypi.org",)) -> EgressRun:
    return EgressRun("cmd_egress", "owner_1", CommandEgressSettings(True, domains)).start(30)


def test_an_allow_listed_host_tunnels_and_the_boundary_gets_a_loopback_proxy(
    upstream: list[str],
) -> None:
    run = _run()
    try:
        assert run.policy_fields["network"].startswith("proxy:127.0.0.1:")
        url = run.environment["HTTPS_PROXY"]
        assert set(run.environment) >= {"HTTPS_PROXY", "https_proxy", "HTTP_PROXY"}
        assert _connect(url, "pypi.org:443").endswith(b"pong")
        assert upstream == ["pypi.org"]
    finally:
        assert run.close() == []


def test_an_unlisted_host_is_refused_without_ever_being_resolved(upstream: list[str]) -> None:
    run = _run()
    url = run.environment["HTTPS_PROXY"]
    assert _connect(url, "exfil-data.attacker.example:443").startswith(b"HTTP/1.1 403")
    assert _connect(url, "pypi.org:80").startswith(b"HTTP/1.1 403")
    # A name check that came after the lookup would have leaked the name to DNS.
    assert upstream == []
    assert run.close() == ["exfil-data.attacker.example:443", "pypi.org:80"]


def test_without_the_run_credential_nothing_tunnels(upstream: list[str]) -> None:
    run = _run()
    try:
        reply = _connect(run.environment["HTTPS_PROXY"], "pypi.org:443", credential=False)
        assert reply.startswith(b"HTTP/1.1 403")
        assert upstream == []
    finally:
        run.close()


def test_a_closed_run_accepts_no_connection(upstream: list[str]) -> None:
    run = _run()
    url = run.environment["HTTPS_PROXY"]
    run.close()
    parts = urlsplit(url)
    with pytest.raises(OSError):
        _connect(url, "pypi.org:443")
    assert parts.port


def test_the_sink_reports_refused_hosts_when_the_run_completes(upstream: list[str]) -> None:
    run = _run()
    _connect(run.environment["HTTPS_PROXY"], "evil.example:443")
    inner = MemoryCommandSink()
    completed: list[Any] = []
    inner.complete = lambda state, returncode: completed.append((state, returncode))  # type: ignore[method-assign,assignment]
    EgressSink(inner, run).complete("succeeded", 0)
    assert "evil.example:443" in inner.captured_text
    assert completed == [("succeeded", 0)]


def test_settings_are_off_by_default_and_validated(tmp_path: Path) -> None:
    assert load_settings(tmp_path) == CommandEgressSettings()
    assert load_settings(tmp_path).enabled is False
    saved = save_settings(tmp_path, True, ["PyPI.org", "*.crates.io"])
    assert saved.domains == ("*.crates.io", "pypi.org")
    assert load_settings(tmp_path) == saved
    with pytest.raises(ValueError):
        save_settings(tmp_path, True, [])
    with pytest.raises(ValueError):
        save_settings(tmp_path, True, ["not a domain"])
