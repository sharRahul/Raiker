"""MEM-11/12/13 — what a model can actually reach, and whether it matches the runtime.

Three defects that only show up when you compare two paths that should agree:

* **MEM-11** — the model's `memory_search` ran the lexical index while the
  ambient recall injected into the *same turn* ran all of hybrid retrieval. Two
  answers to one question, and the weaker one was the half the model could
  steer.
* **MEM-12** — the graph leg was gated on an `entity_id` no production caller
  ever passed, so the third leg of "hybrid" retrieval never ran on a real turn.
* **MEM-13** — the knowledge graph was drawn for a person and consumed
  internally, and no tool could traverse it.
"""
from __future__ import annotations

import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.graph_tools import knowledge_graph
from raiker.tools.memory_tools import memory_search
from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text

SCOPE = "project:alpha"


def _write(store: SQLiteStore, root: Path, text: str) -> str:
    return write_memory(
        text,
        workspace_root=root,
        scope=SCOPE,
        store=store,
        governance=MemoryGovernance(
            "evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"
        ),
    ).memory_id


def _project_vector(store: SQLiteStore, memory_id: str, text: str) -> None:
    vector_id = new_id("vec_")
    store.insert_vector_record(
        VectorRecord(
            vector_id=vector_id,
            content_hash="hash-" + vector_id,
            content_preview="",
            embedding_model=LOCAL_EMBEDDING_MODEL,
            dimensions=384,
            scope=SCOPE,
            sensitivity="public",
            created_at=utc_now(),
            embedding=json.dumps(embed_text(text, 384)),
            owner_principal_id="",
        )
    )
    store.link_memory_projection(memory_id, "vector", vector_id, "v1")


def _entity(store: SQLiteStore, name: str) -> str:
    """Upsert and return the id that is actually stored.

    `upsert_memory_entity` conflicts on `(normalized_name, entity_type)` and
    keeps the existing row, so the id a caller passes is not necessarily the id
    that ends up in the table. Reading it back is the only way to link against
    the right one — an easy trap, and one a caller hits as a foreign-key error
    rather than anything self-explanatory.
    """
    store.upsert_memory_entity(new_id("ent_"), name, "thing")
    matched = store.match_memory_entities(name, limit=1)
    assert matched, f"entity {name!r} should be resolvable after upsert"
    return str(matched[0]["entity_id"])


def _link(store: SQLiteStore, subject: str, predicate: str, obj: str, evidence: str) -> tuple[str, str]:
    subject_id, object_id = _entity(store, subject), _entity(store, obj)
    store.link_memory_entities(new_id("rel_"), subject_id, predicate, object_id, evidence, 0.9)
    return subject_id, object_id


# ── MEM-11 ───────────────────────────────────────────────────────────────────


def test_the_model_tool_and_ambient_recall_now_answer_the_same_way(tmp_path: Path) -> None:
    """The defect stated as the disagreement it was.

    `memory_search` used to return only lexical hits while the gatherer's
    injected context, built in the same turn, carried vector ones too. Both go
    through `retrieve_hybrid_memory` now, so the same query returns the same
    memories in the same order.
    """
    store = SQLiteStore(tmp_path)
    text = "The encrypted NAS target is the backup destination."
    memory_id = _write(store, tmp_path, text)
    _project_vector(store, memory_id, text)

    tool = memory_search(tmp_path, "backup destination", scope=SCOPE)
    ambient = retrieve_hybrid_memory(store=store, query="backup destination", scope=SCOPE, limit=20)

    assert tool["status"] == "success"
    assert [r["memory_id"] for r in tool["results"]] == [m.memory_id for m in ambient]
    assert memory_id in [r["memory_id"] for r in tool["results"]]


def test_a_result_says_which_legs_found_it_and_which_embedding_was_searched(
    tmp_path: Path,
) -> None:
    """A lexical-only hit must not read as corroborated by three signals."""
    store = SQLiteStore(tmp_path)
    text = "Rotation of the SQLCipher key is quarterly."
    memory_id = _write(store, tmp_path, text)
    _project_vector(store, memory_id, text)

    result = memory_search(tmp_path, "rotation quarterly", scope=SCOPE)
    assert result["retrieval"]["strategy"] == "hybrid"
    assert result["retrieval"]["embedding_backend"] == LOCAL_EMBEDDING_MODEL
    assert result["retrieval"]["embedding_is_semantic"] is False
    hit = result["results"][0]
    assert set(hit["sources"]) <= {"lexical", "vector", "graph"}
    assert "lexical" in hit["sources"]
    assert hit["trust_label"] == "untrusted_memory_data"


def test_the_fields_the_lexical_tool_returned_are_not_lost(tmp_path: Path) -> None:
    """Routing through hybrid retrieval must not quietly drop the old shape."""
    store = SQLiteStore(tmp_path)
    _write(store, tmp_path, "The deployment runbook lives in the ops repository.")
    hit = memory_search(tmp_path, "deployment runbook", scope=SCOPE)["results"][0]
    for field in ("memory_id", "text", "scope", "sensitivity", "created_at", "tags", "source"):
        assert field in hit, field
    assert hit["created_at"], "a memory's age is how a reader judges whether it still holds"


# ── MEM-12 ───────────────────────────────────────────────────────────────────


def test_the_graph_leg_fires_from_the_query_without_an_explicit_entity_id(
    tmp_path: Path,
) -> None:
    """The heart of MEM-12.

    The evidence memory shares **no token** with the query, so neither the
    lexical nor the hashing-vector leg can reach it. Only a graph traversal
    anchored on an entity the query names can — and before this change no
    production caller ever supplied that anchor, so it never happened.
    """
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Quarterly verification is performed by the operations team.")
    _link(store, "helios", "verified_by", "operations team", evidence)

    results = retrieve_hybrid_memory(store=store, query="what about helios", scope=SCOPE, limit=10)

    found = {r.memory_id: r for r in results}
    assert evidence in found, "the graph leg must reach a memory sharing no query token"
    assert found[evidence].sources == ("graph",)


def test_an_explicit_entity_id_still_wins_over_resolution(tmp_path: Path) -> None:
    """A caller that names an entity is asking about it, not about the words."""
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Nightly snapshots are retained for thirty days.")
    subject_id, _ = _link(store, "helios", "retains", "snapshots", evidence)

    # The query names a *different* entity; the explicit anchor must be used.
    _link(store, "selene", "retains", "logs", _write(store, tmp_path, "Logs roll weekly."))
    results = retrieve_hybrid_memory(
        store=store, query="selene", scope=SCOPE, entity_id=subject_id, limit=10
    )
    assert evidence in {r.memory_id for r in results}


def test_two_paths_to_one_memory_do_not_inflate_its_score(tmp_path: Path) -> None:
    """Densely connected entities must not outrank exact matches on topology."""
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Retention is thirty days.")
    _link(store, "helios", "retains", "snapshots", evidence)
    _link(store, "snapshots", "stored_on", "helios", evidence)

    results = retrieve_hybrid_memory(store=store, query="helios snapshots", scope=SCOPE, limit=10)
    hit = next(r for r in results if r.memory_id == evidence)
    graph_score = dict(hit.score_breakdown)["graph"]
    assert graph_score <= 0.9 + 1e-9, f"one fact reached twice is still one fact: {graph_score}"


def test_a_query_naming_nothing_leaves_the_graph_leg_idle(tmp_path: Path) -> None:
    """Resolution must not invent an anchor. A coincidence is worse than nothing."""
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Nightly snapshots are retained for thirty days.")
    _link(store, "helios", "retains", "snapshots", evidence)

    results = retrieve_hybrid_memory(store=store, query="unrelated weather report", limit=10)
    assert all("graph" not in r.sources for r in results)


def test_matching_is_on_whole_terms_not_substrings(tmp_path: Path) -> None:
    """`LIKE '%id%'` would anchor on any entity containing those letters."""
    store = SQLiteStore(tmp_path)
    store.upsert_memory_entity(new_id("ent_"), "nas", "thing")
    assert store.match_memory_entities("nas") != []
    assert store.match_memory_entities("nasty business") == []
    # A multi-word entity is still found inside a longer sentence.
    store.upsert_memory_entity(new_id("ent_"), "encrypted NAS", "thing")
    names = {row["display_name"] for row in store.match_memory_entities("the encrypted nas target")}
    assert "encrypted NAS" in names


# ── MEM-13 ───────────────────────────────────────────────────────────────────


def test_a_model_can_find_an_entity_and_then_walk_its_relationships(
    tmp_path: Path,
) -> None:
    """The two-step a model actually performs: discover, then traverse."""
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Backups are written nightly.")
    _link(store, "helios", "hosts", "backups", evidence)

    found = knowledge_graph(tmp_path, "entities", query="helios")
    assert found["status"] == "success" and found["count"] == 1
    entity_id = found["entities"][0]["entity_id"]

    walked = knowledge_graph(tmp_path, "neighbors", entity_id=entity_id)
    assert walked["status"] == "success"
    edge = walked["edges"][0]
    assert (edge["subject"], edge["predicate"], edge["object"]) == ("helios", "hosts", "backups")
    assert edge["direction"] == "outgoing"
    # The governance property: every edge is traceable to approved memory.
    assert edge["evidence_memory_id"] == evidence
    assert walked["trust_label"] == "untrusted_memory_data"


def test_neighbors_resolves_a_name_so_the_model_needs_no_protocol(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Backups are written nightly.")
    _link(store, "helios", "hosts", "backups", evidence)

    walked = knowledge_graph(tmp_path, "neighbors", query="tell me about helios")
    assert walked["count"] == 1
    assert walked["resolved_from"] == "helios"


def test_the_graph_never_exposes_an_edge_whose_evidence_is_withdrawn(
    tmp_path: Path,
) -> None:
    """The graph must not become a back door around memory governance.

    Archiving the evidence has to remove the edge, or a forgotten fact stays
    readable through its shape.
    """
    store = SQLiteStore(tmp_path)
    evidence = _write(store, tmp_path, "Backups are written nightly.")
    _link(store, "helios", "hosts", "backups", evidence)
    assert knowledge_graph(tmp_path, "neighbors", query="helios")["count"] == 1

    store.set_approved_memory_archived(evidence, archived_at=utc_now(), updated_at=utc_now())
    assert knowledge_graph(tmp_path, "neighbors", query="helios")["count"] == 0


def test_unknown_actions_and_missing_anchors_are_named_refusals(tmp_path: Path) -> None:
    SQLiteStore(tmp_path)
    assert knowledge_graph(tmp_path, "delete")["error"]["type"] == "unknown_action"
    assert knowledge_graph(tmp_path, "entities")["error"]["type"] == "empty_query"
    assert knowledge_graph(tmp_path, "neighbors")["error"]["type"] == "missing_anchor"


def test_an_unknown_name_answers_empty_rather_than_failing(tmp_path: Path) -> None:
    """Nothing known by that name is an answer, not an error."""
    SQLiteStore(tmp_path)
    walked = knowledge_graph(tmp_path, "neighbors", query="nothing named this")
    assert walked["status"] == "success"
    assert walked["count"] == 0 and walked["entity"] is None
