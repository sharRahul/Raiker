from __future__ import annotations

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
        "checkpoints",
    }
    assert expected.issubset(store.table_names())
    assert (tmp_path / ".raiker" / "raiker.db").exists()
