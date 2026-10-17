"""DIST-05/06 — the first-run device and installation checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.app import system_check
from raiker.app.system_check import GIB, recommended_local_model, system_readiness
from raiker.cli.principal_resolver import bootstrap_owner


def test_a_dedicated_gpu_is_never_a_requirement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_check, "detect_acceleration", lambda machine=None: ("none", "No dedicated GPU driver found"))
    answer = system_readiness(tmp_path)
    gpu = next(check for check in answer["checks"] if check["id"] == "gpu")
    assert gpu["state"] == "info"
    assert gpu["mandatory"] is False
    assert "gpu" not in answer["blocking"]


def test_too_little_memory_blocks_and_says_why(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_check, "total_memory_bytes", lambda: 2 * GIB)
    answer = system_readiness(tmp_path)
    memory = next(check for check in answer["checks"] if check["id"] == "memory")
    assert memory["state"] == "fail" and "4 GB" in memory["remedy"]
    assert "memory" in answer["blocking"] and answer["ready"] is False


def test_the_local_model_advice_scales_with_memory() -> None:
    assert recommended_local_model(4 * GIB, "none")["parameters"] == "1B–3B"
    assert recommended_local_model(8 * GIB, "none")["parameters"] == "3B–8B"
    assert recommended_local_model(16 * GIB, "none")["parameters"] == "7B–14B"
    assert recommended_local_model(64 * GIB, "none")["parameters"] == "7B–14B"
    assert recommended_local_model(64 * GIB, "cuda")["parameters"] == "14B–32B"


def test_the_network_check_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[object] = []

    class Socket:
        def __init__(self, *_args: object) -> None: ...
        def __enter__(self) -> Socket: return self
        def __exit__(self, *_args: object) -> None: ...
        def connect(self, address: object) -> None: sent.append(("connect", address))
        def getsockname(self) -> tuple[str, int]: return ("192.168.1.5", 4000)
        def send(self, *_args: object) -> None: sent.append("send")
        def sendto(self, *_args: object) -> None: sent.append("sendto")

    monkeypatch.setattr(system_check.socket, "socket", Socket)
    assert system_check.has_network_route() is True
    assert sent == [("connect", ("192.0.2.1", 9))]


def test_every_check_has_the_wire_shape(tmp_path: Path) -> None:
    answer = system_readiness(tmp_path)
    assert {"checks", "blocking", "ready", "recommended_local_model", "locations"} <= set(answer)
    for check in answer["checks"]:
        assert check["state"] in {"pass", "warn", "fail", "info"}
        assert set(check) == {"id", "label", "state", "detail", "remedy", "mandatory", "data"}


def test_the_installation_check_runs_inside_a_real_host(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/setup/verify", headers=headers)
    assert response.status_code == 200
    body = response.json()
    by_id = {check["id"]: check for check in body["checks"]}
    for mandatory in ("host", "database", "memory", "permissions"):
        assert by_id[mandatory]["state"] == "pass", by_id[mandatory]
    assert "nothing was granted by setup" in by_id["permissions"]["detail"]
    # No model chosen yet is a limit, not a failure of the installation.
    assert by_id["model"]["state"] == "warn"
    system = client.get("/api/setup/system", headers=headers)
    assert system.status_code == 200 and system.json()["checks"]


def test_the_installation_time_check_writes_its_answer_and_creates_nothing(tmp_path: Path) -> None:
    from raiker.app.launcher import main

    workspace = tmp_path / "not" / "yet" / "created"
    output = tmp_path / "check.json"
    code = main(["system-check", "--workspace", str(workspace), "--output", str(output)])
    answer = json.loads(output.read_text(encoding="utf-8"))
    assert code == (0 if answer["ready"] else 1)
    assert {check["id"] for check in answer["checks"]} >= {"os", "arch", "memory", "storage"}
    storage = next(check for check in answer["checks"] if check["id"] == "storage")
    assert storage["state"] != "info"  # measured on the nearest existing folder
    assert not workspace.exists()
