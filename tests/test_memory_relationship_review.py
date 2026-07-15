from pathlib import Path

from raiker.memory.entities import propose_entity_relationship, resolve_entity_relationship_proposal
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore


def _memory(store: SQLiteStore, root: Path, text: str) -> str:
    return write_memory(
        text, workspace_root=root, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 0.8, 0.8, "until_forget", "approved", "test"),
    ).memory_id


def test_relationship_inference_requires_human_review_before_graph_mutation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    candidate_id = propose_entity_relationship(
        store=store, subject_name="Sarah", subject_type="person", predicate="married_to",
        object_name="Mark", object_type="person", evidence_memory_id=_memory(store, tmp_path, "Sarah married Mark."),
        confidence=0.8,
    )
    candidate = store.get_memory_relationship_candidate(candidate_id)
    assert candidate is not None and candidate["decision"] == "needs_user_review"
    relationship_id = resolve_entity_relationship_proposal(
        store=store, candidate_id=candidate_id, decision="approved", reviewer_id="principal_owner",
    )
    assert relationship_id
    candidate = store.get_memory_relationship_candidate(candidate_id)
    assert candidate is not None and candidate["resolved_by"] == "principal_owner"


def test_relationship_inference_can_be_denied_without_graph_mutation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    candidate_id = propose_entity_relationship(
        store=store, subject_name="Sarah", subject_type="person", predicate="leads",
        object_name="Project", object_type="project", evidence_memory_id=_memory(store, tmp_path, "Sarah may lead."),
        confidence=0.4,
    )
    assert resolve_entity_relationship_proposal(
        store=store, candidate_id=candidate_id, decision="denied", reviewer_id="principal_owner",
    ) == ""
    candidate = store.get_memory_relationship_candidate(candidate_id)
    assert candidate is not None and candidate["decision"] == "denied"
