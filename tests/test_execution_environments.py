from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.approvals.execution import executable_capability
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.models.tool_call_validation import default_tool_specs
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.tier5_network import CloudExecutionExecutor, RemoteExecutionExecutor

OWNER = "principal_owner"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "execution"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    return workspace


def test_execution_environment_api_configures_and_selects_ssh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    identity = workspace / "id_ed25519"
    identity.write_text("test key path only", encoding="utf-8")
    monkeypatch.setenv("RAIKER_TEST_SSH_KEY", str(identity))
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    saved = client.put(
        "/api/execution-environments/configure",
        headers=headers,
        json={
            "kind": "ssh", "name": "Build host", "enabled": True,
            "config": {"host": "build.example.com", "user": "raiker", "credential_env": "RAIKER_TEST_SSH_KEY"},
        },
    )
    assert saved.status_code == 200, saved.text
    profile_id = saved.json()["profile_id"]
    view = client.get("/api/execution-environments", headers=headers).json()
    remote = next(item for item in view["environments"] if item["profile_id"] == profile_id)
    assert remote["available"] is True
    assert "test key path only" not in str(remote)
    selected = client.put(
        "/api/execution-environments/selection", headers=headers, json={"profile_id": profile_id}
    )
    assert selected.status_code == 200, selected.text
    assert client.get("/api/execution-environments", headers=headers).json()["selected_profile_id"] == profile_id


def test_remote_and_daytona_executors_are_real_bounded_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    service = DashboardService(workspace)
    identity = workspace / "identity"
    identity.write_text("placeholder", encoding="utf-8")
    monkeypatch.setenv("RAIKER_TEST_SSH_KEY", str(identity))
    monkeypatch.setenv("RAIKER_TEST_DAYTONA_KEY", "not-logged")
    ssh_id = service.configure_execution_environment(
        profile_id=None, kind="ssh", name="SSH", enabled=True,
        config={"host": "example.com", "user": "runner", "credential_env": "RAIKER_TEST_SSH_KEY"},
        owner_principal_id=OWNER,
    ).data["profile_id"]
    cloud_id = service.configure_execution_environment(
        profile_id=None, kind="daytona", name="Cloud", enabled=True,
        config={"sandbox_id": "sandbox-1", "api_key_env": "RAIKER_TEST_DAYTONA_KEY", "max_cost": 5},
        owner_principal_id=OWNER,
    ).data["profile_id"]
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        calls.append((list(command), kwargs))
        return {"returncode": 0, "stdout_bytes": 2, "stderr_bytes": 0, "truncated": False}

    principal = Principal(OWNER, PrincipalType.HUMAN, "Owner")
    service.store.select_execution_environment(OWNER, ssh_id)
    ssh = RemoteExecutionExecutor(workspace, service.store, runner=runner).execute(
        GovernedAction("act_ssh", OWNER, "remote_execute", "remote_execute", {"command": "pwd"}), principal
    )
    service.store.select_execution_environment(OWNER, cloud_id)
    cloud = CloudExecutionExecutor(workspace, service.store, runner=runner).execute(
        GovernedAction("act_cloud", OWNER, "cloud_execute", "cloud_execute", {"command": "pwd", "estimated_cost": 1}), principal
    )
    assert ssh.ok and cloud.ok
    assert calls[0][0][0] == "ssh" and "StrictHostKeyChecking=yes" in calls[0][0]
    assert calls[1][0][:3] == ["daytona", "exec", "sandbox-1"]
    assert calls[1][1]["env"] == {"DAYTONA_API_KEY": "not-logged"}
    assert "remote_execution_cap" in REAL_EXECUTOR_CAPABILITIES
    assert "cloud_execution_cap" in REAL_EXECUTOR_CAPABILITIES
    assert build_default_executor_registry(workspace, service.store).has("remote_execution_cap")
    assert {"remote_execute", "cloud_execute"} <= {spec.name for spec in default_tool_specs()}
    assert executable_capability("remote_execute") == "remote_execution_cap"
    assert executable_capability("cloud_execute") == "cloud_execution_cap"
