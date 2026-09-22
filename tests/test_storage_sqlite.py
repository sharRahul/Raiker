from __future__ import annotations

from pathlib import Path

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


def test_the_migrations_table_is_read_once_per_pass_not_once_per_migration(
    tmp_path: Path,
) -> None:
    """GCR-10 — a couple of hundred round trips to answer one question.

    ``bootstrap()`` runs on every ``SQLiteStore`` construction, and the
    architecture builds stores freely: handling one prompt constructs them for
    session ownership, project resolution, readiness, attachment references,
    generated files and the gateway. Each construction asked the ``migrations``
    table once *per migration*, while holding the process-global bootstrap lock
    the others were waiting on.
    """
    store = SQLiteStore(tmp_path)  # the first pass applies the catalogue

    # The connection cache is keyed by workspace and thread, so the next store
    # built here bootstraps over this very connection. SQLite's own trace
    # callback is the only way to watch it: `sqlite3.Connection.execute` is an
    # immutable attribute and cannot be patched.
    asked: list[str] = []
    connection = store.connect()
    connection.set_trace_callback(lambda sql: asked.append(sql))
    try:
        SQLiteStore(tmp_path)
    finally:
        connection.set_trace_callback(None)

    reads = [sql for sql in asked if "FROM migrations" in sql]
    whole_table = [sql for sql in reads if "WHERE migration_id" not in sql]
    per_migration = [sql for sql in reads if "WHERE migration_id" in sql]
    # One read of the whole table. The handful of backfills that guard
    # themselves on their own marker still ask by id, which is why this is a
    # ceiling rather than an equality — it was a hundred and sixty-odd before.
    assert len(whole_table) == 1, whole_table
    assert len(per_migration) < 10, len(per_migration)


def test_the_pass_still_repairs_a_database_that_has_drifted(tmp_path: Path) -> None:
    """The half GCR-10 must not cost: `bootstrap()` is also the self-repair.

    Caching "this workspace is fine" across constructions would be a much
    shorter route to the same schema *only* while nothing else touches the
    file. A marker somebody deleted, an index an older release left behind and
    a legacy path all get put right by the next store, and that is a contract
    the suite states in six places.
    """
    from raiker.storage.migrations import COMMAND_RUNS_MIGRATION_ID

    store = SQLiteStore(tmp_path)
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?", (COMMAND_RUNS_MIGRATION_ID,)
        )

    SQLiteStore(tmp_path)

    with store.connect() as connection:
        restored = connection.execute(
            "SELECT 1 FROM migrations WHERE migration_id = ?", (COMMAND_RUNS_MIGRATION_ID,)
        ).fetchone()
    assert restored is not None


def test_the_snapshot_does_not_outlive_the_pass_that_took_it(tmp_path: Path) -> None:
    """Outside a pass the answer comes from the table, as it always did."""
    store = SQLiteStore(tmp_path)
    assert store._applied is None  # noqa: SLF001 — the point of the test
