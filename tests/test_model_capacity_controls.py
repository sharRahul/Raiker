from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.tasks.scheduler import TaskScheduler


def test_admin_context_capacity_override_and_history(tmp_path: Path) -> None:
    workspace = tmp_path / "capacity"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    saved = client.put(
        "/api/models/raiker-local-llama-cpp/capacity",
        headers=headers,
        json={"model": "local-gguf", "tokens": 32768, "reason": "Verified local server config"},
    )
    assert saved.status_code == 200, saved.text
    models = client.get("/api/models", headers=headers).json()
    profile = next(item for item in models["profiles"] if item["profile_id"] == "raiker-local-llama-cpp")
    assert profile["context_window_tokens"] == 32768
    assert profile["context_window_source"] == "owner"
    capacities = client.get("/api/models/capacities", headers=headers).json()
    entry = next(item for item in capacities["entries"] if item["profile_id"] == "raiker-local-llama-cpp")
    assert entry["endpoint_identity"] == "raiker-local-llama-cpp:local_machine"
    assert entry["history"][0]["reason"] == "Verified local server config"
    assert capacities["refresh_due"] is True

    cleared = client.put(
        "/api/models/raiker-local-llama-cpp/capacity",
        headers=headers,
        json={"model": "local-gguf", "tokens": None, "reason": "Return to runtime facts"},
    )
    assert cleared.status_code == 200, cleared.text
    history = client.get("/api/models/capacities", headers=headers).json()["entries"]
    entry = next(item for item in history if item["profile_id"] == "raiker-local-llama-cpp")
    assert [item["action"] for item in entry["history"]][:2] == ["cleared", "set"]


def test_resident_scheduler_refreshes_due_capacity_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "scheduled-capacity"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    calls: list[str] = []

    async def refresh(
        _service: object, acting_principal_id: str, *, force: bool = False
    ) -> object:
        calls.append(acting_principal_id)
        from raiker.control.dtos import ControlResult

        return ControlResult(ok=True, data={"profiles": [{"profile_id": "local"}]})

    monkeypatch.setattr(
        "raiker.control.dashboard.DashboardService.refresh_local_model_capacities", refresh
    )
    import asyncio

    assert asyncio.run(TaskScheduler(workspace).refresh_model_capacities()) == 1
    assert calls == ["principal_owner"]
