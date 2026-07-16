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
