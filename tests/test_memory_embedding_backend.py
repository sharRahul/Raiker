"""MEM-03 — the vector leg names its own embedding space, and never mixes two.

The defect was not that the hashing embedding is bad. It is that it was used
unconditionally and *silently*: the vector leg embedded the query with
`raiker-local-hash-v1` whatever produced the stored vectors, so a workspace with
semantic vectors compared coordinates from two unrelated spaces, and a workspace
without them ran the lexical signal twice under two different names.

These cover the three properties that fix it: one space per search, the query
embedded in that same space, and every surface saying which space it was.
"""
from __future__ import annotations

import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.semantic import semantic_memory_status
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text
from raiker.vector.backends import (
    LEXICAL_FALLBACK_BACKEND,
    EmbeddingBackend,
    list_embedding_spaces,
    resolve_embedding_backend,
)

SEMANTIC_MODEL = "provider/text-embedding-3-small"
SEMANTIC_DIMENSIONS = 8


def _write(store: SQLiteStore, root: Path, text: str, scope: str = "project:alpha") -> str:
    return write_memory(
        text,
        workspace_root=root,
        scope=scope,
        store=store,
        governance=MemoryGovernance(
            "evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"
        ),
    ).memory_id


def _project(
    store: SQLiteStore, memory_id: str, *, model: str, vector: list[float], scope: str
) -> str:
    """Attach a vector to a memory the way the governed executor does."""
    vector_id = new_id("vec_")
    store.insert_vector_record(
        VectorRecord(
            vector_id=vector_id,
            content_hash="hash-" + vector_id,
            content_preview="",
            embedding_model=model,
            dimensions=len(vector),
            scope=scope,
            sensitivity="public",
            created_at=utc_now(),
            embedding=json.dumps(vector),
            owner_principal_id="",
        )
    )
    store.link_memory_projection(memory_id, "vector", vector_id, "v1")
    return vector_id


def test_a_default_workspace_resolves_the_labelled_lexical_fallback(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    backend = resolve_embedding_backend(store)
    assert backend.model_label == LOCAL_EMBEDDING_MODEL
    assert backend.semantic is False
    assert backend.kind == "lexical_fallback"
    # The reason is present even on success: "you are on the fallback" is the
    # answer the owner needs, and an empty string would read as "all is well".
    assert backend.reason_code == "embedding_backend_semantic_not_configured"


def test_a_semantic_space_wins_automatically_once_it_holds_vectors(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "The owner prefers the encrypted NAS target.")
    _project(
        store,
        memory_id,
        model=SEMANTIC_MODEL,
        vector=[1.0] + [0.0] * (SEMANTIC_DIMENSIONS - 1),
        scope="project:alpha",
    )

    spaces = list_embedding_spaces(store)
    assert [space.model_label for space in spaces] == [SEMANTIC_MODEL]
    backend = resolve_embedding_backend(store)
    assert backend.model_label == SEMANTIC_MODEL
    assert backend.semantic is True
    assert backend.dimensions == SEMANTIC_DIMENSIONS


def test_the_vector_leg_is_dropped_rather_than_answered_from_the_wrong_space(
    tmp_path: Path,
) -> None:
    """The heart of MEM-03.

    The stored vector is semantic and no governed embedder is available to embed
    the query in that space. Before this change the query was hashed anyway and
    the resulting cosine was a number with no meaning. Now the leg is absent —
    the lexical leg still answers, and nothing claims a similarity that was not
    computed.
    """
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "The owner prefers the encrypted NAS target.")
    _project(
        store,
        memory_id,
        model=SEMANTIC_MODEL,
        vector=[1.0] + [0.0] * (SEMANTIC_DIMENSIONS - 1),
        scope="project:alpha",
    )

    results = retrieve_hybrid_memory(store=store, query="encrypted NAS", scope="project:alpha")
    assert results, "the lexical leg still answers"
    assert results[0].sources == ("lexical",)
    assert results[0].vector_backend == SEMANTIC_MODEL
    assert results[0].vector_backend_semantic is True


def test_a_governed_embedder_makes_the_semantic_leg_contribute(tmp_path: Path) -> None:
    """With an embedder for the *same* space, the leg is real again.

    The query shares no token with the memory, so the lexical leg cannot find it.
    Only a vector in the same space can, which is exactly the recall MEM-03 said
    was missing.
    """
    store = SQLiteStore(tmp_path)
    memory_id = _write(store, tmp_path, "The owner prefers the encrypted NAS target.")
    stored = [1.0] + [0.0] * (SEMANTIC_DIMENSIONS - 1)
    _project(store, memory_id, model=SEMANTIC_MODEL, vector=stored, scope="project:alpha")

    def embedder(backend: EmbeddingBackend, query: str) -> list[float]:
        assert backend.model_label == SEMANTIC_MODEL
        assert query == "where should backups go"
        return stored

    results = retrieve_hybrid_memory(
        store=store,
        query="where should backups go",
        scope="project:alpha",
        query_embedder=embedder,
    )
    assert [result.memory_id for result in results] == [memory_id]
    assert results[0].sources == ("vector",)
    assert results[0].vector_backend_semantic is True


def test_vectors_from_a_second_space_are_never_read_into_the_first(tmp_path: Path) -> None:
    """Two spaces, one search. The unselected space contributes nothing."""
    store = SQLiteStore(tmp_path)
    hashed = _write(store, tmp_path, "Alpha memory about deployment.")
    semantic = _write(store, tmp_path, "Beta memory about deployment.")
    _project(
        store,
        hashed,
        model=LOCAL_EMBEDDING_MODEL,
        vector=embed_text("Alpha memory about deployment.", 384),
        scope="project:alpha",
    )
    _project(
        store,
        semantic,
        model=SEMANTIC_MODEL,
        vector=[1.0] + [0.0] * (SEMANTIC_DIMENSIONS - 1),
        scope="project:alpha",
    )

    results = retrieve_hybrid_memory(
        store=store,
        query="deployment",
        scope="project:alpha",
        embedding_backend=LEXICAL_FALLBACK_BACKEND,
    )
    by_id = {result.memory_id: result for result in results}
    assert "vector" in by_id[hashed].sources
    # The semantic memory shares the word "deployment", so it is found — but
    # only lexically. A `vector` source on it would mean its 8-dimension vector
    # had been read into a 384-dimension search.
    assert semantic in by_id, "the lexical leg still finds the shared term"
    assert by_id[semantic].sources == ("lexical",)


def test_an_owner_selection_that_holds_no_vectors_is_named_rather_than_ignored(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path)
    store.set_memory_embedding_backend("provider/never-configured")
    backend = resolve_embedding_backend(store)
    assert backend.model_label == LOCAL_EMBEDDING_MODEL
    assert backend.reason_code == (
        "embedding_backend_selected_has_no_vectors:provider/never-configured"
    )


def test_semantic_status_reports_the_read_backend_not_only_the_write_gate(
    tmp_path: Path,
) -> None:
    """The statement that used to be misleading.

    `embedding_backend: disabled` was true of writes and silent about reads,
    while the vector leg ran on every search. Both facts are now stated.
    """
    store = SQLiteStore(tmp_path)
    status = semantic_memory_status(0, store=store)
    assert status["semantic_writes_enabled"] is False
    assert status["embedding_backend"] == "disabled"
    assert status["retrieval_embedding_backend"] == LOCAL_EMBEDDING_MODEL
    assert status["retrieval_is_semantic"] is False
    assert status["retrieval_embedding_kind"] == "lexical_fallback"
