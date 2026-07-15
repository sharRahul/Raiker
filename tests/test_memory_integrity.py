from pathlib import Path

from raiker.memory.integrity import inspect_memory_integrity
from raiker.memory.store import MemoryGovernance, set_memory_archived, update_memory, write_memory
from raiker.storage.sqlite import SQLiteStore


def test_integrity_reports_stale_projection_and_archive_removes_it(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Integrity fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    store.link_memory_projection(memory.memory_id, "vector", "vec_integrity", "v1")
    assert inspect_memory_integrity(store=store, workspace_root=tmp_path).clean
    with store.connect() as connection:
        connection.execute("UPDATE approved_memory SET archived_at = '2000-01-01T00:00:00Z' WHERE memory_id = ?", (memory.memory_id,))
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.stale_projection_count == 1
    set_memory_archived(memory.memory_id, archived=True, workspace_root=tmp_path, store=store)
    assert inspect_memory_integrity(store=store, workspace_root=tmp_path).clean


def test_reconciliation_never_reactivates_temporally_ineligible_projections(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Future fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    store.link_memory_projection(memory.memory_id, "vector", "vec_future", "v1")
    with store.connect() as connection:
        connection.execute(
            "UPDATE approved_memory SET valid_from = ? WHERE memory_id = ?", ("2100-01-01T00:00:00Z", memory.memory_id)
        )
    store.reconcile_memory_projections()
    assert inspect_memory_integrity(store=store, workspace_root=tmp_path).clean
    assert store.list_memory_projections(memory.memory_id)[0]["active"] == 0


def test_new_projection_is_inactive_when_its_source_is_not_yet_valid(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Future fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE approved_memory SET valid_from = ? WHERE memory_id = ?", ("2100-01-01T00:00:00Z", memory.memory_id)
        )
    store.link_memory_projection(memory.memory_id, "vector", "vec_future_new", "v1")
    assert store.list_memory_projections(memory.memory_id)[0]["active"] == 0


def test_memory_edit_immediately_deactivates_ineligible_projections(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Searchable fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    store.link_memory_projection(memory.memory_id, "vector", "vec_searchable", "v1")
    update_memory(memory.memory_id, workspace_root=tmp_path, store=store, search_enabled=False)
    assert store.list_memory_projections(memory.memory_id)[0]["active"] == 0


def test_durable_memory_persists_a_content_checksum(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Checksummed fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    with store.connect() as connection:
        row = connection.execute(
            "SELECT content_checksum FROM approved_memory WHERE memory_id = ?", (memory.memory_id,)
        ).fetchone()
    assert row["content_checksum"] == "1d85c37471356f4373bd42b5f5ffaa6c27ee7b64ae946c005593359e907709e5"


def test_integrity_reports_durable_memory_checksum_mismatch(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory = write_memory(
        "Checksummed fact.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    with store.connect() as connection:
        connection.execute("UPDATE approved_memory SET text = ? WHERE memory_id = ?", ("Tampered.", memory.memory_id))
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.checksum_mismatch_count == 1
    assert not report.clean


def test_integrity_reports_orphaned_artifacts_and_failed_purge_locations(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_dir = tmp_path / ".raiker" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "mem_orphan.md").write_text("orphan", encoding="utf-8")
    store.create_memory_purge_record(
        "pur_test", "mem_removed", "owner", "2026-01-01T00:00:00Z",
        {"failed_storage_locations": ["artifact_store"]},
    )
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.orphaned_markdown_count == 1
    assert report.failed_purge_location_count == 1
    assert not report.clean


def test_integrity_reports_project_parent_path_inconsistency(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_project("proj_root", "Root", "projects/root")
    store.create_project("proj_child", "Child", "projects/child", parent_id="proj_root")
    with store.connect() as connection:
        connection.execute("UPDATE projects SET path = ? WHERE project_id = ?", ("/wrong/", "proj_child"))
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.project_path_inconsistency_count == 1
    assert not report.clean
