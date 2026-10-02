# SPDX-License-Identifier: Apache-2.0
"""Memory: proposals, the lifecycle of one memory, import and export, indexes and observations."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

from raiker.api.wire.sessions import SourceExcerptView
from raiker.control.views.memory import MemoryControlView, ObservationView


class MemoryProposal(TypedDict):
    """A sentence the runtime proposed remembering, waiting on the owner."""

    candidate_id: str
    source_event_id: str
    memory_type: str
    scope: str
    text: str
    sensitivity: str
    confidence: float
    decision: str
    created_at: str


class MemoryRelationshipProposal(TypedDict):
    """A relationship read out of an approved memory, waiting on the owner."""

    candidate_id: str
    subject_name: str
    subject_type: str
    predicate: str
    object_name: str
    object_type: str
    evidence_memory_id: str
    evidence_text: str
    confidence: float
    extractor_version: str
    decision: Literal["needs_user_review"]
    created_at: str


class ProposalDecided(TypedDict):
    """A decision on a proposal; an approval names the memory it became."""

    ok: bool
    candidate_id: str
    decision: str
    memory_id: NotRequired[str]
    relationship_proposals: NotRequired[int]


class RelationshipScan(TypedDict):
    ok: bool
    scanned: int
    proposed: int
    skipped: int
    already_present: int


class RelationshipDecided(TypedDict):
    ok: bool
    candidate_id: str
    decision: str
    relationship_id: str | None


class RelationshipRejected(TypedDict):
    ok: bool
    relationship_id: str
    active: bool


class MemoryPinned(TypedDict):
    ok: bool
    memory_id: str
    pinned: bool


class MemoryExport(TypedDict):
    ok: bool
    memories: list[MemoryControlView]


class MemoryImportDuplicate(TypedDict):
    """A record that is already stored, or that the file holds twice (``memory_id`` empty)."""

    index: int
    text: str
    scope: str
    memory_id: str


class MemoryImportPreview(TypedDict):
    """What an import would change, before it changes anything (BUG-244)."""

    ok: bool
    total: int
    new_count: int
    duplicate_count: int
    duplicates: list[MemoryImportDuplicate]


class MemoryImportResult(TypedDict):
    ok: bool
    count: int
    reviewed: int
    imported: int
    skipped_duplicates: int
    relationship_proposals: int


class MemoryReconciled(TypedDict):
    ok: bool
    projection_rows_reconciled: int


class MemoryIntegrity(TypedDict):
    """How far each projection of approved memory has drifted from it; nothing is repaired."""

    ok: bool
    clean: bool
    active_memory_count: int
    fts_count: int
    stale_fts_count: int
    missing_markdown_count: int
    stale_projection_count: int
    stale_graph_edge_count: int
    checksum_mismatch_count: int
    orphaned_markdown_count: int
    failed_purge_location_count: int
    project_path_inconsistency_count: int
    text_search_engine: str
    index_engine_mismatch_count: int
    conversation_index_count: int
    stale_conversation_index_count: int


class ConversationIndexRebuilt(TypedDict):
    ok: bool
    indexed_rows: int


class ObservationsView(TypedDict):
    """What the runtime captured while it worked, with the counts an empty list cannot give."""

    ok: bool
    observations: list[ObservationView]
    captured: int
    skipped: int
    gists_pending: int
    due_for_expiry: list[str]


class ObservationsDeleted(TypedDict):
    ok: bool
    deleted_observation_ids: list[str]


class GistDiscarded(TypedDict):
    ok: bool
    gist_id: str
    discarded: bool


class IncognitoSet(TypedDict):
    ok: bool
    incognito: bool


class EmbeddingBackendSet(TypedDict):
    ok: bool
    embedding_backend: str


class EmbeddingIndexBuilt(TypedDict):
    """One governed embedding run (MEM-10), as the executor reported it."""

    ok: bool
    operation: Literal["index_memories"]
    embedding_model: str
    provider_models: list[str]
    indexed_count: int
    indexed_file_chunk_count: int
    skipped_count: int
    skipped: list[dict[str, str]]
    provider_backed: bool
    local_only: bool
    content_redacted: bool


class MemoryForgotten(TypedDict):
    ok: bool
    memory_id: str


class MemoryHistoryEvent(TypedDict):
    audit_id: str
    action: str
    actor_id: str
    created_at: str
    details: dict[str, Any]


class MemoryHistory(TypedDict):
    ok: bool
    memory_id: str
    events: list[MemoryHistoryEvent]


class MemoryScopeChanged(TypedDict):
    ok: bool
    memory_id: str
    scope: str
    updated_at: str


class MemoryArchived(TypedDict):
    ok: bool
    memory_id: str
    archived: bool


class MemoryPurgePreview(TypedDict):
    """What a purge removes, and the id the owner must send back to confirm it."""

    ok: bool
    memory_id: str
    artifacts: list[str]
    backup_disposition: str
    requires_confirmation: str


class MemoryPurged(TypedDict):
    ok: bool
    memory_id: str
    purged: bool
    backup_disposition: str


class MemoryUpdated(TypedDict):
    """An edit, a search switch or an expiry, and the state the memory is in now."""

    ok: bool
    memory_id: str
    search_enabled: bool
    expires_at: str | None


class MemoryCorrected(TypedDict):
    ok: bool
    memory_id: str
    supersedes_memory_id: str


class MemorySource(SourceExcerptView):
    """The passage a memory was drawn from, or the stated reason it cannot be opened (BUG-27)."""

    ok: bool
    memory_id: str


def memory_proposal(row: dict[str, Any]) -> MemoryProposal:
    """A candidate as the review card reads it — never its stored row."""
    return {
        "candidate_id": str(row["candidate_id"]),
        "source_event_id": str(row.get("source_event_id") or ""),
        "memory_type": str(row.get("memory_type") or ""),
        "scope": str(row.get("scope") or ""),
        "text": str(row.get("text") or ""),
        "sensitivity": str(row.get("sensitivity") or ""),
        "confidence": float(row.get("confidence") or 0.0),
        "decision": str(row.get("decision") or ""),
        "created_at": str(row.get("created_at") or ""),
    }


def relationship_proposal(row: dict[str, Any]) -> MemoryRelationshipProposal:
    """A relationship candidate as the review card reads it — never its stored row."""
    return {
        "candidate_id": str(row["candidate_id"]),
        "subject_name": str(row.get("subject_name") or ""),
        "subject_type": str(row.get("subject_type") or ""),
        "predicate": str(row.get("predicate") or ""),
        "object_name": str(row.get("object_name") or ""),
        "object_type": str(row.get("object_type") or ""),
        "evidence_memory_id": str(row.get("evidence_memory_id") or ""),
        "evidence_text": str(row.get("evidence_text") or ""),
        "confidence": float(row.get("confidence") or 0.0),
        "extractor_version": str(row.get("extractor_version") or ""),
        "decision": "needs_user_review",
        "created_at": str(row.get("created_at") or ""),
    }
