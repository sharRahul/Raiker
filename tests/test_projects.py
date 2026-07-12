"""Web-app task 5: project folders.

A project is a named organizing scope — a workspace-contained subpath plus the
sessions (and their checkpoints) created while it is active. It is
governance-neutral: creating or selecting a project grants no capability, and
the project root can never escape the workspace (derived server-side from the
name, then verified — fail closed).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_rahul"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


def _insert_checkpoint(store: SQLiteStore, checkpoint_id: str, session_id: str) -> None:
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO checkpoints
               (checkpoint_id, session_id, checkpoint_type, manifest_path, created_at,
                can_restore_state, can_restore_files)
               VALUES (?, ?, 'turn', 'x', ?, 0, 0)""",
            (checkpoint_id, session_id, utc_now()),
        )


class TestCreateProject:
    def test_create_lists_and_makes_a_contained_root(self, service: DashboardService, workspace: Path) -> None:
        result = service.create_project("Tejas Mk1A", OWNER)
        assert result.ok, result.reason_code
        assert result.data["root_subpath"] == "projects/tejas-mk1a"
        assert (workspace / "projects" / "tejas-mk1a").is_dir()

        listing = service.list_projects()
        assert len(listing.projects) == 1
        view = listing.projects[0]
        assert view.name == "Tejas Mk1A"
        assert view.session_count == 0
        assert view.selected is False
        assert listing.active_project_id is None

    def test_traversal_shaped_names_cannot_escape_the_workspace(
        self, service: DashboardService, workspace: Path
    ) -> None:
        # The slug strips separators/dots, so the root stays inside the
        # workspace no matter what the name looks like.
        result = service.create_project("../../evil", OWNER)
        assert result.ok
        root = (workspace / result.data["root_subpath"]).resolve()
        assert workspace.resolve() in root.parents
        assert not (workspace.parent / "evil").exists()

    def test_empty_and_symbol_only_names_fail_closed(self, service: DashboardService) -> None:
        assert service.create_project("", OWNER).reason_code == "invalid_project_name"
        assert service.create_project("   ", OWNER).reason_code == "invalid_project_name"
        assert service.create_project("///", OWNER).reason_code == "invalid_project_name"
        assert service.create_project("x" * 101, OWNER).reason_code == "invalid_project_name"

    def test_duplicate_names_and_roots_are_rejected(self, service: DashboardService) -> None:
        assert service.create_project("My App", OWNER).ok
        assert service.create_project("My App", OWNER).reason_code == "duplicate_project_name"
        # A different name that slugs to the same root is also rejected.
        assert service.create_project("my  app", OWNER).reason_code == "duplicate_project_root"

    def test_unknown_principal_is_rejected(self, service: DashboardService) -> None:
        result = service.create_project("P", "principal_ghost")
        assert not result.ok
        assert result.reason_code == "principal_not_resolved"


class TestSelectProject:
    def test_select_and_clear(self, service: DashboardService) -> None:
        created = service.create_project("Alpha", OWNER)
        pid = created.data["project_id"]

        selected = service.select_project(pid, OWNER)
        assert selected.ok
        assert selected.data["active_project_id"] == pid
        listing = service.list_projects()
        assert listing.active_project_id == pid
        assert listing.projects[0].selected is True

        cleared = service.select_project(None, OWNER)
        assert cleared.ok
        assert service.list_projects().active_project_id is None

    def test_unknown_project_fails_closed(self, service: DashboardService) -> None:
        result = service.select_project("proj_missing", OWNER)
        assert not result.ok
        assert result.reason_code == "unknown_project:proj_missing"


class TestSessionAssociation:
    def test_new_sessions_are_stamped_with_the_active_project(
        self, service: DashboardService, workspace: Path
    ) -> None:
        pid = service.create_project("Alpha", OWNER).data["project_id"]
        store = service.store
        store.create_session("sess_before", str(workspace))
        service.select_project(pid, OWNER)
        store.create_session("sess_in_project", str(workspace))
        service.select_project(None, OWNER)
        store.create_session("sess_after", str(workspace))

        in_project = [s.session_id for s in service.list_sessions(project_id=pid)]
        assert in_project == ["sess_in_project"]
        all_sessions = {s.session_id for s in service.list_sessions()}
        assert all_sessions == {"sess_before", "sess_in_project", "sess_after"}

    def test_checkpoints_filter_by_project_through_their_session(
        self, service: DashboardService, workspace: Path
    ) -> None:
        pid = service.create_project("Alpha", OWNER).data["project_id"]
        store = service.store
        service.select_project(pid, OWNER)
        store.create_session("sess_p", str(workspace))
        service.select_project(None, OWNER)
        store.create_session("sess_free", str(workspace))
        _insert_checkpoint(store, "ckpt_p", "sess_p")
        _insert_checkpoint(store, "ckpt_free", "sess_free")

        scoped = [c.checkpoint_id for c in service.list_checkpoints(project_id=pid)]
        assert scoped == ["ckpt_p"]
        assert {c.checkpoint_id for c in service.list_checkpoints()} == {"ckpt_p", "ckpt_free"}

    def test_get_project_detail_bundles_scoped_sessions_and_checkpoints(
        self, service: DashboardService, workspace: Path
    ) -> None:
        pid = service.create_project("Alpha", OWNER).data["project_id"]
        service.select_project(pid, OWNER)
        service.store.create_session("sess_p", str(workspace))
        _insert_checkpoint(service.store, "ckpt_p", "sess_p")

        detail = service.get_project(pid)
        assert detail is not None
        assert detail.project.project_id == pid
        assert detail.project.session_count == 1
        assert [s.session_id for s in detail.sessions] == ["sess_p"]
        assert [c.checkpoint_id for c in detail.checkpoints] == ["ckpt_p"]

        assert service.get_project("proj_missing") is None


class TestProjectsApi:
    @pytest.fixture
    def app(self, workspace: Path) -> FastAPI:
        return create_app(workspace)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def _headers(self, client: TestClient) -> dict[str, str]:
        resp = client.post("/api/auth/session", json={"as_principal": None})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['token']}"}

    def test_routes_require_auth(self, client: TestClient) -> None:
        assert client.get("/api/projects").status_code == 401
        assert client.post("/api/projects", json={"name": "P"}).status_code == 401
        assert client.put("/api/projects/selection", json={"project_id": None}).status_code == 401

    def test_create_list_select_detail_roundtrip(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)

        created = client.post("/api/projects", json={"name": "Tejas Mk1A"}, headers=headers)
        assert created.status_code == 200, created.text
        pid = created.json()["project_id"]
        assert (workspace / "projects" / "tejas-mk1a").is_dir()

        listing = client.get("/api/projects", headers=headers).json()
        assert [p["project_id"] for p in listing["projects"]] == [pid]
        assert listing["active_project_id"] is None

        selected = client.put(
            "/api/projects/selection", json={"project_id": pid}, headers=headers
        )
        assert selected.status_code == 200
        assert selected.json()["active_project_id"] == pid

        detail = client.get(f"/api/projects/{pid}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["project"]["selected"] is True

        assert client.get("/api/projects/proj_missing", headers=headers).status_code == 404

    def test_invalid_create_is_an_honest_403(self, client: TestClient) -> None:
        headers = self._headers(client)
        resp = client.post("/api/projects", json={"name": "   "}, headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "invalid_project_name"

    def test_sessions_and_checkpoints_accept_a_project_filter(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = self._headers(client)
        pid = client.post("/api/projects", json={"name": "Alpha"}, headers=headers).json()[
            "project_id"
        ]
        client.put("/api/projects/selection", json={"project_id": pid}, headers=headers)
        store = SQLiteStore(workspace)
        store.create_session("sess_p", str(workspace))
        client.put("/api/projects/selection", json={"project_id": None}, headers=headers)
        store.create_session("sess_free", str(workspace))
        _insert_checkpoint(store, "ckpt_p", "sess_p")
        _insert_checkpoint(store, "ckpt_free", "sess_free")

        sessions = client.get(f"/api/sessions?project_id={pid}", headers=headers).json()
        assert [s["session_id"] for s in sessions] == ["sess_p"]
        checkpoints = client.get(f"/api/checkpoints?project_id={pid}", headers=headers).json()
        assert [c["checkpoint_id"] for c in checkpoints] == ["ckpt_p"]
