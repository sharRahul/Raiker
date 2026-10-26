"""BUG-358 — remote access is protected by the owner's password and MFA.

Owner's decision (2026-10-26): ``RAIKER_OWNER_TOKEN`` is removed; every remote
session needs the password *and* a verified code; MFA must stay on while
remote access is on; sessions that predate the rule, or the enrolment, do not
count; sensitive changes need fresh MFA; local desktop use is unchanged.

A remote request here is one on the proxy listener (``testserver:8766``) with
``X-Forwarded-Proto: https``, which is what the guard needs before anything
else answers. Everything is enforced by the server: the tests call the API
directly, as a client that skipped the UI would.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.proxy_guard import RemoteListener
from raiker.app import remote_access as ra
from raiker.storage.sqlite import SQLiteStore

USER, PASSWORD = "owner", "a-long-password-1"
PROXY_PORT = 8766
HTTPS = {"X-Forwarded-Proto": "https", "User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36"}


class Host:
    """One app reached from this computer and from another device."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.app = create_app(workspace, proxy_listener=RemoteListener(kind="proxy", port=PROXY_PORT))
        self.local = TestClient(self.app)
        self.remote = self.device()

    def device(self) -> TestClient:
        return TestClient(self.app, base_url=f"https://testserver:{PROXY_PORT}", headers=HTTPS)

    def register(self) -> dict[str, str]:
        answer = self.local.post("/api/auth/register", json={"username": USER, "password": PASSWORD})
        assert answer.status_code == 200, answer.text
        return {"Authorization": f"Bearer {answer.json()['token']}"}

    def enrol(self, headers: dict[str, str]) -> pyotp.TOTP:
        enrolled = self.local.post("/api/auth/mfa/enroll", headers=headers).json()
        totp = pyotp.TOTP(enrolled["secret"])
        activated = self.local.post("/api/auth/mfa/activate", json={"code": totp.now()}, headers=headers)
        assert activated.status_code == 200, activated.text
        self.backup_codes = list(enrolled["backup_codes"])
        return totp

    def remote_sign_in(self, totp: pyotp.TOTP, client: TestClient | None = None) -> TestClient:
        device = client or self.remote
        first = device.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
        assert first.status_code == 200, first.text
        assert first.json()["stage"] == "mfa_required"
        second = device.post("/api/auth/mfa/verify", json={"ticket": first.json()["ticket"], "code": totp.now()})
        assert second.status_code == 200, second.text
        device.headers["X-Raiker-CSRF"] = second.json()["csrf_token"]
        return device

    def store(self) -> SQLiteStore:
        return SQLiteStore(self.workspace)


@pytest.fixture()
def host(tmp_path: Path) -> Host:
    return Host(tmp_path)


def _reason(response: Any) -> str:
    detail = response.json().get("detail")
    return str(detail.get("reason_code")) if isinstance(detail, dict) else str(detail)


# 1. Local access works with remote access off, and needs no MFA.
def test_local_access_works_without_mfa(host: Host) -> None:
    headers = host.register()
    assert host.local.get("/api/auth/whoami", headers=headers).status_code == 200
    signed = host.local.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()
    assert signed["stage"] == "session" and signed["token"]


# 2/3. Without MFA, another device cannot sign in at all.
def test_without_mfa_remote_sign_in_is_suspended(host: Host) -> None:
    host.register()
    refused = host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert refused.status_code == 403
    assert _reason(refused) == "remote_access_suspended"
    assert "raiker_session" not in refused.cookies


# 3. A password alone never yields a remote session.
def test_password_alone_yields_only_a_ticket_remotely(host: Host) -> None:
    host.enrol(host.register())
    first = host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    body = first.json()
    assert body["stage"] == "mfa_required" and body["token"] is None
    assert "raiker_session" not in first.cookies
    # The ticket opens nothing.
    ticket = {"Authorization": f"Bearer {body['ticket']}"}
    assert host.remote.get("/api/auth/whoami", headers=ticket).status_code in (401, 403)


# 4. Password and a valid code sign in, as a cookie-only session.
def test_password_and_code_sign_in_with_a_protected_cookie(host: Host) -> None:
    totp = host.enrol(host.register())
    first = host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()
    second = host.remote.post("/api/auth/mfa/verify", json={"ticket": first["ticket"], "code": totp.now()})
    assert second.status_code == 200
    assert second.json()["token"] is None  # no bearer token handed to another device
    cookie = next(value for name, value in second.headers.multi_items() if name == "set-cookie" and value.startswith("raiker_session="))
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    assert second.headers.get("strict-transport-security", "").startswith("max-age=")
    who = host.remote.get("/api/auth/whoami")
    assert who.status_code == 200
    sessions = host.remote.get("/api/auth/sessions").json()
    mine = next(row for row in sessions if row["current"])
    assert mine["origin"] == "remote" and mine["mfa_verified"] is True
    assert mine["client_hint"] == "Chrome on Windows"
    # A write needs the CSRF echo, as on this computer.
    host.remote.headers.pop("X-Raiker-CSRF", None)
    assert host.remote.post("/api/auth/logout").status_code == 403


# 5. A wrong or missing code is refused, logged, and locks out at the threshold.
def test_wrong_codes_are_refused_logged_and_lock_out(host: Host) -> None:
    host.enrol(host.register())
    for _ in range(5):
        ticket = host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()["ticket"]
        assert host.remote.post("/api/auth/mfa/verify", json={"ticket": ticket, "code": "000000"}).status_code == 401
    assert ra.count_events(host.store(), "remote_mfa_failed", "2000-01-01T00:00:00Z") == 5
    # Locked: even the right password is refused now.
    assert host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).status_code == 401


# 6. Sessions made on this computer never work from another device.
def test_local_sessions_do_not_work_remotely(host: Host) -> None:
    password_only = host.register()
    totp = host.enrol(password_only)
    # A session minted locally with MFA is still a local session.
    first = host.local.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()
    local_mfa = host.local.post("/api/auth/mfa/verify", json={"ticket": first["ticket"], "code": totp.now()}).json()
    for token in (password_only["Authorization"], f"Bearer {local_mfa['token']}"):
        refused = host.remote.get("/api/auth/whoami", headers={"Authorization": token})
        assert refused.status_code == 401 and _reason(refused) == "remote_mfa_required"


# 7. Turning MFA off suspends remote access at once, and says so.
def test_turning_mfa_off_suspends_remote_access(host: Host) -> None:
    headers = host.register()
    totp = host.enrol(headers)
    device = host.remote_sign_in(totp)
    elevated = host.local.post("/api/auth/elevate", json={"password": PASSWORD, "mfa_code": totp.now()}, headers=headers)
    off = host.local.post("/api/auth/mfa/disable", headers={"Authorization": f"Bearer {elevated.json()['token']}"})
    assert off.status_code == 200
    # The device is signed out (its session is revoked with every other one).
    assert device.get("/api/auth/whoami").status_code == 401
    assert host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).status_code == 403
    # Local use carries on.
    assert host.local.get("/api/auth/whoami", headers=headers).status_code == 200


# 7. A reset keeps the old authenticator until the new one is confirmed, then
#    retires every session verified against the old one.
def test_an_mfa_reset_is_staged_and_retires_old_verifications(host: Host) -> None:
    headers = host.register()
    totp = host.enrol(headers)
    other = host.remote_sign_in(totp, host.device())
    # Starting a reset needs fresh MFA, not just a session.
    assert host.local.post("/api/auth/mfa/enroll", headers=headers).status_code == 403
    elevated = {"Authorization": "Bearer " + host.local.post(
        "/api/auth/elevate", json={"password": PASSWORD, "mfa_code": totp.now()}, headers=headers
    ).json()["token"]}
    staged = host.local.post("/api/auth/mfa/enroll", headers=elevated).json()
    # While staged, the old authenticator still signs in and remote access stays up.
    assert other.get("/api/auth/whoami").status_code == 200
    assert host.remote_sign_in(totp, host.device()).get("/api/auth/whoami").status_code == 200
    fresh = pyotp.TOTP(staged["secret"])
    assert host.local.post("/api/auth/mfa/activate", json={"code": fresh.now()}, headers=headers).status_code == 200
    assert other.get("/api/auth/whoami").status_code == 401
    assert host.remote_sign_in(fresh, host.device()).get("/api/auth/whoami").status_code == 200


# 16. Signing out every other device works across devices.
def test_signing_out_other_devices(host: Host) -> None:
    totp = host.enrol(host.register())
    first = host.remote_sign_in(totp, host.device())
    second = host.remote_sign_in(totp, host.device())
    answer = second.post("/api/auth/sessions/revoke-others")
    assert answer.status_code == 200 and answer.json()["revoked"] >= 1
    assert first.get("/api/auth/whoami").status_code == 401
    assert second.get("/api/auth/whoami").status_code == 200


def test_one_session_is_revoked_by_id(host: Host) -> None:
    headers = host.register()
    totp = host.enrol(headers)
    device = host.remote_sign_in(totp, host.device())
    sessions = host.local.get("/api/auth/sessions", headers=headers).json()
    remote_row = next(row for row in sessions if row["origin"] == "remote")
    assert host.local.post(f"/api/auth/sessions/{remote_row['session_id']}/revoke", headers=headers).status_code == 200
    assert device.get("/api/auth/whoami").status_code == 401


# 6. Sensitive actions need fresh MFA; remote elevation needs both factors.
def test_sensitive_actions_need_fresh_mfa(host: Host) -> None:
    headers = host.register()
    totp = host.enrol(headers)
    by_password = host.local.post("/api/auth/elevate", json={"password": PASSWORD}, headers=headers).json()["token"]
    refused = host.local.post("/api/auth/mfa/disable", headers={"Authorization": f"Bearer {by_password}"})
    assert refused.status_code == 403 and _reason(refused) == "fresh_mfa_required"
    device = host.remote_sign_in(totp)
    assert device.post("/api/auth/elevate", json={"password": PASSWORD}).status_code == 401
    assert device.post("/api/auth/elevate", json={"mfa_code": totp.now()}).status_code == 401
    both = device.post("/api/auth/elevate", json={"password": PASSWORD, "mfa_code": totp.now()})
    assert both.status_code == 200


# 10. This computer's operations stay on this computer.
def test_local_only_operations_refuse_another_device(host: Host) -> None:
    totp = host.enrol(host.register())
    device = host.remote_sign_in(totp)
    for method, path, body in (
        ("POST", "/api/host/restart", {"confirm": True}),
        ("POST", "/api/host/quit", {"confirm": True}),
        ("POST", "/api/instances", {"name": "second"}),
        ("GET", "/api/recovery/backups", None),
        ("POST", "/api/tray/session", {"secret": "x"}),
        ("POST", "/api/auth/register", {"username": "x", "password": "y-long-password"}),
        ("POST", "/api/auth/password-recovery/begin", {"username": USER}),
    ):
        answer = device.request(method, path, json=body)
        assert answer.status_code == 403, (path, answer.status_code, answer.text)
    elevated = device.post("/api/auth/elevate", json={"password": PASSWORD, "mfa_code": totp.now()}).json()["token"]
    apply = device.post(
        "/api/remote-access/apply",
        json={"config": {"mode": "proxy", "proxy_kind": "port", "proxy_port": 8799}, "confirm": True},
        headers={"Authorization": f"Bearer {elevated}"},
    )
    assert apply.status_code == 403


# Disabling from another device takes effect at once.
def test_disable_from_another_device_takes_effect_at_once(host: Host) -> None:
    totp = host.enrol(host.register())
    device = host.remote_sign_in(totp)
    answer = device.post("/api/remote-access/disable")
    assert answer.status_code == 200
    assert answer.json()["active"]["refusing"] is True
    refused = host.device().get("/api/health")
    assert refused.status_code == 403 and _reason(refused) == "remote_access_disabled"
    assert ra.load_state(host.store()).desired.mode == "local"


# 17. HTTPS is required at the entry point.
def test_remote_requests_without_https_are_refused(host: Host) -> None:
    plain = TestClient(host.app, base_url=f"http://testserver:{PROXY_PORT}")
    refused = plain.get("/api/auth/session-state")
    assert refused.status_code == 403 and _reason(refused) == "remote_https_required"
    assert plain.get("/api/health").status_code == 200  # a proxy's health check


def test_remote_sessions_expire_sooner_than_local_ones(host: Host) -> None:
    headers = host.register()
    totp = host.enrol(headers)
    host.remote_sign_in(totp)
    rows = host.local.get("/api/auth/sessions", headers=headers).json()
    remote_row = next(row for row in rows if row["origin"] == "remote")
    local_row = next(row for row in rows if row["origin"] == "local" and row["current"])
    assert remote_row["absolute_expires_at"] < local_row["absolute_expires_at"]


def test_the_owner_token_is_no_longer_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from raiker.api import serve

    monkeypatch.setenv("RAIKER_OWNER_TOKEN", "x" * 40)
    monkeypatch.delenv("RAIKER_TRUSTED_PROXY", raising=False)
    started: dict[str, Any] = {}
    monkeypatch.setattr("raiker.app.host_start.start_host", lambda *a, **k: started.update(k) or 0)
    assert serve.main(["--workspace", str(tmp_path), "--no-browser", "--port", "8797"]) == 0
    assert "no longer used" in capsys.readouterr().out
    assert started["override"] is None


def test_sign_in_answers_are_never_cached(host: Host) -> None:
    host.enrol(host.register())
    answer = host.remote.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    assert answer.headers.get("cache-control") == "no-store"
    assert host.local.get("/api/health").headers.get("cache-control") != "no-store"

