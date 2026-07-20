"""Workstream F / Slice F3 (ZT-5) — standing grants over the loopback API.

Proves the Security-Settings surface: a human owner can create, list, and revoke
scoped standing grants; the sub-critical ceiling and critical-target invariants
are enforced at the API boundary.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app


@pytest.fixture()
def ctx(tmp_path):  # type: ignore[no-untyped-def]
    client = TestClient(create_app(tmp_path))
    reg = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()
    return client, reg["token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_list_revoke_grant(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token = ctx
    created = client.post(
        "/api/standing-grants",
        json={"action_type": "write_file", "risk_ceiling": "medium", "scope_pattern": "coding"},
        headers=_h(token),
    )
    assert created.status_code == 200, created.text
    grant_id = created.json()["grant"]["grant_id"]

    listed = client.get("/api/standing-grants", headers=_h(token))
    assert listed.status_code == 200
    grants = listed.json()["grants"]
    assert any(g["grant_id"] == grant_id for g in grants)

    revoked = client.post(f"/api/standing-grants/{grant_id}/revoke", headers=_h(token))
    assert revoked.status_code == 200

    after = client.get(
        "/api/standing-grants?include_inactive=false", headers=_h(token)
    ).json()["grants"]
    assert all(g["grant_id"] != grant_id for g in after)


def test_critical_ceiling_rejected(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token = ctx
    resp = client.post(
        "/api/standing-grants",
        json={"action_type": "write_file", "risk_ceiling": "critical"},
        headers=_h(token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "grant_ceiling_cannot_be_critical"


def test_grant_for_critical_target_rejected(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token = ctx
    resp = client.post(
        "/api/standing-grants",
        json={"action_type": "credential_rotate", "risk_ceiling": "high"},
        headers=_h(token),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "grant_target_is_critical"
