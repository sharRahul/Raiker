"""Attaching, indexing and browsing a project's root over HTTP.

Browse is the route that matters most here, because it is the one that hands a
folder the owner granted back to a browser. It resolves through the same
`PathAuthority` a turn writes through — not a second containment check written
for the API — so a path the runtime would refuse cannot be reached by asking the
web app for it instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


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
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def external(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "util").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('x')\n", encoding="utf-8")
    (root / "README.md").write_text("The alpha rollout runbook.\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    return root


@pytest.fixture
def attached_project(workspace: Path, external: Path) -> str:
    service = DashboardService(workspace)
    created = service.create_project("Alpha", OWNER)
    attached = service.attach_project_folder(
        created.data["project_id"], str(external), OWNER
    )
    assert attached.ok, attached.reason_code
    return str(created.data["project_id"])


@pytest.fixture
def managed_project(workspace: Path) -> str:
    created = DashboardService(workspace).create_project("Beta", OWNER)
    assert created.ok, created.reason_code
    return str(created.data["project_id"])


class TestAuthentication:
    def test_every_route_requires_authentication(
        self, client: TestClient, attached_project: str
    ) -> None:
        base = f"/api/projects/{attached_project}"
        assert client.post(f"{base}/root/attach", json={"path": "C:/x"}).status_code == 401
        assert client.delete(f"{base}/root").status_code == 401
        assert client.post(f"{base}/root/index").status_code == 401
        assert client.get(f"{base}/root/status").status_code == 401
        assert client.get(f"{base}/browse").status_code == 401

    def test_an_unknown_project_is_not_found_never_forbidden(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        response = client.get("/api/projects/proj_nope/browse", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"]["reason_code"] == "project_not_found"


class TestBrowse:
    def test_browse_lists_the_root(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        body = client.get(
            f"/api/projects/{attached_project}/browse", headers=headers
        ).json()

        assert {entry["name"] for entry in body["entries"]} == {"src", "README.md"}
        assert body["root_kind"] == "attached"
        assert body["root_missing"] is False
        assert body["parent"] is None

    def test_browse_lists_one_directory_and_nothing_above_it(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        response = client.get(
            f"/api/projects/{attached_project}/browse?path=src", headers=headers
        )

        assert response.status_code == 200
        body = response.json()
        assert {entry["name"] for entry in body["entries"]} == {"main.py", "util"}
        assert body["parent"] == ""

    def test_directories_sort_before_files(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        body = client.get(
            f"/api/projects/{attached_project}/browse?path=src", headers=headers
        ).json()

        assert [entry["name"] for entry in body["entries"]] == ["util", "main.py"]

    def test_browse_refuses_a_path_above_the_root(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        response = client.get(
            f"/api/projects/{attached_project}/browse?path=../secrets", headers=headers
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "outside_workspace"

    def test_browse_refuses_an_absolute_path(
        self, client: TestClient, headers: dict[str, str], attached_project: str, tmp_path: Path
    ) -> None:
        # A relative path is what the contract takes. Accepting an absolute one
        # would let the caller name a root the project was never given.
        response = client.get(
            f"/api/projects/{attached_project}/browse",
            params={"path": str(tmp_path / "elsewhere")},
            headers=headers,
        )

        assert response.status_code == 400

    def test_browse_hides_the_ignored_directories(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        body = client.get(
            f"/api/projects/{attached_project}/browse", headers=headers
        ).json()

        assert "node_modules" not in {entry["name"] for entry in body["entries"]}

    def test_browse_reports_a_missing_root_rather_than_an_empty_tree(
        self, workspace: Path, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        DashboardService(workspace).detach_project_folder(attached_project, OWNER)

        body = client.get(
            f"/api/projects/{attached_project}/browse", headers=headers
        ).json()

        assert body["root_missing"] is True
        assert body["entries"] == []

    def test_browse_works_for_a_managed_project_too(
        self, workspace: Path, client: TestClient, headers: dict[str, str], managed_project: str
    ) -> None:
        # One explorer over both root kinds is the point; a managed project that
        # answered differently would need a second surface.
        root = workspace / ".raiker" / "projects" / "beta"
        (root / "notes.md").write_text("beta", encoding="utf-8")

        body = client.get(
            f"/api/projects/{managed_project}/browse", headers=headers
        ).json()

        assert body["root_kind"] == "managed"
        assert {entry["name"] for entry in body["entries"]} == {"notes.md"}


class TestIndexAndStatus:
    def test_status_states_watching_and_staleness(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        body = client.get(
            f"/api/projects/{attached_project}/root/status", headers=headers
        ).json()

        assert body["root_kind"] == "attached"
        assert body["watching"] is False
        assert body["watch_reason"] == "not_started"
        assert body["last_scanned_at"] == ""
        assert body["indexed_files"] == 0

    def test_indexing_now_catalogues_the_folder(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        response = client.post(
            f"/api/projects/{attached_project}/root/index", headers=headers
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert body["indexed"] >= 1
        status_body = client.get(
            f"/api/projects/{attached_project}/root/status", headers=headers
        ).json()
        assert status_body["indexed_files"] >= 1

    def test_browse_shows_index_state_only_once_indexed(
        self, client: TestClient, headers: dict[str, str], attached_project: str
    ) -> None:
        before = client.get(
            f"/api/projects/{attached_project}/browse", headers=headers
        ).json()
        assert all(entry["index_state"] is None for entry in before["entries"])

        client.post(f"/api/projects/{attached_project}/root/index", headers=headers)

        after = client.get(
            f"/api/projects/{attached_project}/browse", headers=headers
        ).json()
        readme = next(e for e in after["entries"] if e["name"] == "README.md")
        assert readme["index_state"] == "ready"

    def test_indexing_a_managed_project_is_refused(
        self, client: TestClient, headers: dict[str, str], managed_project: str
    ) -> None:
        # A managed project's files arrive by import, which already indexes
        # them; a scan would find only what Raiker itself wrote.
        response = client.post(
            f"/api/projects/{managed_project}/root/index", headers=headers
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "project_root_not_attached"


class TestAttachAndDetach:
    def test_attaching_a_folder_makes_it_the_root(
        self, tmp_path: Path, client: TestClient, headers: dict[str, str], managed_project: str
    ) -> None:
        folder = tmp_path / "other-repo"
        folder.mkdir()

        response = client.post(
            f"/api/projects/{managed_project}/root/attach",
            json={"path": str(folder), "writable": True},
            headers=headers,
        )

        assert response.status_code == 200, response.text
        body = client.get(
            f"/api/projects/{managed_project}/root/status", headers=headers
        ).json()
        assert body["root_kind"] == "attached"
        assert body["writable"] is True

    def test_attaching_a_folder_inside_the_workspace_is_refused(
        self, workspace: Path, client: TestClient, headers: dict[str, str], managed_project: str
    ) -> None:
        inside = workspace / "inside"
        inside.mkdir()

        response = client.post(
            f"/api/projects/{managed_project}/root/attach",
            json={"path": str(inside)},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "attach_path_inside_workspace"

    def test_detaching_leaves_every_file_alone(
        self, workspace: Path, client: TestClient, headers: dict[str, str],
        attached_project: str, external: Path,
    ) -> None:
        response = client.delete(
            f"/api/projects/{attached_project}/root", headers=headers
        )

        assert response.status_code == 200, response.text
        # Only the pointer goes. Detaching a project is not revoking a folder,
        # and it is certainly not deleting one.
        assert (external / "README.md").is_file()
        assert SQLiteStore(workspace).list_brain_source_grants(OWNER)
        assert (
            client.get(
                f"/api/projects/{attached_project}/browse", headers=headers
            ).json()["root_missing"]
            is True
        )
