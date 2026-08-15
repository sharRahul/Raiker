"""Regression cover for FIXED-200 … FIXED-203 — the memory recall hardening round.

Each test names the failure it prevents rather than the code it calls: recall
runs on every turn with the owner's raw prompt as the query, so a defect here is
a defect in every conversation.
"""
import json
import time
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text

GOVERNANCE = MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test")


def _write(store: SQLiteStore, root: Path, text: str, *, projected: bool = True) -> str:
    memory = write_memory(
        text, workspace_root=root, scope="project:x", store=store, governance=GOVERNANCE
    )
    if projected:
        vector_id = new_id("vec_")
        store.insert_vector_record(
            VectorRecord(
                vector_id, VectorIndex.compute_content_hash(memory.text), memory.text,
                LOCAL_EMBEDDING_MODEL, 384, memory.scope, memory.sensitivity, utc_now(),
                json.dumps(embed_text(memory.text, 384)),
            )
        )
        store.link_memory_projection(memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL)
    return memory.memory_id


# ── FIXED-201 — an ordinary prompt must not raise out of recall ──

@pytest.mark.parametrize(
    "query",
    [
        "NOT deployment",          # leading keyword operator
        "AND leading",             # leading keyword operator
        "unbalanced (paren",       # unbalanced group
        "trailing paren)",         # unbalanced group
        "the NEAR keyword",        # infix keyword operator
        'quote " inside',
        "star * alone",
        "colon: prefix",
    ],
)
def test_prose_that_looks_like_fts_syntax_is_searched_not_executed(
    tmp_path: Path, query: str
) -> None:
    store = SQLiteStore(tmp_path)
    _write(store, tmp_path, "Deployment notes for the parser service.")
    # The prompt reaches recall verbatim, so an FTS operator in ordinary English
    # used to raise OperationalError and fail the turn's context source.
    assert isinstance(store.search_approved_memory(query, scope="project:x", limit=5), list)


def test_a_keyword_operator_does_not_invert_the_owners_question(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    # Holds all three words, which is what tells the two readings apart: as
    # syntax, `find NOT deployment` means "find, excluding deployment" and this
    # record is excluded by the very term being asked about; as three literals it
    # matches. Only the literal reading is what the owner typed.
    _write(store, tmp_path, "find not deployment in the log")
    assert len(store.search_approved_memory("find NOT deployment", scope="project:x", limit=5)) == 1


# ── FIXED-202 — zero-similarity memories must not be recalled ──

def test_a_query_matching_nothing_recalls_nothing(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    for text in [
        "Invoice 8812 was paid in March.",
        "The build uses Vite.",
        "Cat food brand is Whiskas.",
        "Server rack is in row 4.",
    ]:
        _write(store, tmp_path, text)
    # `VectorIndex.search` returns the top *k* with no floor, so on a corpus
    # smaller than the limit "top 10" is "all of them" at score 0.0 — every
    # unrelated owner memory presented to the model as recalled context.
    assert retrieve_hybrid_memory(store=store, query="zzzz qqqq wwww", scope="project:x") == []


def test_a_real_match_is_still_recalled(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    target = _write(store, tmp_path, "The deployment uses blue-green rollout.")
    _write(store, tmp_path, "Cat food brand is Whiskas.")
    results = retrieve_hybrid_memory(store=store, query="deployment rollout", scope="project:x")
    assert [result.memory_id for result in results] == [target]
    assert results[0].score > 0.0


# ── FIXED-200 — recall must not re-run the match once per row ──

def test_recall_does_not_scale_with_the_whole_corpus(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    for index in range(400):
        _write(store, tmp_path, f"note {index} about deployment and parsing", projected=False)
    started = time.perf_counter()
    rows = store.search_approved_memory("deployment parsing", scope="project:x", limit=10)
    elapsed = time.perf_counter() - started
    assert len(rows) == 10
    # Joining `approved_memory` onto the FTS table made the planner re-execute
    # the match per candidate row: ~4 s here, 13 s at 800 rows, 170 s at 3 000.
    # Driving from the index costs ~11 ms. The bound is loose on purpose — it is
    # a guard against the plan inverting again, not a benchmark.
    assert elapsed < 2.0, f"recall took {elapsed:.2f}s — the FTS join plan may have inverted"


# ── FIXED-203 — chunking must not loop forever ──

@pytest.mark.parametrize(("chunk_size", "overlap"), [(4, 4), (4, 5), (0, 0), (-1, 0), (8, -1)])
def test_chunk_text_rejects_arguments_that_never_advance(chunk_size: int, overlap: int) -> None:
    # An overlap at or above the chunk size advances the cursor by zero, so the
    # loop never terminates and the chunk list grows until the process dies.
    with pytest.raises(ValueError):
        VectorIndex.chunk_text("abcdefghij", chunk_size=chunk_size, overlap=overlap)


def test_chunk_text_still_overlaps_normally() -> None:
    assert VectorIndex.chunk_text("abcdefghij", chunk_size=4, overlap=1) == [
        "abcd",
        "defg",
        "ghij",
        "j",
    ]
