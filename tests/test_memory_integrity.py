from pathlib import Path

from raiker.memory.integrity import inspect_memory_integrity
from raiker.memory.store import MemoryGovernance, set_memory_archived, write_memory
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
