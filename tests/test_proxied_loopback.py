"""BUG-347 — a reverse proxy in front of a loopback-bound Raiker.

Owner's decision (2026-10-26): refuse by default, trust a named proxy on
request. A forwarded request is never local; on a loopback-only host it is
refused unless its socket peer is a proxy named in ``RAIKER_TRUSTED_PROXY``,
and then it is served as remote: recovery refused, rate limited, HSTS over
HTTPS. Diagnostics says how the host is reached and what it refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api import serve
from raiker.api.app import create_app
from raiker.api.proxy_guard import (
    REFUSAL_REASON,
    ProxyConfigError,
    is_local_request,
    trusted_proxies,
)
from raiker.api.security import RateLimitMiddleware

FORWARDED = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trusted: str = "") -> TestClient:
    monkeypatch.setenv("RAIKER_TRUSTED_PROXY", trusted)
    # The test client's peer is "testclient", which the guard reads as this machine.
    return TestClient(create_app(tmp_path))


@pytest.mark.parametrize(
    "header",
    ["Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Real-IP"],
)
def test_any_forwarding_header_is_refused_on_a_loopback_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, header: str
) -> None:
    client = _client(tmp_path, monkeypatch)
    refused = client.get("/api/health", headers={header: "203.0.113.9"})
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["reason_code"] == REFUSAL_REASON
    assert "RAIKER_TRUSTED_PROXY" in detail["message"] and "--allow-public" in detail["message"]
    # The refusal still carries the security headers.
    assert refused.headers.get("x-frame-options") == "DENY"
    page = client.get("/", headers={header: "203.0.113.9"})
    assert page.status_code == 403
    assert "reverse proxy" in page.text


def test_a_direct_local_request_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/health").status_code == 200


def test_recovery_refuses_a_request_a_trusted_proxy_forwarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch, trusted="127.0.0.1")
    served = client.get("/api/health", headers=FORWARDED)
    assert served.status_code == 200
    assert served.headers.get("strict-transport-security", "").startswith("max-age=")
    local = client.get("/api/recovery/backups")
    proxied = client.get("/api/recovery/backups", headers=FORWARDED)
    assert proxied.status_code == 403
    assert "recovery_loopback_only" in proxied.text
    assert "recovery_loopback_only" not in local.text


def test_a_forwarded_request_never_gets_the_loopback_rate_exemption() -> None:
    middleware = RateLimitMiddleware(app=lambda *_: None, loopback_only=True)  # type: ignore[arg-type]
    local = {"type": "http", "method": "GET", "client": ("127.0.0.1", 1), "headers": []}
    proxied = {**local, "headers": [(b"x-forwarded-for", b"203.0.113.9")]}
    assert middleware._safe_loopback_read(local) is True
    assert middleware._safe_loopback_read(proxied) is False
    assert is_local_request(proxied) is False


def test_diagnostics_names_how_the_host_is_reached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    token = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    client.get("/api/health", headers={"X-Forwarded-For": "203.0.113.9"})
    remote = client.get("/api/diagnostics", headers=h).json()["remote_access"]
    assert remote["mode"] == "loopback"
    assert remote["proxied_requests_refused"] == 1
    assert remote["last_refused_at"]


def test_trusted_proxy_entries_are_addresses() -> None:
    assert [str(n) for n in trusted_proxies("127.0.0.1, 10.0.0.0/8")] == ["127.0.0.1/32", "10.0.0.0/8"]
    with pytest.raises(ProxyConfigError):
        trusted_proxies("my-proxy.local")


def test_trusting_a_proxy_needs_the_owner_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_TRUSTED_PROXY", "127.0.0.1")
    monkeypatch.delenv("RAIKER_OWNER_TOKEN", raising=False)
    assert serve.main(["--workspace", str(tmp_path), "--no-browser"]) == 2
    monkeypatch.setenv("RAIKER_TRUSTED_PROXY", "not-an-address")
    assert serve.main(["--workspace", str(tmp_path), "--no-browser"]) == 2


def test_an_unreadable_trusted_proxy_setting_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_TRUSTED_PROXY", "proxy.example")
    with pytest.raises(ProxyConfigError):
        create_app(tmp_path)


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
