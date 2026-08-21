from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from raiker.memory.entity_extraction import (
    EXTRACTOR_VERSION,
    extract_relationship_candidates,
    propose_memory_relationships,
)
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
OTHER = "principal_other"


def _memory(store: SQLiteStore, root: Path, text: str, owner: str = OWNER) -> str:
    return write_memory(
        text,
        workspace_root=root,
        store=store,
        owner_principal_id=owner,
        governance=MemoryGovernance(
            "evt_extract",
            "sess_extract",
            "turn_extract",
            "test",
            0.9,
            0.9,
            "until_forget",
            "approved",
            owner,
        ),
    ).memory_id


@pytest.mark.parametrize(
    "text, triple",
    [
        ("Sarah is married to Mark.", ("Sarah", "married_to", "Mark")),
        ("Rahul works on Raiker.", ("Rahul", "works_on", "Raiker")),
        ("Rahul uses Python.", ("Rahul", "uses", "Python")),
        ("Rahul prefers dark mode.", ("Rahul", "prefers", "dark mode")),
        ("Raiker is located in London.", ("Raiker", "located_in", "London")),
        ("API is part of Raiker.", ("API", "part_of", "Raiker")),
        ("Raiker is a governed agent.", ("Raiker", "is_a", "governed agent")),
    ],
)
def test_extracts_only_the_bounded_predicate_vocabulary(
    text: str, triple: tuple[str, str, str]
) -> None:
    extracted = extract_relationship_candidates(text)
    assert len(extracted) == 1
    assert (extracted[0].subject_name, extracted[0].predicate, extracted[0].object_name) == triple
    assert extracted[0].extractor_version == EXTRACTOR_VERSION


def test_unrecognized_or_secret_like_text_produces_no_candidate() -> None:
    assert extract_relationship_candidates("Sarah might possibly know Mark.") == ()
    assert extract_relationship_candidates("Rahul uses sk-proj-abcdefghijklmnopqrstuvwxyz.") == ()


def test_explicit_relation_proposes_review_but_does_not_populate_graph(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Sarah is married to Mark.")

    summary = propose_memory_relationships(store, memory_id, OWNER)

    assert summary.proposed == 1
    candidate = store.list_memory_relationship_candidates(OWNER)[0]
    assert (candidate["subject_name"], candidate["predicate"], candidate["object_name"]) == (
        "Sarah",
        "married_to",
        "Mark",
    )
    assert store.match_memory_entities("Sarah") == []


def test_proposal_is_idempotent_and_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Rahul uses Python.")

    first = propose_memory_relationships(store, memory_id, OWNER)
    second = propose_memory_relationships(store, memory_id, OWNER)

    assert first.proposed == 1
    assert second.already_present == 1
    assert len(store.list_memory_relationship_candidates(OWNER)) == 1
    assert store.list_memory_relationship_candidates(OTHER) == []


def test_atomic_approval_is_stale_safe_and_cross_owner_safe(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Sarah is married to Mark.")
    propose_memory_relationships(store, memory_id, OWNER)
    candidate_id = str(store.list_memory_relationship_candidates(OWNER)[0]["candidate_id"])

    with pytest.raises(ValueError, match="stale_memory_relationship_candidate"):
        store.resolve_memory_relationship_candidate_atomic(
            candidate_id,
            owner_principal_id=OTHER,
            decision="approved",
            reviewer_id=OTHER,
        )
    relationship_id = store.resolve_memory_relationship_candidate_atomic(
        candidate_id,
        owner_principal_id=OWNER,
        decision="approved",
        reviewer_id=OWNER,
    )
    assert relationship_id
    with pytest.raises(ValueError, match="stale_memory_relationship_candidate"):
        store.resolve_memory_relationship_candidate_atomic(
            candidate_id,
            owner_principal_id=OWNER,
            decision="approved",
            reviewer_id=OWNER,
        )
    assert len(store.list_memory_entity_neighborhood(
        store.match_memory_entities("Sarah")[0]["entity_id"], owner_principal_id=OWNER
    )) == 1


def test_denial_creates_no_entity_or_edge(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Sarah is married to Mark.")
    propose_memory_relationships(store, memory_id, OWNER)
    candidate_id = str(store.list_memory_relationship_candidates(OWNER)[0]["candidate_id"])

    assert store.resolve_memory_relationship_candidate_atomic(
        candidate_id,
        owner_principal_id=OWNER,
        decision="denied",
        reviewer_id=OWNER,
    ) == ""
    assert store.match_memory_entities("Sarah") == []


def test_concurrent_review_has_one_winner_and_one_stale_decision(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Sarah is married to Mark.")
    propose_memory_relationships(store, memory_id, OWNER)
    candidate_id = str(store.list_memory_relationship_candidates(OWNER)[0]["candidate_id"])

    def resolve() -> str:
        try:
            return store.resolve_memory_relationship_candidate_atomic(
                candidate_id,
                owner_principal_id=OWNER,
                decision="approved",
                reviewer_id=OWNER,
            )
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _item: resolve(), range(2)))

    assert sum(value.startswith("rel_") for value in outcomes) == 1
    assert outcomes.count("stale_memory_relationship_candidate") == 1


def test_relationship_write_failure_rolls_back_entities_and_review(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id = _memory(store, tmp_path, "Sarah is married to Mark.")
    propose_memory_relationships(store, memory_id, OWNER)
    candidate_id = str(store.list_memory_relationship_candidates(OWNER)[0]["candidate_id"])
    with store.connect() as connection:
        connection.execute(
            """CREATE TRIGGER reject_test_relationship BEFORE INSERT
               ON memory_entity_relationships BEGIN
               SELECT RAISE(ABORT, 'injected relationship failure'); END"""
        )

    with pytest.raises(Exception, match="injected relationship failure"):
        store.resolve_memory_relationship_candidate_atomic(
            candidate_id,
            owner_principal_id=OWNER,
            decision="approved",
            reviewer_id=OWNER,
        )

    candidate = store.get_memory_relationship_candidate(candidate_id)
    assert candidate is not None
    assert candidate["decision"] == "needs_user_review"
    assert store.match_memory_entities("Sarah") == []
