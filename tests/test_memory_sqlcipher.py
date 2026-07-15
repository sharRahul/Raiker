import sqlite3
from pathlib import Path

import pytest

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore


def test_memory_database_uses_sqlcipher_not_plain_sqlite(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    write_memory(
        "Encrypted durable memory.", workspace_root=tmp_path, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    assert not store.db_path.read_bytes().startswith(b"SQLite format 3")
    with store.connect() as encrypted:
        assert encrypted.execute("SELECT sql FROM sqlite_master WHERE name = 'approved_memory_fts'").fetchone()[0].lower().find("fts4") >= 0
    with sqlite3.connect(store.db_path) as plaintext, pytest.raises(sqlite3.DatabaseError):
        plaintext.execute("SELECT * FROM approved_memory").fetchall()


def test_plaintext_database_is_converted_without_leaving_plaintext_backup(tmp_path: Path) -> None:
    db_path = tmp_path / ".raiker" / "raiker.db"
    db_path.parent.mkdir()
    with sqlite3.connect(db_path) as plaintext:
        plaintext.execute("CREATE TABLE legacy_note (value TEXT)")
        plaintext.execute("INSERT INTO legacy_note VALUES ('preserved')")
    store = SQLiteStore(tmp_path)
    with store.connect() as encrypted:
        assert encrypted.execute("SELECT value FROM legacy_note").fetchone()[0] == "preserved"
    assert not db_path.with_suffix(".plaintext-backup").exists()
