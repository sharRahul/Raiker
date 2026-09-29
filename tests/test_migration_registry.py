"""OPT-07 — the migration order is data, and CI holds it still.

Bootstrap used to wire every migration by hand: an import for its id, an import
for its SQL and a call, in an order only reading the whole method revealed. The
order is now :data:`MIGRATIONS`, and these tests are what stop an entry being
moved — which would change what an existing database's upgrade does — or a new
step naming a runner method that is not there.
"""

from __future__ import annotations

from pathlib import Path

from raiker.storage.migrations import (
    MIGRATIONS,
    PHASE_1_MIGRATION_ID,
    Migration,
    RunnerStep,
    SearchMigration,
)
from raiker.storage.sqlite import SQLiteStore


def _recorded_ids() -> list[str]:
    return [step.id for step in MIGRATIONS if isinstance(step, (Migration, SearchMigration))]


def test_every_recorded_migration_id_is_unique() -> None:
    ids = _recorded_ids()
    assert len(ids) == len(set(ids))
    assert PHASE_1_MIGRATION_ID not in ids  # applied by bootstrap before the registry


def test_every_runner_step_names_a_method_the_store_has() -> None:
    missing = [
        step.method
        for step in MIGRATIONS
        if isinstance(step, RunnerStep) and not callable(getattr(SQLiteStore, step.method, None))
    ]
    assert missing == []


def test_a_fresh_database_applies_the_registry_in_its_declared_order(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.bootstrap()
    with store.connect() as connection:
        applied = [
            str(row[0])
            for row in connection.execute("SELECT migration_id FROM migrations ORDER BY rowid")
        ]
    assert applied[0] == PHASE_1_MIGRATION_ID
    position = {migration_id: index for index, migration_id in enumerate(applied)}
    declared = _recorded_ids()
    assert [migration_id for migration_id in declared if migration_id not in position] == []
    # Runner steps record ids of their own between these, so the registry is a
    # subsequence of what was applied — in exactly this order.
    assert [position[migration_id] for migration_id in declared] == sorted(
        position[migration_id] for migration_id in declared
    )


def test_a_second_bootstrap_applies_nothing(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.bootstrap()
    with store.connect() as connection:
        before = connection.execute("SELECT COUNT(*) FROM migrations").fetchone()[0]
    store.bootstrap()
    with store.connect() as connection:
        after = connection.execute("SELECT COUNT(*) FROM migrations").fetchone()[0]
    assert before == after
