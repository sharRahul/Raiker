"""Remote access (BUG-347, BUG-358)."""

from __future__ import annotations

import socket
from pathlib import Path

from fastapi.testclient import TestClient

from tests.contract_cases.auth import _elevated, _with_mfa
from tests.contract_cases.base import Call, Cases, fresh, plain


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _proxy_config() -> dict[str, object]:
    return {"mode": "proxy", "proxy_kind": "port", "proxy_port": _free_port()}


def _apply(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers, totp, _backup = _with_mfa(client)
    return "/api/remote-access/apply", {"config": _proxy_config(), "confirm": True}, _elevated(client, headers, totp)


def _rollback(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers, totp, _backup = _with_mfa(client)
    elevated = _elevated(client, headers, totp)
    applied = client.post(
        "/api/remote-access/apply", json={"config": _proxy_config(), "confirm": True}, headers=elevated
    )
    assert applied.status_code == 200, applied.text
    return "/api/remote-access/rollback", None, elevated


def _revoke_others(_ws: Path, client: TestClient, _h: dict[str, str]) -> Call:
    headers, _totp, _backup = _with_mfa(client)
    return "/api/auth/sessions/revoke-others", None, headers


CASES: Cases = {
    ("GET", "/api/remote-access"): plain("/api/remote-access"),
    ("POST", "/api/remote-access/check"): lambda _ws, _client, _h: ("/api/remote-access/check", _proxy_config()),
    ("POST", "/api/remote-access/apply"): fresh(_apply),
    ("POST", "/api/remote-access/rollback"): fresh(_rollback),
    ("POST", "/api/remote-access/disable"): plain("/api/remote-access/disable"),
    ("POST", "/api/auth/sessions/revoke-others"): fresh(_revoke_others),
}
