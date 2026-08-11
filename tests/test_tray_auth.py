from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner


def test_tray_bootstrap_is_one_time_and_host_control_scoped(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    app = create_app(tmp_path, tray_bootstrap_secret="one-time-secret")
    client = TestClient(app)

    exchanged = client.post("/api/tray/session", json={"secret": "one-time-secret"})
    assert exchanged.status_code == 200
    headers = {"Authorization": f"Bearer {exchanged.json()['token']}"}
    assert client.get("/api/host", headers=headers).status_code == 200
    assert client.get("/api/tasks", headers=headers).status_code == 403
    assert client.post("/api/tray/session", json={"secret": "one-time-secret"}).status_code == 401


def test_tray_bootstrap_rejects_wrong_secret(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path, tray_bootstrap_secret="right"))
    assert client.post("/api/tray/session", json={"secret": "wrong"}).status_code == 401

