from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import raiker.app.tray as tray_module
from raiker.api.app import create_app
from raiker.app.tray import _exchange
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


def test_tray_waits_for_first_run_owner_instead_of_giving_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def post(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal attempts
        attempts += 1
        if attempts <= 20:
            return SimpleNamespace(is_success=False, status_code=409)
        return SimpleNamespace(is_success=True, json=lambda: {"token": "host-token"})

    monkeypatch.setattr(tray_module.httpx, "post", post)
    monkeypatch.setattr(tray_module.threading.Event, "wait", lambda self, timeout: True)

    assert _exchange("http://127.0.0.1:8765", "secret") == "host-token"
    assert attempts == 21
