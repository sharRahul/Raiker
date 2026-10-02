"""Sign-in, MFA, elevation, device sessions and the account."""

from __future__ import annotations

from pathlib import Path

import pyotp
from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases, Seed, fresh, plain

USER, PASSWORD = "alice", "right-pass-123"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient) -> dict[str, str]:
    """The first account, and its session's headers."""
    response = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return _bearer(response.json()["token"])


def _with_mfa(client: TestClient) -> tuple[dict[str, str], pyotp.TOTP, list[str]]:
    headers = _register(client)
    enrolled = client.post("/api/auth/mfa/enroll", headers=headers).json()
    totp = pyotp.TOTP(enrolled["secret"])
    activated = client.post("/api/auth/mfa/activate", json={"code": totp.now()}, headers=headers)
    assert activated.status_code == 200, activated.text
    return headers, totp, enrolled["backup_codes"]


def _elevated(client: TestClient, headers: dict[str, str], totp: pyotp.TOTP | None = None) -> dict[str, str]:
    body = {"password": PASSWORD, "mfa_code": totp.now() if totp else None}
    response = client.post("/api/auth/elevate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return _bearer(response.json()["token"])


def _account(path: str, body: object = None) -> Seed:
    """Register, then call ``path`` as that account."""

    def seed(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
        return path, body, _register(client)

    return fresh(seed)


def _login(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    _register(client)
    return "/api/auth/login", {"username": USER, "password": PASSWORD}


def _recovery_begin(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    _register(client)
    return "/api/auth/password-recovery/begin", {"username": USER}


def _recovery_complete(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    # A backup code: the TOTP code of this window was spent activating MFA.
    _headers, _totp, backup = _with_mfa(client)
    ticket = client.post("/api/auth/password-recovery/begin", json={"username": USER}).json()["ticket"]
    return (
        "/api/auth/password-recovery/complete",
        {"ticket": ticket, "code": backup[0], "new_password": "another-pass-456"},
    )


def _mfa_verify(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    _headers, totp, _backup = _with_mfa(client)
    ticket = client.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()["ticket"]
    return "/api/auth/mfa/verify", {"ticket": ticket, "code": totp.now()}


def _mfa_activate(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers = _register(client)
    secret = client.post("/api/auth/mfa/enroll", headers=headers).json()["secret"]
    return "/api/auth/mfa/activate", {"code": pyotp.TOTP(secret).now()}, headers


def _mfa_disable(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers, totp, _backup = _with_mfa(client)
    return "/api/auth/mfa/disable", None, _elevated(client, headers, totp)


def _revoke(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers = _register(client)
    client.post("/api/auth/login", json={"username": USER, "password": PASSWORD})
    rows = client.get("/api/auth/sessions", headers=headers).json()
    other = next(row["session_id"] for row in rows if not row["current"])
    return f"/api/auth/sessions/{other}/revoke", None, headers


def _delete_account(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers = _register(client)
    return "/api/account", None, _elevated(client, headers)


CASES: Cases = {
    ("POST", "/api/auth/register"): fresh(
        plain("/api/auth/register", {"username": USER, "password": PASSWORD})
    ),
    ("POST", "/api/auth/login"): fresh(_login),
    ("POST", "/api/auth/session"): plain("/api/auth/session", {"as_principal": None}),
    ("GET", "/api/auth/bootstrap-status"): plain("/api/auth/bootstrap-status"),
    ("POST", "/api/auth/password-recovery/begin"): fresh(_recovery_begin),
    ("POST", "/api/auth/password-recovery/complete"): fresh(_recovery_complete),
    ("POST", "/api/auth/mfa/verify"): fresh(_mfa_verify),
    ("POST", "/api/auth/mfa/enroll"): _account("/api/auth/mfa/enroll"),
    ("POST", "/api/auth/mfa/activate"): fresh(_mfa_activate),
    ("POST", "/api/auth/mfa/disable"): fresh(_mfa_disable),
    ("POST", "/api/auth/elevate"): _account("/api/auth/elevate", {"password": PASSWORD}),
    ("POST", "/api/auth/password"): _account(
        "/api/auth/password", {"old_password": PASSWORD, "new_password": "another-pass-456"}
    ),
    ("POST", "/api/auth/logout"): _account("/api/auth/logout"),
    ("GET", "/api/auth/whoami"): plain("/api/auth/whoami"),
    ("GET", "/api/auth/session-state"): plain("/api/auth/session-state"),
    ("GET", "/api/auth/sessions"): _account("/api/auth/sessions"),
    ("POST", "/api/auth/sessions/{session_id}/revoke"): fresh(_revoke),
    ("DELETE", "/api/account"): fresh(_delete_account),
}
