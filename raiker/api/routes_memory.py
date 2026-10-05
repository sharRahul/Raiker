"""Reliable memory controls (backlog item 3): user-facing surface over the
existing governed memory store.

These routes read/control the same store the memory_write/memory_forget tools
already use — no second memory system is created. List carries provenance,
scope, sensitivity, confidence, retention, and a pin flag. Forget reuses the
governed forget path (human-only). An incognito opt-out boundary withholds
approved project memory from the turn context.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.schemas import serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.memory import (
    ConversationIndexRebuilt,
    DamagedVectorsRemoved,
    EmbeddingBackendSet,
    EmbeddingIndexBuilt,
    GistDiscarded,
    IncognitoSet,
    MemoryArchived,
    MemoryCorrected,
    MemoryExport,
    MemoryForgotten,
    MemoryHistory,
    MemoryImportBatches,
    MemoryImportPreview,
    MemoryImportResult,
    MemoryImportUndone,
    MemoryIntegrity,
    MemoryPinned,
    MemoryProposal,
    MemoryPurged,
    MemoryPurgePreview,
    MemoryReconciled,
    MemoryRelationshipProposal,
    MemoryScopeChanged,
    MemorySource,
    MemoryUpdated,
    ObservationsDeleted,
    ObservationsView,
    ProposalDecided,
    RelationshipDecided,
    RelationshipRejected,
    RelationshipScan,
    TextIndexesRebuilt,
    memory_proposal,
    relationship_proposal,
)
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.runtime.authority.models import Principal
from raiker.runtime.source_provenance import SourceProvenanceService
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _service(request: Request) -> DashboardService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return DashboardService(ws)


@router.get("/api/memory")
async def list_memories(
    request: Request,
    scope: str | None = None,
    include_inactive: bool = False,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """List approved memories with governance metadata + pin state.

    ``include_inactive`` adds the archived and expired records the owner can
    restore or extend. It changes what is *listed*, never what is recalled.
    """
    return serialize_dto(
        _service(request).list_memories(
            scope=scope,
            acting_principal_id=auth_data[0].principal_id,
            include_inactive=include_inactive,
        )
    )


@router.get("/api/memory/proposals")
async def list_memory_proposals(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    answer: list[MemoryProposal] = [
        memory_proposal(row)
        for row in _service(request).list_memory_proposals(auth_data[0].principal_id)
    ]
    return serialize_dto(answer)


@router.post("/api/memory/proposals/{candidate_id}/decision")
async def decide_memory_proposal(
    candidate_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).decide_memory_proposal(
        candidate_id,
        decision=str(body.get("decision", "")),
        edited_text=(str(body["edited_text"]) if body.get("edited_text") is not None else None),
        reason=(str(body["reason"]) if body.get("reason") is not None else None),
        expected_decision=str(body.get("expected_decision", "deferred")),
        acting_principal_id=auth_data[0].principal_id,
    )
    if not result.ok:
        conflict = result.reason_code in {"stale_memory_proposal"}
        raise refusal(
            status.HTTP_409_CONFLICT if conflict else status.HTTP_403_FORBIDDEN,
            result.reason_code,
        )
    answer = cast(ProposalDecided, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/relationship-proposals")
@router.get("/api/memory/entity-proposals")
async def list_memory_relationship_proposals(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    answer: list[MemoryRelationshipProposal] = [
        relationship_proposal(row) for row in _service(request).list_memory_relationship_proposals(
        auth_data[0].principal_id
    )
    ]
    return serialize_dto(answer)


@router.post("/api/memory/relationship-proposals/scan")
@router.post("/api/memory/entity-proposals/scan")
async def scan_memory_relationships(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).scan_memory_relationships(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(RelationshipScan, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/relationship-proposals/{candidate_id}/decision")
@router.post("/api/memory/entity-proposals/{candidate_id}/decision")
async def decide_memory_relationship_proposal(
    candidate_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).decide_memory_relationship_proposal(
        candidate_id,
        decision=str(body.get("decision", "")),
        expected_decision=str(body.get("expected_decision", "needs_user_review")),
        acting_principal_id=auth_data[0].principal_id,
    )
    if not result.ok:
        raise refusal(status.HTTP_409_CONFLICT
                if result.reason_code == "stale_memory_relationship_proposal"
                else status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(RelationshipDecided, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/entity-relationships/{relationship_id}/reject")
async def reject_memory_relationship(
    relationship_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).reject_memory_relationship(
        relationship_id,
        reason=str(body.get("reason", "")),
        expected_active=bool(body.get("expected_active", True)),
        acting_principal_id=auth_data[0].principal_id,
    )
    if not result.ok:
        raise refusal(status.HTTP_409_CONFLICT
                if result.reason_code == "stale_memory_relationship"
                else status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(RelationshipRejected, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}/pin")
async def set_memory_pinned(
    memory_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Pin (or unpin) a memory. Organizing label only — grants nothing."""
    pinned = bool(body.get("pinned", False))
    result = _service(request).set_memory_pinned(memory_id, pinned, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryPinned, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/export")
async def export_memories(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).export_memories(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryExport, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/import/preview")
async def preview_memory_import(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BUG-244 — how many of these records the workspace already holds.

    A read. It writes nothing and proposes nothing, so the review step can say
    what an import would actually change before the owner decides.
    """
    raw_memories = body.get("memories", [])
    memories = raw_memories if isinstance(raw_memories, list) else []
    result = _service(request).preview_memory_import(memories, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryImportPreview, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/import")
async def import_memories(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    raw_memories = body.get("memories", [])
    memories = raw_memories if isinstance(raw_memories, list) else []
    # Skipping what is already stored is the default; the owner can ask for a
    # second copy deliberately, having been shown which record it copies.
    skip_duplicates = body.get("skip_duplicates", True) is not False
    # UX-MEM-08 — the records the owner chose to skip in the review. Anything
    # that is not a whole number is dropped rather than guessed at.
    raw_excluded = body.get("exclude_indices", [])
    excluded = frozenset(
        value
        for value in (raw_excluded if isinstance(raw_excluded, list) else [])
        if isinstance(value, int) and not isinstance(value, bool)
    )
    raw_name = body.get("file_name", "")
    result = _service(request).import_memories(
        memories,
        auth_data[0].principal_id,
        skip_duplicates=skip_duplicates,
        exclude_indices=excluded,
        file_name=raw_name if isinstance(raw_name, str) else "",
    )
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryImportResult, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/import/batches")
async def list_memory_import_batches(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """UX-MEM-08 — recent import receipts, each one an import that can be taken back."""
    result = _service(request).list_memory_import_batches(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryImportBatches, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/import/batches/{batch_id}/undo")
async def undo_memory_import(
    batch_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """UX-MEM-08 — forget what one import wrote, except what the owner has changed since."""
    result = _service(request).undo_memory_import(batch_id, auth_data[0].principal_id)
    if not result.ok:
        code = {
            "unknown_import_batch": status.HTTP_404_NOT_FOUND,
            "import_batch_already_undone": status.HTTP_409_CONFLICT,
        }.get(result.reason_code or "", status.HTTP_403_FORBIDDEN)
        raise refusal(code, result.reason_code)
    answer = cast(MemoryImportUndone, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/reconcile")
async def reconcile_memory_indexes(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Owner-started reconciliation for FTS and projection lifecycle state."""
    result = _service(request).reconcile_memory_indexes(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryReconciled, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/integrity")
async def memory_integrity(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """MEM-09 — the owner-started integrity report, read-only.

    Declared above the `{memory_id}` routes so "integrity" is never read as an
    id. It scans and reports; every repair it names is a separate action.
    """
    result = _service(request).memory_integrity(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryIntegrity, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/conversation-index/rebuild")
async def rebuild_conversation_index(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """MEM-09's repair for a drifted conversation index."""
    result = _service(request).rebuild_conversation_index(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(ConversationIndexRebuilt, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/text-indexes/rebuild")
async def rebuild_text_indexes(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """DEC-24 step 6 — rebuild every text index; the repair for a damaged one."""
    result = _service(request).rebuild_text_indexes(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(TextIndexesRebuilt, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/vectors/remove-damaged")
async def remove_damaged_vectors(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """DEC-24 step 6 — remove vectors that cannot be read, so they can be indexed again."""
    result = _service(request).remove_damaged_vectors(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(DamagedVectorsRemoved, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/observations")
async def list_observations(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """MEM-04 — what the runtime captured while it worked, and what it refused."""
    result = _service(request).list_observations(auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(ObservationsView, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/observations/delete")
async def delete_observations(
    request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    raw_ids = body.get("observation_ids", [])
    observation_ids = {str(item) for item in raw_ids} if isinstance(raw_ids, list) else set()
    result = _service(request).delete_observations(observation_ids, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_404_NOT_FOUND
            if result.reason_code == "unknown_observation"
            else status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(ObservationsDeleted, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/gists/{gist_id}/discard")
async def discard_gist(
    request: Request, gist_id: str, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    result = _service(request).discard_gist(gist_id, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_404_NOT_FOUND
            if result.reason_code == "unknown_gist"
            else status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(GistDiscarded, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/eidetic/cleanup")
async def cleanup_expired_observations(
    request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    raw_ids = body.get("observation_ids", [])
    observation_ids = {str(item) for item in raw_ids} if isinstance(raw_ids, list) else set()
    result = _service(request).cleanup_expired_observations(
        observation_ids, str(body.get("now", utc_now())), auth_data[0].principal_id
    )
    if not result.ok:
        raise refusal(status.HTTP_409_CONFLICT, result.reason_code)
    answer = cast(ObservationsDeleted, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/settings")
async def get_memory_settings(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return serialize_dto(_service(request).get_memory_settings(auth_data[0].principal_id))


@router.put("/api/memory/incognito")
async def set_memory_incognito(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Toggle the incognito opt-out boundary (human-only).

    When on, the context gatherer withholds approved project memory from the
    turn context even if a project opted in. The memory is not deleted.
    """
    incognito = bool(body.get("incognito", False))
    result = _service(request).set_memory_incognito(incognito, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(IncognitoSet, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/embedding-backend")
async def set_memory_embedding_backend(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Choose which embedding space recall searches (MEM-03, human-only).

    ``auto`` means "the best space this workspace actually holds vectors in".
    Any other value must name a space that exists, or the choice is refused
    rather than quietly downgraded.
    """
    backend = str(body.get("embedding_backend", "auto")).strip() or "auto"
    result = _service(request).set_memory_embedding_backend(backend, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN
            if result.reason_code != "embedding_backend_unknown"
            else status.HTTP_409_CONFLICT, result.reason_code)
    answer = cast(EmbeddingBackendSet, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/embedding-index")
async def build_memory_embedding_index(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Embed the approved memories into a real semantic space (MEM-10, human-only).

    The route names the provider and the embedding model; it never names the
    memories. Which rows are eligible is resolved inside the executor from the
    acting principal, so this cannot be pointed at another account's memory, and
    the run goes through ``model_provider_runtime`` - one gate read, one policy
    review, one approval, one audit event - rather than around it.
    """
    provider = str(body.get("provider", "")).strip()
    model = str(body.get("model", "")).strip()
    # GCR-05 — off the loop before the synchronous work starts. This embeds
    # every eligible memory through a provider; inline it would hold the ASGI
    # event loop for the whole run.
    result = await asyncio.to_thread(
        lambda: _service(request).build_memory_embedding_index(
            provider, model, auth_data[0].principal_id
        )
    )
    if not result.ok:
        raise refusal(status.HTTP_409_CONFLICT
            if result.reason_code
            in {
                "embedding_model_not_named",
                "embedding_model_not_offered",
                "no_memories_to_index",
            }
            else status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(EmbeddingIndexBuilt, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.delete("/api/memory/{memory_id}")
async def forget_memory(
    memory_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Forget a memory through the governed path (human-only)."""
    result = _service(request).forget_memory_controlled(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryForgotten, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/{memory_id}/source")
async def get_memory_source(
    memory_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The passage this memory was drawn from, if it can still be opened (BUG-27).

    Memory already stored where each record came from and offered no way to go
    there, which made provenance unverifiable — indistinguishable, from the
    owner's seat, from provenance that was invented. This resolves those stored
    coordinates against the caller's own access and returns bounded plain text
    plus the offsets of the passage inside it.

    Every non-resolvable case is a named status rather than an error, because
    "this memory's source was deleted" and "you may not read that conversation"
    are both true answers the owner is entitled to see. Nothing here reveals
    whether a conversation the caller may not read exists.
    """
    principal_id = auth_data[0].principal_id
    memory = next(
        (
            record
            for record in _service(request).list_memories(acting_principal_id=principal_id)
            if record.memory_id == memory_id
        ),
        None,
    )
    if memory is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "memory_not_found")
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    service = SourceProvenanceService(SQLiteStore(ws))
    excerpt = service.resolve(dict(memory.provenance), memory.text, principal_id)
    answer = cast(MemorySource, {"ok": True, "memory_id": memory_id, **excerpt.to_dict()})
    return serialize_dto(answer)


@router.get("/api/memory/{memory_id}/history")
async def get_memory_history(
    memory_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).memory_history(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_404_NOT_FOUND, result.reason_code)
    answer = cast(MemoryHistory, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}/scope")
async def change_memory_scope(
    memory_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).change_memory_scope(
        memory_id,
        str(body.get("scope", "")),
        body.get("expected_updated_at"),
        str(body.get("reason", "")),
        auth_data[0].principal_id,
    )
    if not result.ok:
        conflict = result.reason_code == "stale_memory_scope_change"
        raise refusal(
            status.HTTP_409_CONFLICT if conflict else status.HTTP_403_FORBIDDEN,
            result.reason_code,
        )
    answer = cast(MemoryScopeChanged, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}/archive")
async def set_memory_archived(memory_id: str, request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    result = _service(request).set_memory_archived(memory_id, bool(body.get("archived", True)), auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryArchived, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.get("/api/memory/{memory_id}/purge-preview")
async def preview_memory_purge(memory_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    result = _service(request).preview_memory_purge(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryPurgePreview, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.delete("/api/memory/{memory_id}/purge")
async def purge_memory(memory_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth), x_memory_purge_confirm: str | None = Header(default=None)) -> dict[str, Any]:
    result = _service(request).purge_memory(memory_id, x_memory_purge_confirm, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(
            status.HTTP_409_CONFLICT if result.reason_code == "memory_purge_confirmation_required" else status.HTTP_403_FORBIDDEN,
            result.reason_code,
        )
    answer = cast(MemoryPurged, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}")
async def edit_memory(
    memory_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).edit_memory_controlled(
        memory_id, str(body.get("text", "")), auth_data[0].principal_id
    )
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryUpdated, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.post("/api/memory/{memory_id}/correct")
async def correct_memory(
    memory_id: str, request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    result = _service(request).correct_memory_controlled(
        memory_id, str(body.get("text", "")), str(body.get("reason", "")), auth_data[0].principal_id
    )
    if not result.ok:
        raise refusal(status.HTTP_409_CONFLICT, result.reason_code)
    answer = cast(MemoryCorrected, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}/search")
async def set_memory_search_enabled(
    memory_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).set_memory_search_enabled(
        memory_id, bool(body.get("enabled", True)), auth_data[0].principal_id
    )
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryUpdated, {"ok": True, **result.data})
    return serialize_dto(answer)


@router.put("/api/memory/{memory_id}/expiry")
async def set_memory_expiry(
    memory_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    raw_expires_at = body.get("expires_at")
    expires_at = None if raw_expires_at in (None, "") else str(raw_expires_at)
    result = _service(request).set_memory_expiry(memory_id, expires_at, auth_data[0].principal_id)
    if not result.ok:
        raise refusal(status.HTTP_403_FORBIDDEN, result.reason_code)
    answer = cast(MemoryUpdated, {"ok": True, **result.data})
    return serialize_dto(answer)
