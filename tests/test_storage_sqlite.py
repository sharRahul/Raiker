from __future__ import annotations

from pathlib import Path
from unittest import mock

from raiker.storage.sqlite import SQLiteStore


def test_sqlite_bootstrap_creates_required_tables(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    expected = {
        "migrations",
        "sessions",
        "turns",
        "tasks",
        "events_index",
        "tool_actions",
        "policy_decisions",
        "approvals",
        "memory_candidates",
        "connector_profiles",
        "model_profiles",
        "model_usage_ledger",
        "model_weekly_budgets",
        "provider_usage_snapshots",
        "checkpoints",
    }
    assert expected.issubset(store.table_names())
    assert (tmp_path / ".raiker" / "raiker.db").exists()

    with store.connect() as connection:
        usage_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(model_usage_ledger)").fetchall()
        }
    assert {"profile_id", "request_kind"}.issubset(usage_columns)


# ── GCR-10 ───────────────────────────────────────────────────────────────────


def test_a_workspace_is_bootstrapped_once_and_not_on_every_store(tmp_path: Path) -> None:
    """GCR-10 — an ordinary repository object was a schema lifecycle event.

    Handling one prompt builds stores for session ownership, project resolution,
    readiness, attachment references, generated files and the gateway. Each
    construction re-walked the whole migration catalogue and every backfill,
    under the process-global lock the others were waiting on.
    """
    from raiker.storage import sqlite as sqlite_module

    runs: list[Path] = []
    original = sqlite_module.SQLiteStore.bootstrap

    def counted(self: sqlite_module.SQLiteStore) -> None:
        runs.append(self.db_path)
        original(self)

    with mock.patch.object(sqlite_module.SQLiteStore, "bootstrap", counted):
        sqlite_module.SQLiteStore(tmp_path)
        assert len(runs) == 1
        for _ in range(10):
            sqlite_module.SQLiteStore(tmp_path)
        assert len(runs) == 1

        # A second workspace is a second schema, and gets its own.
        other = tmp_path / "other"
        other.mkdir()
        sqlite_module.SQLiteStore(other)
        assert len(runs) == 2


def test_the_cheap_path_still_adopts_rows_written_with_no_owner(tmp_path: Path) -> None:
    """Not everything `bootstrap()` does is schema, and skipping that part would
    change who a row belongs to.

    Three of its passes adopt rows written with no owner — a session started by
    the CLI is the one that made this visible — so they run on every store, and
    only the migration catalogue above them is skipped.
    """
    from raiker.storage import sqlite as sqlite_module

    adopted: list[int] = []
    original = sqlite_module.SQLiteStore.assign_legacy_data_to_original_owner

    def counted(self: sqlite_module.SQLiteStore) -> None:
        adopted.append(1)
        original(self)

    sqlite_module.SQLiteStore(tmp_path)
    with mock.patch.object(
        sqlite_module.SQLiteStore, "assign_legacy_data_to_original_owner", counted
    ):
        sqlite_module.SQLiteStore(tmp_path)
        sqlite_module.SQLiteStore(tmp_path)
    assert len(adopted) == 2


def test_a_workspace_handed_back_is_proved_again(tmp_path: Path) -> None:
    """Invalidation is what a shutdown, a key rotation and a live reset all do."""
    from raiker.storage import sqlite as sqlite_module

    runs: list[Path] = []
    original = sqlite_module.SQLiteStore.bootstrap

    def counted(self: sqlite_module.SQLiteStore) -> None:
        runs.append(self.db_path)
        original(self)

    with mock.patch.object(sqlite_module.SQLiteStore, "bootstrap", counted):
        store = sqlite_module.SQLiteStore(tmp_path)
        sqlite_module.invalidate_workspace_connections(tmp_path)
        sqlite_module.SQLiteStore(tmp_path)
        assert len(runs) == 2

        # And a database that is simply gone is never assumed present, however
        # recently this process bootstrapped one at that path.
        sqlite_module.close_cached_connections()
        store.db_path.unlink()
        sqlite_module.SQLiteStore(tmp_path)
        assert len(runs) == 3
