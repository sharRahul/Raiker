"""A fresh workspace is a re-keyed copy of a schema template, not a 208-step replay."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.storage.migrations import SCHEMA_GENERATION
from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections
from raiker.storage.stores import migration_runner


def _schema(store: SQLiteStore) -> list[tuple[str, str, str]]:
    with store.connect() as connection:
        return sorted(tuple(row) for row in connection.execute("SELECT type, name, sql FROM sqlite_master"))


@pytest.fixture(autouse=True)
def fresh_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(migration_runner, "_TEMPLATE", {})
    monkeypatch.delenv("RAIKER_SCHEMA_TEMPLATE", raising=False)


def test_the_second_fresh_workspace_is_seeded_with_the_same_schema_and_its_own_key(tmp_path: Path) -> None:
    first = SQLiteStore(tmp_path / "a")
    assert len(migration_runner._TEMPLATE) == 1
    template_path, template_key = next(iter(migration_runner._TEMPLATE.values()))
    # Data written after the build never reaches the template.
    with first.connect() as connection:
        connection.execute("UPDATE memory_vector_search_state SET revision = 99")
    second = SQLiteStore(tmp_path / "b")
    assert _schema(second) == _schema(first)
    with second.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_GENERATION
        assert connection.execute("SELECT revision FROM memory_vector_search_state").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM migrations").fetchone()[0] > 200
    # The copy is under the workspace's own key: the template key does not open it.
    probe = sqlite3.connect(str(second.db_path))
    probe.execute(f"PRAGMA key = \"x'{template_key}'\"")
    with pytest.raises(sqlite3.DatabaseError):
        probe.execute("SELECT count(*) FROM sqlite_master").fetchone()
    probe.close()
    assert template_path.is_file() and template_path.parent != second.db_path.parent


def test_an_existing_database_is_never_replaced(tmp_path: Path) -> None:
    SQLiteStore(tmp_path / "a")
    existing = SQLiteStore(tmp_path / "b")
    with existing.connect() as connection:
        connection.execute("UPDATE memory_vector_search_state SET revision = 7")
    invalidate_workspace_connections(existing.paths.workspace_root)
    reopened = SQLiteStore(tmp_path / "b")
    with reopened.connect() as connection:
        assert connection.execute("SELECT revision FROM memory_vector_search_state").fetchone()[0] == 7


def test_the_template_can_be_switched_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_SCHEMA_TEMPLATE", "off")
    SQLiteStore(tmp_path / "a")
    assert migration_runner._TEMPLATE == {}
    assert _schema(SQLiteStore(tmp_path / "b"))


def test_a_template_is_only_used_by_a_build_with_the_same_search_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    SQLiteStore(tmp_path / "a")
    built_with = next(iter(migration_runner._TEMPLATE))
    other = "fts4" if built_with == "fts5" else "fts5"
    monkeypatch.setattr(SQLiteStore, "_text_search_engine", other)
    store = SQLiteStore(tmp_path / "b")
    assert store.resolved_text_search_engine() == other
    assert set(migration_runner._TEMPLATE) == {built_with, other}
