"""RAIKER-2025 — the text indexes are FTS5, and ranking is relevance.

Two claims are under test, and they are different claims. The first is
structural: both rebuildable projections are created on FTS5 where the build has
it, and a workspace that was created on FTS4 is converted in place without
losing a row. The second is behavioural, and is the reason the first one
matters: MEM-05 said the oldest exact answer was the first result dropped,
because ordering by `created_at DESC` is the only deterministic order available
without a relevance score. With BM25 there is one.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.migrations import TEXT_SEARCH_FTS5_MIGRATION_ID
from raiker.storage.sqlite import SQLiteStore


def _governance() -> MemoryGovernance:
    return MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test")


def _write(store: SQLiteStore, root: Path, text: str, scope: str = "project:alpha") -> str:
    return write_memory(
        text, workspace_root=root, store=store, governance=_governance(), scope=scope
    ).memory_id


def test_both_text_indexes_are_built_on_the_probed_engine(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    engine = store.resolved_text_search_engine()
    assert engine == "fts5", "the shipped SQLite/SQLCipher builds are expected to provide FTS5"
    with store.connect() as connection:
        for table in ("approved_memory_fts", "conversation_fts"):
            ddl = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
            ).fetchone()[0]
            assert f"using {engine}" in ddl.lower(), table
        assert connection.execute(
            "SELECT 1 FROM migrations WHERE migration_id = ?", (TEXT_SEARCH_FTS5_MIGRATION_ID,)
        ).fetchone() is not None


def test_a_workspace_left_on_fts4_is_converted_in_place_and_keeps_its_rows(
    tmp_path: Path,
) -> None:
    """The upgrade path, driven from a real FTS4 index rather than a fresh one.

    The index is a projection, so the test's evidence is not that the rows
    survived the DDL — they are recomputed, not copied — but that the same
    search answers the same way afterwards.
    """
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "The encrypted NAS target is the backup destination.")
    assert [row["memory_id"] for row in store.search_approved_memory("encrypted")] == [memory_id]

    # Put the workspace back on FTS4, exactly as a pre-RAIKER-2025 one was.
    with store.connect() as connection:
        connection.execute("DROP TABLE approved_memory_fts")
        connection.execute(
            "CREATE VIRTUAL TABLE approved_memory_fts USING fts4(memory_id UNINDEXED, text, tags)"
        )
        SQLiteStore._rebuild_memory_fts(connection)
        connection.execute(
            "DELETE FROM migrations WHERE migration_id = ?", (TEXT_SEARCH_FTS5_MIGRATION_ID,)
        )
        assert SQLiteStore._index_engine(connection, "approved_memory_fts") == "fts4"

    reopened = SQLiteStore(tmp_path)
    with reopened.connect() as connection:
        assert SQLiteStore._index_engine(connection, "approved_memory_fts") == "fts5"
    assert [row["memory_id"] for row in reopened.search_approved_memory("encrypted")] == [memory_id]


def test_the_oldest_exact_answer_outranks_newer_partial_ones(tmp_path: Path) -> None:
    """MEM-05, stated as the failure it was.

    The best match is the oldest row and every newer row mentions the query term
    once. Under recency ordering the answer is behind all of them and a limit of
    two discards it; under BM25 it is first.
    """
    store = SQLiteStore(tmp_path)
    best = _write(
        store,
        tmp_path,
        "Rotation: rotation of the SQLCipher key is quarterly, and rotation is logged.",
    )
    newer = [
        _write(store, tmp_path, f"Unrelated note {index} mentioning rotation once.")
        for index in range(5)
    ]
    with store.connect() as connection:
        # Make the good answer unambiguously the *oldest* row, so recency
        # ordering would put it last.
        connection.execute(
            "UPDATE approved_memory SET created_at = '2023-01-01T00:00:00Z' WHERE memory_id = ?",
            (best,),
        )
        for index, memory_id in enumerate(newer):
            connection.execute(
                "UPDATE approved_memory SET created_at = ? WHERE memory_id = ?",
                (f"2026-08-0{index + 1}T00:00:00Z", memory_id),
            )

    ranked = [row["memory_id"] for row in store.search_approved_memory("rotation", limit=2)]
    assert ranked[0] == best, "the exact answer must rank first, not be dropped by the limit"


def test_conversation_search_returns_a_marked_snippet_and_ranks_by_relevance(
    tmp_path: Path,
) -> None:
    """`snippet()` takes its arguments in a different order on each engine.

    Getting that wrong does not raise on FTS4 — it silently returns NULL — so
    the assertion is on the snippet's *content*, not merely on its presence.
    """
    store = SQLiteStore(tmp_path)
    store.create_session("sess_1", str(tmp_path), title="Deployments")
    for index, (turn_id, text) in enumerate(
        (
            ("turn_weak", "A passing mention of deployment in a longer sentence."),
            ("turn_strong", "Deployment, deployment and deployment again."),
        )
    ):
        store.insert_turn("sess_1", turn_id, text)
        store.complete_turn(turn_id, "completed", f"Answer {index}.")

    hits = store.search_conversation_turns("deployment", limit=5)
    assert hits, "the index must answer a query the transcript plainly contains"
    assert hits[0]["turn_id"] == "turn_strong"
    assert "deployment" in str(hits[0]["snippet"]).lower()


def test_operator_shaped_prose_is_read_as_words_not_as_syntax(tmp_path: Path) -> None:
    """A prompt is prose. Neither grammar may read part of it as an operator.

    `NOT` and `NEAR` are keywords in both FTS4 and FTS5, so a query the owner
    typed as English would either raise or silently invert. The memory below
    contains both words, so a query containing them must *match* it — which it
    cannot do if either one was parsed as syntax.
    """
    store = SQLiteStore(tmp_path)
    memory_id = _write(
        store, tmp_path, "The deployment runbook is not stored near the ops repository."
    )
    for query in ("NOT deployment", "deployment NEAR runbook", "not near deployment"):
        found = [row["memory_id"] for row in store.search_approved_memory(query)]
        assert found == [memory_id], query


@pytest.mark.parametrize("query", ("a (b", 'quote"', "*", "  "))
def test_a_query_with_no_indexable_term_answers_empty_rather_than_raising(
    tmp_path: Path, query: str
) -> None:
    store = SQLiteStore(tmp_path)
    _write(store, tmp_path, "The deployment runbook lives in the ops repository.")
    assert store.search_approved_memory(query) == []
