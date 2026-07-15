"""Conversation organisation remainder: nested projects/folders tests.

Nested projects/folders are organizing scopes — they grant nothing and change no
gate, policy, or authority. Like the existing `projects` table, folders can
contain other folders or sessions. Arbitrary depth via parent_id + materialized
path. Two deletion modes: archive (AI autonomous, soft) and delete (human-only,
hard with orphanage cascade).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
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
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


class TestProjectNestingMigration:
    def test_migration_creates_nesting_columns_and_trigger(self, store: SQLiteStore) -> None:
        cols = {row["name"] for row in store.connect().execute("PRAGMA table_info(projects)").fetchall()}
        assert "parent_id" in cols
        assert "path" in cols
        assert "is_archived" in cols
        assert "archived_at" in cols
        # Trigger removed; path management handled in Python for reliability

    def test_defaults_for_existing_projects(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        row = store.load_project("p1")
        assert row is not None
        assert row["parent_id"] is None
        assert row["path"] == "/p1/"
        assert row["is_archived"] == 0
        assert row["archived_at"] is None

    def test_backfill_repairs_legacy_paths_from_parent_links(self, workspace: Path, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        with store.connect() as connection:
            connection.execute("UPDATE projects SET path = '/' WHERE project_id = 'p2'")
            connection.execute(
                "DELETE FROM migrations WHERE migration_id = 'RAIKER-1014-project-self-inclusive-path'"
            )

        repaired = SQLiteStore(workspace).load_project("p2")
        assert repaired is not None
        assert repaired["path"] == "/p1/p2/"


class TestProjectTreeQueries:
    def test_list_project_tree_returns_nested_structure(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.create_project("p3", "Grandchild", "projects/root/child/gc", parent_id="p2")

        tree = store.list_project_tree()
        assert len(tree) == 1
        assert tree[0]["project_id"] == "p1"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["project_id"] == "p2"
        assert len(tree[0]["children"][0]["children"]) == 1
        assert tree[0]["children"][0]["children"][0]["project_id"] == "p3"

    def test_list_project_tree_excludes_archived_by_default(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.archive_project("p1")  # archives subtree

        tree = store.list_project_tree()
        assert tree == []

    def test_list_project_tree_include_archived(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.archive_project("p1")

        tree = store.list_project_tree(include_archived=True)
        assert len(tree) == 1
        assert tree[0]["is_archived"] == 1


class TestProjectMove:
    def test_move_project_updates_path_and_descendants(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.move_project("p2", None)  # move to root

        child = store.load_project("p2")
        assert child is not None
        assert child["parent_id"] is None
        assert child["path"] == "/p2/"

    def test_move_project_does_not_move_siblings(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "First", "projects/root/first", parent_id="p1")
        store.create_project("p3", "Second", "projects/root/second", parent_id="p1")

        assert store.move_project("p2", "p3")
        assert store.load_project("p2")["path"] == "/p1/p3/p2/"
        assert store.load_project("p3")["path"] == "/p1/p3/"

    def test_move_prevents_cycle(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        assert not store.move_project("p1", "p2")  # would create cycle
        parent = store.load_project("p1")
        assert parent is not None
        assert parent["parent_id"] is None


class TestProjectArchive:
    def test_archive_project_archives_subtree(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.archive_project("p1")
        p1 = store.load_project("p1")
        assert p1 is not None and p1["is_archived"] == 1
        p2 = store.load_project("p2")
        assert p2 is not None and p2["is_archived"] == 1

    def test_archive_is_idempotent(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.archive_project("p1")
        store.archive_project("p1")  # second call no-op
        p1 = store.load_project("p1")
        assert p1 is not None and p1["is_archived"] == 1

    def test_archive_project_does_not_archive_siblings(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "First", "projects/root/first", parent_id="p1")
        store.create_project("p3", "Second", "projects/root/second", parent_id="p1")

        assert store.archive_project("p2")
        assert store.load_project("p2")["is_archived"] == 1
        assert store.load_project("p3")["is_archived"] == 0


class TestProjectDeleteWithOrphanage:
    def test_delete_project_orphans_children_and_hard_deletes_target(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.delete_project_with_orphanage("p1")
        assert store.load_project("p1") is None
        child = store.load_project("p2")
        assert child is not None
        assert child["parent_id"] is None
        assert child["path"].startswith("/orphaned/")
        assert child["is_archived"] == 1


class TestAncestorContexts:
    def test_get_ancestor_contexts_returns_active_ancestors(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.save_project_context("p1", instructions="Root inst", attachment_ids=[], memory_enabled=True)
        store.save_project_context("p2", instructions="Child inst", attachment_ids=[], memory_enabled=False)

        contexts = store.get_ancestor_contexts("p2")
        assert len(contexts) == 1  # Only ancestors, not self
        assert contexts[0]["instructions"] == "Root inst"

    def test_memory_mode_inherits_nearest_explicit_ancestor(self, store: SQLiteStore) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        store.create_project("p3", "Leaf", "projects/root/child/leaf", parent_id="p2")
        store.save_project_context("p1", instructions="", attachment_ids=[], memory_mode="enabled")
        store.save_project_context("p2", instructions="", attachment_ids=[], memory_mode="inherit")
        store.save_project_context("p3", instructions="", attachment_ids=[], memory_mode="disabled")

        assert store.load_effective_project_context("p2")["memory_enabled"] is True
        assert store.load_effective_project_context("p3")["memory_enabled"] is False


class TestDashboardServiceNested:
    def test_list_project_tree_active_only(self, service: DashboardService, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        r = service.archive_project("p1", OWNER)
        assert r.ok, r.reason_code
        tree = service.list_project_tree()
        assert tree == []

    def test_archive_is_ai_autonomous(self, service: DashboardService, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        from raiker.contracts.ids import utc_now
        with service.store.connect() as conn:
            conn.execute("""INSERT OR IGNORE INTO principals (principal_id, principal_type, display_name, role_ids, domain_scopes, max_runtime_mode, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("ai_principal", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1))
        result = service.archive_project("p1", "ai_principal")
        assert result.ok, result.reason_code
        p1 = store.load_project("p1")
        assert p1 is not None and p1["is_archived"] == 1

    def test_move_project_human_only(self, service: DashboardService, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        from raiker.contracts.ids import utc_now
        with service.store.connect() as conn:
            conn.execute("""INSERT OR IGNORE INTO principals (principal_id, principal_type, display_name, role_ids, domain_scopes, max_runtime_mode, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("ai_principal", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1))
        result = service.move_project("p2", None, "ai_principal")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"

    def test_delete_project_requires_confirm(self, service: DashboardService, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        result = service.delete_project("p1", OWNER)
        assert not result.ok
        assert result.reason_code == "project_delete_confirmation_required"
        # With confirm=True, succeeds and orphans children
        result = service.delete_project("p1", OWNER, confirm=True)
        assert result.ok, result.reason_code
        assert store.load_project("p1") is None
        child = store.load_project("p2")
        assert child is not None
        assert child["parent_id"] is None
        assert child["is_archived"] == 1

    def test_get_session_context_merges_ancestor_contexts(self, service: DashboardService, store: SQLiteStore, workspace: Path) -> None:
        store.create_project("p1", "Root", "projects/root")
        store.create_project("p2", "Child", "projects/root/child", parent_id="p1")
        r = service.save_project_context("p1", instructions="Root instructions", attachment_ids=[], memory_enabled=True, acting_principal_id=OWNER)
        assert r.ok, r.reason_code
        r = service.save_project_context("p2", instructions="Child instructions", attachment_ids=[], memory_enabled=False, acting_principal_id=OWNER)
        assert r.ok, r.reason_code
        r = service.select_project("p2", OWNER)
        assert r.ok, r.reason_code
        store.create_session("sess1", str(workspace))
        context = service.get_session_context("sess1")
        assert "Root instructions" in context["instructions"]
        assert "Child instructions" in context["instructions"]
        assert context["memory_enabled"] is False
