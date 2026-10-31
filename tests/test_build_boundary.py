"""DEC-06 step 1 — Build's boundary is the server's answer.

``GET /api/build/boundary`` resolves Project → repository → environment →
model from the stored selections a turn reads, names the first link that would
stop a turn with its one remedy, and never trusts a project id it cannot
resolve for this owner.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.session_state import ModelSessionState
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture(autouse=True)
def measured_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests are about the other links; the sandbox is measured available.

    `test_an_unenforced_sandbox_stops_the_turn_at_the_environment` undoes this.
    """
    from raiker.control.dashboard_parts import execution
    from raiker.execution.profiles import ProfileProbe

    monkeypatch.setattr(
        execution,
        "probe_execution_profile",
        lambda profile, **_: ProfileProbe(
            profile, True, None, "2026-10-30T00:00:00Z", boundary="appcontainer"
        ),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _project(client: TestClient, headers: dict[str, str], name: str = "Alpha") -> str:
    created = client.post("/api/projects", json={"name": name}, headers=headers)
    assert created.status_code in (200, 201), created.text
    return str(created.json()["project_id"])


def _boundary(client: TestClient, headers: dict[str, str], project_id: str | None) -> Any:
    path = "/api/build/boundary" + (f"?project_id={project_id}" if project_id else "")
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_without_a_project_the_project_link_stops_the_turn(
    client: TestClient, headers: dict[str, str]
) -> None:
    body = _boundary(client, headers, None)
    assert body["ready"] is False
    assert body["project_id"] is None
    assert body["refusal"]["step"] == "project"
    assert body["refusal"]["action_href"] == "#/projects"


def test_an_unknown_project_id_is_no_project(
    client: TestClient, headers: dict[str, str]
) -> None:
    body = _boundary(client, headers, "proj_not_mine")
    assert body["project_id"] is None
    assert body["refusal"]["step"] == "project"


def test_with_a_project_and_no_model_the_model_link_stops_it(
    client: TestClient, headers: dict[str, str]
) -> None:
    project_id = _project(client, headers)
    body = _boundary(client, headers, project_id)
    assert body["project_id"] == project_id
    assert body["project_name"] == "Alpha"
    # BUG-316 — the project files the work; reads, writes and commands resolve
    # against the workspace, and the boundary says which folder that is.
    assert body["works_in"] == "ws"
    assert body["environment_name"]
    assert body["refusal"]["step"] == "model"
    assert body["refusal"]["action_href"] == "#/models"
    assert body["model"] is None


def test_a_ready_boundary_names_every_link_in_order(
    client: TestClient,
    headers: dict[str, str],
    workspace: Path,
    mark_model_ready: Callable[..., None],
) -> None:
    project_id = _project(client, headers)
    (workspace / "projects" / "app").mkdir(parents=True)
    repo = client.post(
        "/api/code/repos", json={"kind": "local", "path": "projects/app"}, headers=headers
    ).json()
    client.put("/api/code/repos/selection", json={"repo_id": repo["repo_id"]}, headers=headers)
    store = SQLiteStore(workspace)
    store.save_principal_model_state(
        "principal_owner",
        ModelSessionState(
            session_id="principal_owner",
            profile_id="ollama-local-openai-compatible",
            model="llama3.2:3b",
        ),
    )
    mark_model_ready(workspace, "principal_owner", "ollama-local-openai-compatible", "llama3.2:3b")

    body = _boundary(client, headers, project_id)
    assert body["ready"] is True, body["refusal"]
    assert body["refusal"] is None
    assert body["repo_label"]
    assert body["repo_kind"] == "local"
    assert body["writable_root"] == "projects/app"
    assert body["model"] == "llama3.2:3b"
    assert body["provider"] == "ollama"
    assert body["model_off_machine"] is False
    assert body["model_ready"] is True


def test_an_unenforced_sandbox_stops_the_turn_at_the_environment(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.control.dashboard_parts import execution
    from raiker.execution.profiles import ProfileProbe

    monkeypatch.setattr(
        execution,
        "probe_execution_profile",
        lambda profile, **_: ProfileProbe(
            profile, False, "native_sandbox_not_enforced", "2026-10-30T00:00:00Z", boundary="none"
        ),
    )
    body = _boundary(client, headers, _project(client, headers))
    assert body["ready"] is False
    assert body["refusal"]["step"] == "environment"
    assert body["refusal"]["reason_code"] == "native_sandbox_not_enforced"
    assert body["environment_available"] is False
