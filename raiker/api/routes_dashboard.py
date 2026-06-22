from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import AuthSessionRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.control.dashboard import AuthSessionView, DashboardService
from raiker.runtime.authority.models import Principal

router = APIRouter()


def _service(request: Request) -> DashboardService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return DashboardService(ws)


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(ws).authenticate(request)


# ── Auth: local token mint (unauthenticated; loopback-only, human owner only) ──
@router.post("/api/auth/session")
async def mint_session(body: AuthSessionRequest, request: Request) -> dict[str, Any]:
    service = _service(request)
    result = service.mint_owner_session(body.as_principal)
    if not isinstance(result, AuthSessionView):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return serialize_dto(result)


# ── Read-only governed views (Bearer required) ────────────────────────────────
@router.get("/api/sessions")
async def list_sessions(
    request: Request,
    limit: int = 50,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_sessions(limit=limit))


@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_session(session_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown session: {session_id}")
    return serialize_dto(view)


@router.get("/api/turns/{turn_id}")
async def get_turn(
    turn_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_turn(turn_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown turn: {turn_id}")
    return serialize_dto(view)


@router.get("/api/events")
async def list_events(
    request: Request,
    session_id: str | None = None,
    turn_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(
        _service(request).list_events(
            session_id=session_id, turn_id=turn_id, event_type=event_type, limit=limit
        )
    )


@router.get("/api/checkpoints")
async def list_checkpoints(
    request: Request,
    session_id: str | None = None,
    limit: int = 50,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_checkpoints(session_id=session_id, limit=limit))


@router.get("/api/checkpoints/{checkpoint_id}")
async def get_checkpoint(
    checkpoint_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_checkpoint(checkpoint_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown checkpoint: {checkpoint_id}"
        )
    return serialize_dto(view)


@router.get("/api/tasks")
async def list_tasks(
    request: Request,
    session_id: str | None = None,
    task_status: str | None = None,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_tasks(session_id=session_id, status=task_status))


@router.get("/api/models")
async def get_models(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return serialize_dto(_service(request).get_models())


@router.get("/api/diagnostics")
async def get_diagnostics(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    return serialize_dto(_service(request).get_diagnostics(principal.principal_id))
