"""DEC-24 step 6 — a damaged text index is a rebuildable degraded state.

The memory integrity report measured drift (an index whose row count disagrees
with the table it projects) and nothing measured damage: an index SQLite itself
reports as corrupt, which fails every search through it. These hold that the
report names damage, that a rebuild repairs it from the rows that own the text,
and that the rows themselves are never touched.
"""

from __future__ import annotations

from pathlib import Path

from raiker.memory.integrity import inspect_memory_integrity
from raiker.storage.sqlite import SQLiteStore


def _damage_conversation_index(store: SQLiteStore) -> None:
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO conversation_fts (turn_id, session_id, role, text) "
            "VALUES ('turn_1', 'sess_1', 'user', 'hello damaged index')"
        )
    # Separately committed, so the segment written above is on disk to lose.
    with store.connect() as connection:
        connection.execute("DELETE FROM conversation_fts_data WHERE id NOT IN (1, 10)")


def test_a_healthy_workspace_has_no_damaged_index(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert store.damaged_text_indexes() == []
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.damaged_text_indexes == ()
    assert report.clean


def test_damage_is_named_and_makes_the_report_unclean(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _damage_conversation_index(store)

    assert store.damaged_text_indexes() == ["conversation_fts"]
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.damaged_text_indexes == ("conversation_fts",)
    assert not report.clean


def test_rebuild_recomputes_every_index_from_its_source_rows(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _damage_conversation_index(store)

    counts = store.rebuild_text_indexes()

    assert set(counts) == set(SQLiteStore.TEXT_INDEX_TABLES)
    assert store.damaged_text_indexes() == []
    with store.connect() as connection:
        # The stray row was in the index only, never in `turns`, so a rebuild
        # from the table that owns the text does not bring it back.
        assert connection.execute("SELECT COUNT(*) FROM conversation_fts").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM conversation_fts WHERE conversation_fts MATCH 'hello'"
        ).fetchone()[0] == 0
