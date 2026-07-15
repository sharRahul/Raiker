"""Web-app task 5: project folders.

A project is a named organizing scope — a workspace-contained subpath plus the
sessions (and their checkpoints) created while it is active. It is
governance-neutral: creating or selecting a project grants no capability, and
the project root can never escape the workspace (derived server-side from the
name, then verified — fail closed).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
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

    def test_delete_removes_scoped_chats_checkpoints_and_project_root(
        self, service: DashboardService, workspace: Path
    ) -> None:
        project_id = service.create_project("Alpha", OWNER).data["project_id"]
        service.select_project(project_id, OWNER)
        service.store.create_session("sess_alpha", str(workspace))
        _insert_checkpoint(service.store, "ckpt_alpha", "sess_alpha")

        result = service.delete_project(project_id, OWNER, confirm=True)

        assert result.ok, result.reason_code
        assert service.store.load_session("sess_alpha") is None
        assert service.store.load_project(project_id) is None
        assert service.store.get_active_project() is None
        assert not (workspace / "projects" / "alpha").exists()


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


class TestProjectContext:
    def test_project_context_is_explicit_and_only_reaches_its_sessions(
        self, service: DashboardService, workspace: Path
    ) -> None:
        project_id = service.create_project("Alpha", OWNER).data["project_id"]
        service.select_project(project_id, OWNER)
        service.store.create_session("sess_alpha", str(workspace))
        service.select_project(None, OWNER)
        service.store.create_session("sess_other", str(workspace))

        service.store.save_project_context(
            project_id, instructions="Use the Alpha conventions.", attachment_ids=[], memory_enabled=True
        )

        included = ContextGatherer().gather(
            workspace_root=workspace,
            session_id="sess_alpha",
            turn_id="turn_alpha",
            prompt_text="hello",
        ).included_items
        context = [item for item in included if item.source.source_type == "project_context"]
        assert len(context) == 1
        assert "Use the Alpha conventions." in context[0].content
        assert context[0].metadata["memory_enabled"] is True

        other = ContextGatherer().gather(
            workspace_root=workspace,
            session_id="sess_other",
            turn_id="turn_other",
            prompt_text="hello",
        ).included_items
        assert all(item.source.source_type != "project_context" for item in other)


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
        assert client.post("/api/projects/proj_x/export").status_code == 401

    def test_export_returns_direct_project_events_as_ndjson_attachment(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Alpha"}, headers=headers
        ).json()["project_id"]
        client.put("/api/projects/selection", json={"project_id": project_id}, headers=headers)
        session_id = "sess_alpha"
        SQLiteStore(workspace).create_session(session_id, str(workspace))
        EventLogWriter(SQLiteStore(workspace)).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="action_proposed",
                actor="test",
                payload={"message": "export me"},
            )
        )

        response = client.post(f"/api/projects/{project_id}/export", headers=headers)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert len(lines) == 1
        assert response.content.endswith(b"\n")
        assert json.loads(lines[0])["payload"]["message"] == "export me"
        assert str(workspace) not in response.text

    def test_export_preserves_multiple_ndjson_records(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Alpha"}, headers=headers
        ).json()["project_id"]
        client.put("/api/projects/selection", json={"project_id": project_id}, headers=headers)
        store = SQLiteStore(workspace)
        store.create_session("sess_alpha", str(workspace))
        writer = EventLogWriter(store)
        for message in ("first", "second"):
            writer.append(
                make_event(
                    session_id="sess_alpha",
                    turn_id=None,
                    event_type="action_proposed",
                    actor="test",
                    payload={"message": message},
                )
            )

        response = client.post(f"/api/projects/{project_id}/export", headers=headers)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert response.content.endswith(b"\n")
        records = [json.loads(line) for line in response.text.splitlines()]
        assert [record["payload"]["message"] for record in records] == ["first", "second"]

    def test_export_applies_visibility_to_bootstrap_and_named_accounts(
        self, client: TestClient, workspace: Path
    ) -> None:
        owner_headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Alpha"}, headers=owner_headers
        ).json()["project_id"]
        registered = client.post(
            "/api/auth/register", json={"username": "alex", "password": "right-pass-123"}
        )
        assert registered.status_code == 200, registered.text
        alex_headers = {"Authorization": f"Bearer {registered.json()['token']}"}
        maria_registered = client.post(
            "/api/auth/register", json={"username": "maria", "password": "right-pass-123"}
        )
        assert maria_registered.status_code == 200, maria_registered.text
        store = SQLiteStore(workspace)
        alex_principal = store.get_principal(registered.json()["principal_id"])
        assert alex_principal is not None
        alex_user_id = str(alex_principal["delegated_by_user_id"])
        maria_principal = store.get_principal(maria_registered.json()["principal_id"])
        assert maria_principal is not None
        maria_user_id = str(maria_principal["delegated_by_user_id"])
        store.save_active_project(project_id)
        store.create_session("sess_alex", str(workspace), user_id=alex_user_id)
        store.create_session("sess_maria", str(workspace), user_id=maria_user_id)
        store.create_session("sess_legacy", str(workspace))
        writer = EventLogWriter(store)
        for session_id in ("sess_alex", "sess_maria", "sess_legacy"):
            writer.append(
                make_event(
                    session_id=session_id,
                    turn_id=None,
                    event_type="action_proposed",
                    actor="test",
                    payload={"session": session_id},
                )
            )

        owner_response = client.post(f"/api/projects/{project_id}/export", headers=owner_headers)
        assert owner_response.status_code == 200, owner_response.text
        owner_exported = [json.loads(line)["session_id"] for line in owner_response.text.splitlines()]
        assert set(owner_exported) == {"sess_legacy"}

        response = client.post(f"/api/projects/{project_id}/export", headers=alex_headers)

        assert response.status_code == 200, response.text
        exported = [json.loads(line)["session_id"] for line in response.text.splitlines()]
        assert set(exported) == {"sess_alex", "sess_legacy"}

    def test_export_of_empty_project_returns_empty_attachment(
        self, client: TestClient
    ) -> None:
        headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Empty"}, headers=headers
        ).json()["project_id"]

        response = client.post(f"/api/projects/{project_id}/export", headers=headers)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert "attachment" in response.headers["content-disposition"]
        assert response.content == b""

    def test_export_of_unknown_project_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/projects/proj_missing/export", headers=self._headers(client)
        )

        assert response.status_code == 404
        assert response.json()["detail"]["reason_code"] == "unknown_project:proj_missing"

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

    def test_project_context_roundtrip(self, client: TestClient) -> None:
        headers = self._headers(client)
        pid = client.post("/api/projects", json={"name": "Alpha"}, headers=headers).json()["project_id"]
        saved = client.put(
            f"/api/projects/{pid}/context",
            json={"instructions": "Keep changes focused.", "attachment_ids": [], "memory_enabled": True},
            headers=headers,
        )
        assert saved.status_code == 200, saved.text
        detail = client.get(f"/api/projects/{pid}", headers=headers).json()
        assert detail["context"] == {
            "instructions": "Keep changes focused.",
            "attachment_ids": [],
            "memory_enabled": True,
            "memory_mode": "enabled",
        }

    def test_authenticated_human_can_confirm_project_deletion(
        self, client: TestClient, workspace: Path
    ) -> None:
        owner_headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Alpha"}, headers=owner_headers
        ).json()["project_id"]
        registered = client.post(
            "/api/auth/register", json={"username": "alex", "password": "right-pass-123"}
        )
        assert registered.status_code == 200, registered.text

        response = client.delete(
            f"/api/projects/{project_id}",
            headers={
                "Authorization": f"Bearer {registered.json()['token']}",
                "X-Project-Delete-Confirm": project_id,
            },
        )

        assert response.status_code == 200, response.text
        assert not (workspace / "projects" / "alpha").exists()

    def test_project_deletion_requires_an_explicit_confirmation(
        self, client: TestClient
    ) -> None:
        headers = self._headers(client)
        project_id = client.post(
            "/api/projects", json={"name": "Alpha"}, headers=headers
        ).json()["project_id"]

        response = client.delete(f"/api/projects/{project_id}", headers=headers)

        assert response.status_code == 409
        assert response.json()["detail"]["reason_code"] == "project_delete_confirmation_required"

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

    # ── Nested projects/folders API ────────────────────────────────────────────

    def test_tree_list_returns_project_hierarchy(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        # Create root and child via store (service create_project doesn't accept parent_id)
        store = SQLiteStore(workspace)
        store.create_project("p_root", "Root", "projects/root")
        store.create_project("p_child", "Child", "projects/root/child", parent_id="p_root")
        tree = client.get("/api/projects/tree", headers=headers).json()
        assert isinstance(tree, list)
        assert len(tree) == 1
        assert tree[0]["project_id"] == "p_root"
        assert len(tree[0]["children"]) == 1

    def test_move_project_happy_path(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        store = SQLiteStore(workspace)
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        resp = client.put("/api/projects/p2/move", json={"parent_id": None}, headers=headers)
        assert resp.status_code == 200, resp.text

    def test_move_project_rejects_unknown_field(self, client: TestClient) -> None:
        headers = self._headers(client)
        resp = client.put(
            "/api/projects/proj_x/move", json={"parent_id": None, "smuggled": True}, headers=headers
        )
        assert resp.status_code == 422

    def test_archive_project_happy_path(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        store = SQLiteStore(workspace)
        store.create_project("p1", "Root", "projects/root")
        resp = client.put("/api/projects/p1/archive", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        p1 = store.load_project("p1")
        assert p1 is not None and p1["is_archived"] == 1
