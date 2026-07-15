"""Reliable memory controls (backlog item 3): user-visible memory list with
pin/bookmark, forget, and an incognito opt-out boundary — all over the EXISTING
governed memory store (no second memory system is created).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.control.dashboard import DashboardService
from raiker.memory.store import MemoryGovernance, get_memory, search_memory, write_memory
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


def _seed_memory(
    store: SQLiteStore,
    workspace: Path,
    *,
    text: str = "The user prefers tabs over spaces.",
    scope: str = "project:proj_alpha",
) -> str:
    return write_memory(
        text,
        workspace_root=workspace,
        scope=scope,
        governance=MemoryGovernance(
            source_event_id="evt_seed",
            source_session_id="sess_seed",
            source_turn_id="turn_seed",
            source_type="agent",
            confidence=0.9,
            trust_score=0.8,
            retention="until_forget",
            approval_state="approved",
            created_by="test",
        ),
        store=store,
    ).memory_id


class TestMemoryList:
    def test_list_returns_memories_with_governance_metadata(
        self, service: DashboardService, workspace: Path
    ) -> None:
        mid = _seed_memory(service.store, workspace)
        memories = service.list_memories()
        assert len(memories) == 1
        m = memories[0]
        assert m.memory_id == mid
        assert "tabs" in m.text
        assert m.scope == "project:proj_alpha"
        assert m.confidence == 0.9
        assert m.trust_score == 0.8
        assert m.retention == "until_forget"
        assert m.approval_state == "approved"
        assert m.pinned is False

    def test_list_can_filter_by_scope(self, service: DashboardService, workspace: Path) -> None:
        _seed_memory(service.store, workspace, scope="project:alpha")
        _seed_memory(service.store, workspace, text="other", scope="project:beta")
        assert {m.scope for m in service.list_memories()} == {
            "project:alpha",
            "project:beta",
        }
        assert {m.scope for m in service.list_memories(scope="project:alpha")} == {
            "project:alpha"
        }


class TestMemoryPin:
    def test_pin_round_trips_and_surfaces_in_list(
        self, service: DashboardService, workspace: Path
    ) -> None:
        mid = _seed_memory(service.store, workspace)
        assert service.set_memory_pinned(mid, True, OWNER).ok
        memories = service.list_memories()
        assert memories[0].pinned is True
        assert service.set_memory_pinned(mid, False, OWNER).ok
        assert service.list_memories()[0].pinned is False

    def test_ai_principal_cannot_pin(self, service: DashboardService, workspace: Path) -> None:
        from raiker.contracts.ids import utc_now

        with service.store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        mid = _seed_memory(service.store, workspace)
        result = service.set_memory_pinned(mid, True, "principal_ai")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"


class TestMemoryForget:
    def test_forget_removes_memory_from_list(self, service: DashboardService, workspace: Path) -> None:
        mid = _seed_memory(service.store, workspace)
        assert service.forget_memory_controlled(mid, OWNER).ok
        assert service.list_memories() == []

    def test_unknown_memory_fails_closed(self, service: DashboardService) -> None:
        result = service.forget_memory_controlled("mem_missing", OWNER)
        assert not result.ok
        assert result.reason_code == "unknown_memory:mem_missing"

    def test_ai_principal_cannot_forget(self, service: DashboardService, workspace: Path) -> None:
        from raiker.contracts.ids import utc_now

        with service.store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        mid = _seed_memory(service.store, workspace)
        result = service.forget_memory_controlled(mid, "principal_ai")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"

    def test_human_can_archive_and_restore(self, service: DashboardService, workspace: Path) -> None:
        mid = _seed_memory(service.store, workspace)
        assert service.set_memory_archived(mid, True, OWNER).ok
        assert service.list_memories() == []
        assert service.set_memory_archived(mid, False, OWNER).ok
        assert [m.memory_id for m in service.list_memories()] == [mid]


class TestMemoryEditAndSearchParticipation:
    def test_human_can_edit_a_memory_and_exclude_it_from_search(
        self, service: DashboardService, workspace: Path
    ) -> None:
        mid = _seed_memory(service.store, workspace, text="Use tabs.")

        edited = service.edit_memory_controlled(mid, "Use spaces.", OWNER)
        assert edited.ok
        stored = get_memory(mid, workspace_root=workspace)
        assert stored is not None
        assert stored.text == "Use spaces."

        assert service.set_memory_search_enabled(mid, False, OWNER).ok
        assert search_memory("spaces", workspace_root=workspace) == []

    def test_expiry_hides_memory_and_export_import_round_trips(
        self, service: DashboardService, workspace: Path
    ) -> None:
        mid = _seed_memory(service.store, workspace, text="Portable memory")
        assert service.set_memory_expiry(mid, "2000-01-01T00:00:00Z", OWNER).ok
        assert service.list_memories() == []
        assert service.set_memory_expiry(mid, None, OWNER).ok
        assert [m.text for m in service.list_memories()] == ["Portable memory"]
        assert service.set_memory_expiry(mid, "2000-01-01T00:00:00Z", OWNER).ok
        exported = service.export_memories(OWNER)
        assert exported.ok and exported.data["memories"] == []
        imported = service.import_memories(
            [{"text": "Imported memory", "scope": "project:proj_alpha"}], OWNER
        )
        assert imported.ok
        assert [m.text for m in service.list_memories()] == ["Imported memory"]


class TestIncognitoBoundary:
    def test_incognito_round_trips(self, service: DashboardService) -> None:
        assert service.get_memory_settings().incognito is False
        assert service.set_memory_incognito(True, OWNER).ok
        assert service.get_memory_settings().incognito is True
        assert service.set_memory_incognito(False, OWNER).ok
        assert service.get_memory_settings().incognito is False

    def test_incognito_withholds_project_memory_from_context(
        self, service: DashboardService, workspace: Path
    ) -> None:
        # Create a project, enable its memory, and seed an approved memory in
        # the project scope — so context gathering would normally include it.
        pid = service.create_project("Alpha", OWNER).data["project_id"]
        service.select_project(pid, OWNER)
        service.save_project_context(
            pid, instructions="Use tabs.", attachment_ids=[], memory_enabled=True,
            acting_principal_id=OWNER,
        )
        _seed_memory(service.store, workspace, scope=f"project:{pid}")
        service.store.create_session("sess_alpha", str(workspace))
        service.select_project(None, OWNER)

        gatherer = ContextGatherer()
        included = gatherer.gather(
            workspace_root=workspace, session_id="sess_alpha", turn_id="t", prompt_text="hi",
        ).included_items
        assert any(i.source.source_type == "project_context" for i in included)

        # Turn incognito on: the project context still appears (instructions are
        # not memory), but the approved project memory is withheld.
        service.set_memory_incognito(True, OWNER)
        included_incog = gatherer.gather(
            workspace_root=workspace, session_id="sess_alpha", turn_id="t2", prompt_text="hi",
        ).included_items
        proj_ctx = [i for i in included_incog if i.source.source_type == "project_context"]
        assert proj_ctx, "project context (instructions) should still be present"
        assert proj_ctx[0].metadata["memory_enabled"] is False, (
            "incognito must suppress memory_enabled so no memory is included"
        )


class TestMemoryApi:
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
        assert client.get("/api/memory").status_code == 401
        assert client.get("/api/memory/settings").status_code == 401

    def test_list_pin_forget_roundtrip(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        store = SQLiteStore(workspace)
        mid = _seed_memory(store, workspace)

        listing = client.get("/api/memory", headers=headers).json()
        assert len(listing) == 1
        assert listing[0]["memory_id"] == mid
        assert listing[0]["pinned"] is False

        pinned = client.put(f"/api/memory/{mid}/pin", json={"pinned": True}, headers=headers)
        assert pinned.status_code == 200, pinned.text
        assert client.get("/api/memory", headers=headers).json()[0]["pinned"] is True

        forgotten = client.delete(f"/api/memory/{mid}", headers=headers)
        assert forgotten.status_code == 200, forgotten.text
        assert client.get("/api/memory", headers=headers).json() == []

    def test_incognito_roundtrip(self, client: TestClient) -> None:
        headers = self._headers(client)
        assert client.get("/api/memory/settings", headers=headers).json()["incognito"] is False
        resp = client.put("/api/memory/incognito", json={"incognito": True}, headers=headers)
        assert resp.status_code == 200
        assert client.get("/api/memory/settings", headers=headers).json()["incognito"] is True

    def test_edit_and_search_participation_routes(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        mid = _seed_memory(SQLiteStore(workspace), workspace, text="Use tabs.")
        edited = client.put(f"/api/memory/{mid}", json={"text": "Use spaces."}, headers=headers)
        assert edited.status_code == 200, edited.text
        hidden = client.put(f"/api/memory/{mid}/search", json={"enabled": False}, headers=headers)
        assert hidden.status_code == 200, hidden.text
        listed = client.get("/api/memory", headers=headers).json()
        assert listed[0]["text"] == "Use spaces."
        assert listed[0]["search_enabled"] is False
        assert listed[0]["expires_at"] is None

    def test_expiry_export_and_import_routes(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        mid = _seed_memory(SQLiteStore(workspace), workspace, text="Portable memory")

        expired = client.put(
            f"/api/memory/{mid}/expiry",
            json={"expires_at": "2000-01-01T00:00:00Z"},
            headers=headers,
        )
        assert expired.status_code == 200, expired.text
        assert client.get("/api/memory", headers=headers).json() == []

        cleared = client.put(f"/api/memory/{mid}/expiry", json={"expires_at": None}, headers=headers)
        assert cleared.status_code == 200, cleared.text
        exported = client.get("/api/memory/export", headers=headers)
        assert exported.status_code == 200, exported.text
        assert exported.json()["memories"][0]["text"] == "Portable memory"

        imported = client.post(
            "/api/memory/import",
            json={"memories": [{"text": "Imported memory", "scope": "project:proj_alpha"}]},
            headers=headers,
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["count"] == 1
