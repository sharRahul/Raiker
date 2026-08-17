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

from raiker.memory.integrity import inspect_memory_integrity
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.migrations import TEXT_SEARCH_FTS5_MIGRATION_ID
from raiker.storage.sqlite import SQLiteStore, store_health


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


def test_a_build_without_fts5_keeps_fts4_and_still_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback branch, exercised rather than assumed.

    A build without FTS5 is the case the probe exists for, and it is the case
    no CI runner has — every platform Raiker targets ships FTS5, so without
    forcing it this path would be dead code that only fails on someone else's
    machine. The `snippet()` assertion is the point: FTS4 numbers the column
    *after* the markers, and the wrong order returns NULL for every row rather
    than raising, so a non-empty snippet is what proves the order is right.
    """
    monkeypatch.setattr(SQLiteStore, "_text_search_engine", "fts4")
    store = SQLiteStore(tmp_path)
    assert store.resolved_text_search_engine() == "fts4"

    memory_id = _write(store, tmp_path, "The deployment runbook lives in the ops repository.")
    assert [row["memory_id"] for row in store.search_approved_memory("deployment")] == [memory_id]

    store.create_session("sess_fts4", str(tmp_path), title="Deploys")
    store.insert_turn("sess_fts4", "turn_fts4", "How do we handle deployment?")
    store.complete_turn("turn_fts4", "completed", "Read the runbook.")
    hits = store.search_conversation_turns("deployment")
    assert [hit["turn_id"] for hit in hits] == ["turn_fts4"]
    assert "deployment" in str(hits[0]["snippet"]).lower()

    with store.connect() as connection:
        for table in ("approved_memory_fts", "conversation_fts"):
            assert SQLiteStore._index_engine(connection, table) == "fts4", table


def test_a_workspace_written_by_an_fts5_less_release_upgrades_without_losing_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The upgrade an owner will actually perform, rehearsed end to end.

    `sqlcipher3-wheels` gained FTS5 at 0.5.6; 0.5.2 and 0.5.4 have none. So a
    workspace created by an earlier Raiker release genuinely holds FTS4 indexes,
    and the question that matters is not whether the DDL converts but whether
    the owner loses anything: every memory still findable, the best match still
    first, the conversation snippet still marked, integrity still clean, and
    health saying which engine answered.
    """
    monkeypatch.setattr(SQLiteStore, "_text_search_engine", "fts4")
    older = SQLiteStore(tmp_path)
    memory_ids = [
        _write(older, tmp_path, text)
        for text in (
            "Rotation: rotation of the key is quarterly, and rotation is logged.",
            "A note mentioning rotation once.",
            "Backups go to the encrypted NAS target.",
        )
    ]
    older.create_session("sess_upgrade", str(tmp_path), title="Ops")
    older.insert_turn("sess_upgrade", "turn_upgrade", "How often is rotation done?")
    older.complete_turn("turn_upgrade", "completed", "Quarterly, and it is logged.")
    with older.connect() as connection:
        for table in ("approved_memory_fts", "conversation_fts"):
            assert SQLiteStore._index_engine(connection, table) == "fts4", table

    # The same files, opened by a build that has FTS5.
    monkeypatch.setattr(SQLiteStore, "_text_search_engine", None)
    upgraded = SQLiteStore(tmp_path)
    with upgraded.connect() as connection:
        for table in ("approved_memory_fts", "conversation_fts"):
            assert SQLiteStore._index_engine(connection, table) == "fts5", table

    ranked = [row["memory_id"] for row in upgraded.search_approved_memory("rotation")]
    assert set(ranked) == {memory_ids[0], memory_ids[1]}, "no memory may be lost"
    assert ranked[0] == memory_ids[0], "and the best match now ranks first"
    assert [
        row["memory_id"] for row in upgraded.search_approved_memory("NAS")
    ] == [memory_ids[2]]
    hits = upgraded.search_conversation_turns("rotation")
    assert [hit["turn_id"] for hit in hits] == ["turn_upgrade"]
    assert "rotation" in str(hits[0]["snippet"]).lower()

    report = inspect_memory_integrity(store=upgraded, workspace_root=tmp_path)
    assert report.clean
    assert report.text_search_engine == "fts5"
    assert report.index_engine_mismatch_count == 0
    assert report.fts_count == len(memory_ids)


def test_an_index_left_on_the_wrong_engine_is_reported_rather_than_answered_silently(
    tmp_path: Path,
) -> None:
    """A workspace carried to an older host, and back.

    An FTS4 index on an FTS5 build answers every query, so nothing surfaces it
    except a check that looks. The integrity report is where an owner can act on
    it — upgrade, or accept recency ordering — so it must not read as clean.
    """
    store = SQLiteStore(tmp_path)
    _write(store, tmp_path, "The deployment runbook lives in the ops repository.")
    with store.connect() as connection:
        connection.execute("DROP TABLE conversation_fts")
        connection.execute(
            "CREATE VIRTUAL TABLE conversation_fts USING fts4("
            "turn_id UNINDEXED, session_id UNINDEXED, role UNINDEXED, text)"
        )

    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.index_engine_mismatch_count == 1
    assert report.clean is False


def test_the_ranked_query_evaluates_the_index_once(tmp_path: Path) -> None:
    """A performance invariant old enough to predate the ranking, asserted.

    Scoring with a correlated scalar subquery puts BM25 on the row and re-scans
    the FTS table *per candidate row*: measured at 5.2 s against 800 memories
    where the joined form costs 23 ms. It is not a wrong answer, so no
    correctness test catches it — the only symptom is a slow suite, which is
    how it reached CI in the first place.

    The plan is the assertion rather than a stopwatch: a timing budget on a
    shared runner is a flaky test, while "how many times is the index scanned"
    is exactly the property that regressed and does not vary with load.
    """
    store = SQLiteStore(tmp_path)
    for index in range(25):
        _write(store, tmp_path, f"Memory {index} about deployment and the ops runbook.")

    with store.connect() as connection:
        plan = "\n".join(
            str(row[-1])
            for row in connection.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT m.*, ranked.relevance FROM approved_memory m "
                "JOIN (SELECT memory_id, bm25(approved_memory_fts, 0.0, 1.0, 0.4) AS relevance "
                "      FROM approved_memory_fts WHERE approved_memory_fts MATCH ?) AS ranked "
                "  ON ranked.memory_id = m.memory_id "
                "ORDER BY ranked.relevance ASC LIMIT 20",
                ("deployment",),
            )
        )
    assert plan.count("approved_memory_fts") == 1, f"the index must be scanned once:\n{plan}"
    assert "CORRELATED" not in plan.upper(), f"no per-row re-evaluation:\n{plan}"
    assert "SEARCH m USING INDEX" in plan, f"and each hit probed by primary key:\n{plan}"

    # And the query the store actually issues still answers correctly.
    assert len(store.search_approved_memory("deployment", limit=5)) == 5


def test_health_names_the_engine_and_what_it_costs(tmp_path: Path) -> None:
    """A silent fallback needs a surface, or it is indistinguishable from working."""
    SQLiteStore(tmp_path)
    health = store_health(tmp_path)
    assert health["store"] == "ok"
    assert health["text_search_engine"] == "fts5"
    assert health["text_search_ranking"] == "bm25_relevance"
    assert health["text_search_reason"] == ""


@pytest.mark.parametrize("query", ("a (b", 'quote"', "*", "  "))
def test_a_query_with_no_indexable_term_answers_empty_rather_than_raising(
    tmp_path: Path, query: str
) -> None:
    store = SQLiteStore(tmp_path)
    _write(store, tmp_path, "The deployment runbook lives in the ops repository.")
    assert store.search_approved_memory(query) == []
