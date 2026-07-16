"""Project context remainder (backlog item 1): chat move in/out of a project,
project-scoped schedules, and live ancestor-context inheritance.

A project is an organizing scope — moving a chat into or out of one grants
nothing and changes no gate, policy, or authority. It only changes the bounded
context the chat receives: instructions, shared attachments, and the opt-in
approved-memory boundary. Moving out must remove all of that.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
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
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


def _project(store: SQLiteStore, project_id: str, name: str, parent_id: str | None = None) -> str:
    store.create_project(project_id, name, name.lower(), parent_id=parent_id)
    return project_id


def _session_project(store: SQLiteStore, session_id: str) -> str | None:
    session = store.load_session(session_id)
    assert session is not None
    return session["project_id"]


class TestSessionMove:
    def test_move_session_into_project(self, store: SQLiteStore, service: DashboardService) -> None:
        _project(store, "proj_a", "Alpha")
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")

        result = service.set_session_project("sess_1", "proj_a", OWNER)

        assert result.ok
        assert result.data["project_id"] == "proj_a"
        assert _session_project(store, "sess_1") == "proj_a"

    def test_move_session_out_of_project(self, store: SQLiteStore, service: DashboardService) -> None:
        _project(store, "proj_a", "Alpha")
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")
        service.set_session_project("sess_1", "proj_a", OWNER)

        result = service.set_session_project("sess_1", None, OWNER)

        assert result.ok
        assert result.data["project_id"] is None
        assert _session_project(store, "sess_1") is None

    def test_move_to_unknown_project_is_rejected(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")

        result = service.set_session_project("sess_1", "proj_missing", OWNER)

        assert not result.ok
        assert result.reason_code == "unknown_project:proj_missing"

    def test_move_unknown_session_is_rejected(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")

        result = service.set_session_project("sess_missing", "proj_a", OWNER)

        assert not result.ok
        assert result.reason_code == "unknown_session:sess_missing"

    def test_move_requires_a_resolvable_principal(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")

        result = service.set_session_project("sess_1", "proj_a", "principal_unknown")

        assert not result.ok
        assert result.reason_code == "principal_not_resolved"

    def test_move_emits_a_typed_event(self, store: SQLiteStore, service: DashboardService) -> None:
        _project(store, "proj_a", "Alpha")
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")

        service.set_session_project("sess_1", "proj_a", OWNER)

        types = [row["event_type"] for row in store.list_event_index(session_id="sess_1")]
        assert "session_project_changed" in types


class TestMoveChangesContext:
    def test_context_appears_on_move_in_and_disappears_on_move_out(
        self, workspace: Path, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")
        store.save_project_context(
            "proj_a", instructions="Alpha house rules.", attachment_ids=[], memory_enabled=False
        )
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")
        gatherer = ContextGatherer()

        def instructions_in_context() -> str:
            bundle = gatherer.gather(
                workspace_root=workspace,
                session_id="sess_1",
                turn_id="turn_1",
                prompt_text="hello",
            )
            return "\n".join(item.content for item in bundle.items)

        assert "Alpha house rules." not in instructions_in_context()

        service.set_session_project("sess_1", "proj_a", OWNER)
        assert "Alpha house rules." in instructions_in_context()

        service.set_session_project("sess_1", None, OWNER)
        assert "Alpha house rules." not in instructions_in_context()


class TestAncestorContextIsLive:
    def test_gatherer_merges_ancestor_instructions_root_to_leaf(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _project(store, "proj_root", "Root")
        _project(store, "proj_leaf", "Leaf", parent_id="proj_root")
        store.save_project_context(
            "proj_root", instructions="Root rule.", attachment_ids=[], memory_enabled=False
        )
        store.save_project_context(
            "proj_leaf", instructions="Leaf rule.", attachment_ids=[], memory_enabled=False
        )
        # The active project is per-user, so it is set for the same user the
        # session belongs to — that is what stamps the session's project.
        store.save_active_project("proj_leaf", "owner")
        store.create_session("sess_1", str(store.paths.workspace_root), user_id="owner")

        bundle = ContextGatherer().gather(
            workspace_root=workspace,
            session_id="sess_1",
            turn_id="turn_1",
            prompt_text="hello",
        )
        content = "\n".join(item.content for item in bundle.items)

        assert "Root rule." in content
        assert "Leaf rule." in content
        assert content.index("Root rule.") < content.index("Leaf rule.")

    def test_effective_context_unions_attachments_and_keeps_leaf_memory_flag(
        self, store: SQLiteStore
    ) -> None:
        _project(store, "proj_root", "Root")
        _project(store, "proj_leaf", "Leaf", parent_id="proj_root")
        store.save_project_context(
            "proj_root", instructions="Root rule.", attachment_ids=[], memory_enabled=True
        )
        store.save_project_context(
            "proj_leaf", instructions="Leaf rule.", attachment_ids=[], memory_enabled=False
        )

        effective = store.load_effective_project_context("proj_leaf")

        assert effective["instructions"] == "Root rule.\n\nLeaf rule."
        assert effective["memory_enabled"] is False

    def test_archived_ancestor_context_is_not_inherited(self, store: SQLiteStore) -> None:
        _project(store, "proj_root", "Root")
        _project(store, "proj_leaf", "Leaf", parent_id="proj_root")
        store.save_project_context(
            "proj_root", instructions="Root rule.", attachment_ids=[], memory_enabled=False
        )
        store.save_project_context(
            "proj_leaf", instructions="Leaf rule.", attachment_ids=[], memory_enabled=False
        )
        store.archive_project("proj_root")

        effective = store.load_effective_project_context("proj_leaf")

        assert "Root rule." not in effective["instructions"]
        assert "Leaf rule." in effective["instructions"]


class TestProjectScopedSchedules:
    def test_task_is_stamped_with_the_active_project(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")
        store.save_active_project("proj_a", "owner")

        task = service.create_task(
            title="Weekly review",
            objective="Summarise the week",
            user_id="owner",
            principal_id=OWNER,
            scheduled_at="2026-07-20T09:00:00Z",
            recurrence="weekly",
        )

        assert task.project_id == "proj_a"

    def test_explicit_project_overrides_the_active_project(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")
        _project(store, "proj_b", "Beta")
        store.save_active_project("proj_a")

        task = service.create_task(
            title="Beta task",
            objective="Do beta work",
            user_id="owner",
            principal_id=OWNER,
            project_id="proj_b",
        )

        assert task.project_id == "proj_b"

    def test_task_without_an_active_project_has_no_project(
        self, service: DashboardService
    ) -> None:
        task = service.create_task(
            title="Loose task", objective="No project", user_id="owner", principal_id=OWNER
        )

        assert task.project_id is None

    def test_task_list_is_filtered_by_project(
        self, store: SQLiteStore, service: DashboardService
    ) -> None:
        _project(store, "proj_a", "Alpha")
        _project(store, "proj_b", "Beta")
        service.create_task(
            title="Alpha task", objective="a", user_id="owner", principal_id=OWNER, project_id="proj_a"
        )
        service.create_task(
            title="Beta task", objective="b", user_id="owner", principal_id=OWNER, project_id="proj_b"
        )
        service.create_task(title="Loose task", objective="c", user_id="owner", principal_id=OWNER)

        alpha = service.list_tasks(project_id="proj_a", user_id="owner")
        beta = service.list_tasks(project_id="proj_b", user_id="owner")
        every = service.list_tasks(user_id="owner")

        assert [t.title for t in alpha] == ["Alpha task"]
        assert [t.title for t in beta] == ["Beta task"]
        assert len(every) == 3

    def test_unknown_project_on_create_is_rejected(self, service: DashboardService) -> None:
        with pytest.raises(ValueError, match="unknown_project"):
            service.create_task(
                title="Ghost task",
                objective="x",
                user_id="owner",
                principal_id=OWNER,
                project_id="proj_missing",
            )


class TestApi:
    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        return TestClient(create_app(workspace))

    def _headers(self, client: TestClient) -> dict[str, str]:
        resp = client.post("/api/auth/session", json={"as_principal": None})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['token']}"}

    def test_move_round_trip_through_the_api(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        store = SQLiteStore(workspace)
        _project(store, "proj_a", "Alpha")
        store.create_session("sess_a", str(workspace))

        moved_in = client.put(
            "/api/sessions/sess_a/project", json={"project_id": "proj_a"}, headers=headers
        )
        assert moved_in.status_code == 200, moved_in.text
        assert moved_in.json()["project_id"] == "proj_a"
        listing = client.get("/api/sessions", params={"project_id": "proj_a"}, headers=headers).json()
        assert [s["session_id"] for s in listing] == ["sess_a"]
        assert listing[0]["project_id"] == "proj_a"

        moved_out = client.put(
            "/api/sessions/sess_a/project", json={"project_id": None}, headers=headers
        )
        assert moved_out.status_code == 200, moved_out.text
        assert moved_out.json()["project_id"] is None
        assert client.get("/api/sessions", params={"project_id": "proj_a"}, headers=headers).json() == []

    def test_unknown_session_move_is_a_403(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        _project(SQLiteStore(workspace), "proj_a", "Alpha")

        resp = client.put(
            "/api/sessions/sess_missing/project", json={"project_id": "proj_a"}, headers=headers
        )

        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_session:sess_missing"

    def test_move_requires_authentication(self, client: TestClient, workspace: Path) -> None:
        SQLiteStore(workspace).create_session("sess_a", str(workspace))

        resp = client.put("/api/sessions/sess_a/project", json={"project_id": None})

        assert resp.status_code in (401, 403)

    def test_task_list_is_scoped_by_project_through_the_api(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = self._headers(client)
        _project(SQLiteStore(workspace), "proj_a", "Alpha")

        created = client.post(
            "/api/tasks",
            json={"title": "Alpha task", "description": "a", "project_id": "proj_a"},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["project_id"] == "proj_a"
        client.post("/api/tasks", json={"title": "Loose task", "description": "b"}, headers=headers)

        scoped = client.get("/api/tasks", params={"project_id": "proj_a"}, headers=headers).json()
        assert [t["title"] for t in scoped] == ["Alpha task"]
        assert len(client.get("/api/tasks", headers=headers).json()) == 2

    def test_task_create_with_unknown_project_is_a_422(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = self._headers(client)

        resp = client.post(
            "/api/tasks",
            json={"title": "Ghost", "description": "x", "project_id": "proj_missing"},
            headers=headers,
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "unknown_project:proj_missing"


class TestSessionIsolation:
    """An account cannot move another account's chat between projects."""

    @pytest.fixture
    def client(self, workspace: Path) -> TestClient:
        return TestClient(create_app(workspace))

    def test_account_cannot_move_another_accounts_session(  # type: ignore[no-untyped-def]
        self, client: TestClient, workspace: Path, seed_account
    ) -> None:
        # Both accounts are seeded directly: this workspace is already
        # CLI-bootstrapped with an owner, so registration refuses them. A
        # session still only moves for the account that owns it.
        store = SQLiteStore(workspace)
        bob_principal_id, bob_token = seed_account(workspace, "bob")
        bob_principal = store.get_principal(bob_principal_id)
        assert bob_principal is not None
        store.create_session(
            "sess_bob", str(workspace), user_id=str(bob_principal["delegated_by_user_id"])
        )
        assert bob_token

        alex_principal_id, alex_token = seed_account(workspace, "alex")
        alex_headers = {"Authorization": f"Bearer {alex_token}"}
        # Alex owns the destination project, so the move is refused for the one
        # reason under test: the session is Bob's.
        store.create_project(
            "proj_a", "Alpha", "alpha", owner_user_id=store.principal_user_id(alex_principal_id)
        )

        resp = client.put(
            "/api/sessions/sess_bob/project", json={"project_id": "proj_a"}, headers=alex_headers
        )

        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_session:sess_bob"
        assert _session_project(store, "sess_bob") is None
