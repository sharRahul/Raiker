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
