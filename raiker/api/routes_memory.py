"""Reliable memory controls (backlog item 3): user-facing surface over the
existing governed memory store.

These routes read/control the same store the memory_write/memory_forget tools
already use — no second memory system is created. List carries provenance,
scope, sensitivity, confidence, retention, and a pin flag. Forget reuses the
governed forget path (human-only). An incognito opt-out boundary withholds
approved project memory from the turn context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import serialize_dto
from raiker.api.sessions import ApiSession
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.runtime.authority.models import Principal
from raiker.runtime.source_provenance import SourceProvenanceService
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _service(request: Request) -> DashboardService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return DashboardService(ws)


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(ws).authenticate(request)


@router.get("/api/memory")
async def list_memories(
    request: Request,
    scope: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """List approved memories with governance metadata + pin state."""
    return serialize_dto(
        _service(request).list_memories(scope=scope, acting_principal_id=auth_data[0].principal_id)
    )


@router.get("/api/memory/proposals")
async def list_memory_proposals(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return _service(request).list_memory_proposals(auth_data[0].principal_id)


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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/memory/export")
async def export_memories(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).export_memories(auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.post("/api/memory/import")
async def import_memories(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    raw_memories = body.get("memories", [])
    memories = raw_memories if isinstance(raw_memories, list) else []
    result = _service(request).import_memories(memories, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.post("/api/memory/reconcile")
async def reconcile_memory_indexes(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Owner-started reconciliation for FTS and projection lifecycle state."""
    result = _service(request).reconcile_memory_indexes(auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.delete("/api/memory/{memory_id}")
async def forget_memory(
    memory_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Forget a memory through the governed path (human-only)."""
    result = _service(request).forget_memory_controlled(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "memory_not_found"},
        )
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    service = SourceProvenanceService(SQLiteStore(ws))
    excerpt = service.resolve(dict(memory.provenance), memory.text, principal_id)
    return {"ok": True, "memory_id": memory_id, **excerpt.to_dict()}


@router.get("/api/memory/{memory_id}/history")
async def get_memory_history(
    memory_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).memory_history(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/memory/{memory_id}/archive")
async def set_memory_archived(memory_id: str, request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    result = _service(request).set_memory_archived(memory_id, bool(body.get("archived", True)), auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.get("/api/memory/{memory_id}/purge-preview")
async def preview_memory_purge(memory_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    result = _service(request).preview_memory_purge(memory_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.delete("/api/memory/{memory_id}/purge")
async def purge_memory(memory_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth), x_memory_purge_confirm: str | None = Header(default=None)) -> dict[str, Any]:
    result = _service(request).purge_memory(memory_id, x_memory_purge_confirm, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT if result.reason_code == "memory_purge_confirmation_required" else status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.post("/api/memory/{memory_id}/correct")
async def correct_memory(
    memory_id: str, request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    result = _service(request).correct_memory_controlled(
        memory_id, str(body.get("text", "")), str(body.get("reason", "")), auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}
