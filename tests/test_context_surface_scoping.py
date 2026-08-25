"""Chat and Build retrieval boundaries, enforced by the backend.

The boundary is a property of the turn, not of which UI submitted it, so these
tests drive the gatherer and the prompt API directly rather than a component.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer, ContextScopeError
from raiker.contracts.ids import new_id
from raiker.control.dashboard import DashboardService
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("bootstrap", "Bootstrap", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def account(workspace: Path, seed_account: Any) -> tuple[str, str]:
    """A credential-backed account, because only one of those is owner-scoped.

    ``account_scope`` resolves a *real* local account; a CLI-bootstrapped
    principal has no credential row and gathers unscoped, which is the one
    configuration in which none of these boundaries apply.
    """
    result: tuple[str, str] = seed_account(workspace, "owner")
    return result


@pytest.fixture
def owner(account: tuple[str, str]) -> str:
    return account[0]


@pytest.fixture
def headers(account: tuple[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {account[1]}"}


def _project(workspace: Path, owner: str, name: str) -> str:
    result = DashboardService(workspace).create_project(name, owner)
    assert result.ok, result.data
    return str(result.data["project_id"])


def _import(client: TestClient, headers: dict[str, str], url: str, path: str, text: str) -> str:
    response = client.post(
        url,
        json={
            "files": [
                {
                    "relative_path": path,
                    "media_type": "text/markdown",
                    "data_base64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["ok"] is True, result
    return str(result["file_id"])


def _session(workspace: Path, owner: str, *, project_id: str | None, title: str) -> str:
    store = SQLiteStore(workspace)
    session_id = new_id("sess_")
    user_id = store.principal_user_id(owner)
    store.create_session(session_id, str(workspace), title=title, user_id=user_id)
    if project_id is not None:
        assert store.set_session_project(session_id, project_id, user_id=user_id)
    return session_id


def _gather(
    workspace: Path, owner: str, *, surface: str, project_id: str | None, prompt: str
) -> Any:
    return ContextGatherer().gather(
        workspace_root=workspace,
        session_id=_session(workspace, owner, project_id=None, title="Current"),
        turn_id=new_id("turn_"),
        prompt_text=prompt,
        owner_principal_id=owner,
        surface=surface,
        project_id=project_id,
    )


def _recall(bundle: Any) -> dict[str, Any]:
    for item in bundle.items:
        if item.source.source_type == "memory_recall":
            return {"content": item.content, "metadata": item.metadata}
    return {"content": "", "metadata": {}}


@pytest.fixture
def two_projects(
    workspace: Path, owner: str, client: TestClient, headers: dict[str, str]
) -> dict[str, str]:
    alpha = _project(workspace, owner, "Alpha")
    beta = _project(workspace, owner, "Beta")
    _import(
        client, headers, f"/api/projects/{alpha}/managed-files",
        "handbook.md", "The alpha handbook covers the shared keyword rollout.",
    )
    _import(
        client, headers, f"/api/projects/{beta}/managed-files",
        "handbook.md", "The beta handbook also covers the shared keyword rollout.",
    )
    _import(client, headers, "/api/memory/files", "account.md", "Account-wide handbook notes about the rollout.")
    return {"alpha": alpha, "beta": beta}


def test_chat_recall_can_find_every_owned_project(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    recall = _recall(
        _gather(workspace, owner, surface="chat", project_id=None, prompt="handbook rollout")
    )

    assert "alpha handbook" in recall["content"]
    assert "beta handbook" in recall["content"]
    assert recall["metadata"]["surface"] == "chat"


def test_build_recall_excludes_other_project_files(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    recall = _recall(
        _gather(
            workspace, owner, surface="build",
            project_id=two_projects["alpha"], prompt="handbook rollout",
        )
    )

    assert "alpha handbook" in recall["content"]
    assert "beta handbook" not in recall["content"]
    # Account-wide memory files stay in scope: they belong to the owner, not a project.
    assert "Account-wide handbook notes" in recall["content"]
    assert recall["metadata"]["project_id"] == two_projects["alpha"]


def test_build_recall_excludes_other_projects_memories(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    store = SQLiteStore(workspace)
    for key, marker in (("alpha", "alpha roadmap milestone"), ("beta", "beta roadmap milestone")):
        write_memory(
            marker,
            workspace_root=workspace,
            store=store,
            governance=MemoryGovernance(
                "evt", "session", None, "test", 1.0, 1.0, "until_forget", "approved", owner
            ),
            scope=f"project:{two_projects[key]}",
            owner_principal_id=owner,
        )

    recall = _recall(
        _gather(
            workspace, owner, surface="build",
            project_id=two_projects["alpha"], prompt="roadmap milestone",
        )
    )

    assert "alpha roadmap milestone" in recall["content"]
    assert "beta roadmap milestone" not in recall["content"]


def test_build_recall_excludes_unassigned_and_other_project_chats(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    assigned = _session(workspace, owner, project_id=two_projects["alpha"], title="Alpha planning")
    unassigned = _session(workspace, owner, project_id=None, title="Loose thoughts")
    other = _session(workspace, owner, project_id=two_projects["beta"], title="Beta planning")

    recall = _recall(
        _gather(
            workspace, owner, surface="build",
            project_id=two_projects["alpha"], prompt="planning",
        )
    )
    session_ids = set(recall["metadata"]["session_ids"])

    assert assigned in session_ids
    assert unassigned not in session_ids
    assert other not in session_ids


def test_chat_recall_includes_unassigned_chats(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    unassigned = _session(workspace, owner, project_id=None, title="Loose thoughts")

    recall = _recall(
        _gather(workspace, owner, surface="chat", project_id=None, prompt="thoughts")
    )

    assert unassigned in set(recall["metadata"]["session_ids"])


def test_build_without_a_project_fails_closed(workspace: Path, owner: str) -> None:
    with pytest.raises(ContextScopeError, match="build_requires_project"):
        _gather(workspace, owner, surface="build", project_id=None, prompt="work")


def test_build_with_an_unowned_project_fails_closed(workspace: Path, owner: str) -> None:
    with pytest.raises(ContextScopeError, match="build_project_not_found"):
        _gather(workspace, owner, surface="build", project_id="proj_absent", prompt="work")


def test_chat_cannot_declare_a_project_scope(
    workspace: Path, owner: str, two_projects: dict[str, str]
) -> None:
    bundle = _gather(
        workspace, owner, surface="chat", project_id=two_projects["alpha"], prompt="handbook"
    )

    # Chat drops the project rather than half-applying it.
    assert _recall(bundle)["metadata"]["project_id"] == ""


def test_prompt_api_rejects_build_without_a_project(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/prompts", json={"text": "work", "surface": "build"}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "build_requires_project"


def test_prompt_api_rejects_an_unowned_build_project(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/prompts",
        json={"text": "work", "surface": "build", "project_id": "proj_absent"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "build_project_not_found"


def test_prompt_api_rejects_a_project_on_chat(
    workspace: Path, owner: str, client: TestClient, headers: dict[str, str]
) -> None:
    project_id = _project(workspace, owner, "Alpha")

    response = client.post(
        "/api/prompts",
        json={"text": "hello", "surface": "chat", "project_id": project_id},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "chat_has_no_project_scope"


def test_streaming_prompt_enforces_the_same_boundary(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/prompts/stream", json={"text": "work", "surface": "build"}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason_code"] == "build_requires_project"
