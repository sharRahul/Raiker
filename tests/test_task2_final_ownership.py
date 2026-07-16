from __future__ import annotations

from pathlib import Path

from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    forget_memory,
    write_memory,
)
from raiker.storage.sqlite import SQLiteStore


def _governance(owner: str) -> MemoryGovernance:
    return MemoryGovernance("evt", "session", None, "test", 1.0, 1.0, "until_forget", "approved", owner)


def test_owner_reconcile_only_touches_its_projection_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    first = write_memory("first", workspace_root=tmp_path, store=store, governance=_governance("a"), owner_principal_id="a")
    second = write_memory("second", workspace_root=tmp_path, store=store, governance=_governance("b"), owner_principal_id="b")
    store.link_memory_projection(first.memory_id, "vector", "vec_a", "test", owner_principal_id="a")
    store.link_memory_projection(second.memory_id, "vector", "vec_b", "test", owner_principal_id="b")
    with store.connect() as connection:
        connection.execute("UPDATE memory_projections SET active = 0 WHERE memory_id = ?", (second.memory_id,))

    store.reconcile_memory_projections(owner_principal_id="a")

    assert store.list_memory_projections(second.memory_id)[0]["active"] == 0


def test_forget_tombstone_keeps_owner_metadata(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    entry = write_memory("owned", workspace_root=tmp_path, store=store, governance=_governance("a"), owner_principal_id="a")
    assert forget_memory(
        entry.memory_id, workspace_root=tmp_path, store=store, owner_principal_id="a",
        governance=MemoryForgetGovernance("evt", "session", None, "test", "a"),
    )
    assert '"owner_principal_id": "a"' in (tmp_path / ".raiker" / "memory" / f"{entry.memory_id}.md").read_text()


def test_purge_account_leaves_no_plaintext_in_fts_or_on_disk(tmp_path: Path) -> None:
    """Purging an account must not strand its memory text anywhere.

    ``approved_memory_fts`` is keyed only by ``memory_id`` — it has no owner
    column — so an owner-keyed delete sweep never matches it, and the durable
    ``.raiker/memory/<id>.md`` export is not a database row at all. Both keep
    full plaintext after the owning row is gone.
    """
    store = SQLiteStore(tmp_path)
    entry = write_memory(
        "PURGE ME SECRET ROADMAP", workspace_root=tmp_path, store=store,
        governance=_governance("principal_purge"), owner_principal_id="principal_purge",
    )
    keeper = write_memory(
        "KEEP ME", workspace_root=tmp_path, store=store,
        governance=_governance("principal_keep"), owner_principal_id="principal_keep",
    )
    markdown = tmp_path / ".raiker" / "memory" / f"{entry.memory_id}.md"
    assert markdown.exists()

    store.purge_account("principal_purge")

    with store.connect() as connection:
        fts = connection.execute(
            "SELECT text FROM approved_memory_fts WHERE memory_id = ?", (entry.memory_id,)
        ).fetchall()
        rows = connection.execute(
            "SELECT 1 FROM approved_memory WHERE memory_id = ?", (entry.memory_id,)
        ).fetchall()
    assert rows == []
    assert fts == [], "purged memory still searchable in FTS"
    assert not markdown.exists(), "purged memory still on disk as plaintext"
    # The other owner is untouched.
    keeper_markdown = tmp_path / ".raiker" / "memory" / f"{keeper.memory_id}.md"
    assert keeper_markdown.exists()
    with store.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM approved_memory WHERE memory_id = ?", (keeper.memory_id,)
        ).fetchone() is not None
