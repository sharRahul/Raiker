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
from raiker.runtime.executors.tier5_network import (
    CloudExecutionExecutor,
    ProviderSpendSnapshot,
    RemoteExecutionExecutor,
)

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


def test_execution_environment_api_configures_container_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "raiker-tools:approved")
    monkeypatch.setattr("raiker.control.dashboard.shutil.which", lambda name: f"/bin/{name}")
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    saved = client.put(
        "/api/execution-environments/configure",
        headers=headers,
        json={
            "kind": "container",
            "name": "Repository review",
            "enabled": True,
            "config": {
                "runtime": "podman",
                "image": "raiker-tools:approved",
                "tools": ["grep", "read_file"],
                "repository_access": "read_only",
                "writable_output": True,
            },
        },
    )

    assert saved.status_code == 200, saved.text
    view = client.get("/api/execution-environments", headers=headers).json()
    profile = next(
        item for item in view["environments"] if item["profile_id"] == saved.json()["profile_id"]
    )
    assert profile["runtime"] == "podman"
    assert profile["image"] == "raiker-tools:approved"
    assert profile["assigned_tool_count"] == 2
    assert profile["repository_access"] == "read_only"
    assert profile["writable_output"] is True
    assert view["container_options"] == {
        "runtimes": ["docker", "podman"],
        "images": ["raiker-tools:approved"],
        "supported_tools": ["glob", "grep", "list_directory", "read_file", "shell", "stat_path"],
    }


def test_execution_environment_api_rejects_non_allowlisted_container_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "raiker-tools:approved")
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]

    response = client.put(
        "/api/execution-environments/configure",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "container",
            "name": "Unapproved",
            "enabled": True,
            "config": {
                "runtime": "docker",
                "image": "attacker/latest",
                "tools": ["grep"],
                "repository_access": "read_only",
                "writable_output": True,
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "container_image_not_allowed"


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


def test_daytona_budget_is_cumulative_and_provider_actual_replaces_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    service = DashboardService(workspace)
    monkeypatch.setenv("RAIKER_TEST_DAYTONA_KEY", "not-logged")
    cloud_id = service.configure_execution_environment(
        profile_id=None,
        kind="daytona",
        name="Cloud",
        enabled=True,
        config={"sandbox_id": "sandbox-1", "api_key_env": "RAIKER_TEST_DAYTONA_KEY", "max_cost": 5},
        owner_principal_id=OWNER,
    ).data["profile_id"]
    service.store.select_execution_environment(OWNER, cloud_id)
    principal = Principal(OWNER, PrincipalType.HUMAN, "Owner")
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> dict[str, Any]:
        calls.append(command)
        return {"returncode": 0, "stdout_bytes": 0, "stderr_bytes": 0, "truncated": False}

    unavailable = CloudExecutionExecutor(workspace, service.store, runner=runner)
    first = unavailable.execute(
        GovernedAction("act_reserved", OWNER, "cloud_execute", "cloud_execute", {"command": "pwd", "estimated_cost": 3}),
        principal,
    )
    denied = unavailable.execute(
        GovernedAction("act_denied", OWNER, "cloud_execute", "cloud_execute", {"command": "pwd", "estimated_cost": 3}),
        principal,
    )
    assert first.ok
    assert not denied.ok and denied.reason_code == "cloud_execution_budget_exceeded"
    assert len(calls) == 1
    reserved = service.store.cloud_execution_cost_summary(OWNER, cloud_id, max_cost=5)
    assert reserved["reserved_cost"] == 3
    assert reserved["reconciliation_status"] == "provider_unavailable"

    # A separate profile demonstrates actual-cost reconciliation without
    # mutating or discarding the reservation/history events.
    second_id = service.configure_execution_environment(
        profile_id=None,
        kind="daytona",
        name="Metered cloud",
        enabled=True,
        config={"sandbox_id": "sandbox-2", "api_key_env": "RAIKER_TEST_DAYTONA_KEY", "max_cost": 5},
        owner_principal_id=OWNER,
    ).data["profile_id"]
    service.store.select_execution_environment(OWNER, second_id)
    snapshots = iter([ProviderSpendSnapshot(100, "before"), ProviderSpendSnapshot(101.25, "after")])
    metered = CloudExecutionExecutor(
        workspace, service.store, runner=runner, spend_reader=lambda _config, _key: next(snapshots)
    )
    result = metered.execute(
        GovernedAction("act_metered", OWNER, "cloud_execute", "cloud_execute", {"command": "pwd", "estimated_cost": 3}),
        principal,
    )
    assert result.ok
    actual = service.store.cloud_execution_cost_summary(OWNER, second_id, max_cost=5)
    assert actual["actual_cost"] == 1.25
    assert actual["provider_cost"] == 1.25
    assert actual["reserved_cost"] == 0
    assert [item["event_type"] for item in actual["history"]] == [
        "provider_snapshot", "reserved", "provider_snapshot", "reconciled"
    ]
