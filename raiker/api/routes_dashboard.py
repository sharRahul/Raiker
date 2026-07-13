from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    AuthSessionRequest,
    CreateProjectRequest,
    SelectProjectRequest,
    SetModelAdvisorRequest,
    SetModelFallbackRequest,
    SetModelSelectionRequest,
    serialize_dto,
)
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


# ── Auth: first-run local token mint ──────────────────────────────────────────
# Loopback-only, human-owner bootstrap. Available ONLY before the first lock-screen
# account is registered; once any account exists, this fails closed and callers
# must authenticate through /api/auth/login (+ MFA). This preserves the owner
# bootstrap path without leaving an unauthenticated entry to a configured system.
@router.post("/api/auth/session")
async def mint_session(body: AuthSessionRequest, request: Request) -> dict[str, Any]:
    from raiker.storage.sqlite import SQLiteStore

    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    if SQLiteStore(ws).list_accounts():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "login_required"},
        )
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
    project_id: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    user_id = auth_data[1].delegated_by_user_id
    return serialize_dto(
        _service(request).list_sessions(limit=limit, project_id=project_id, user_id=user_id)
    )


@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_session(session_id, user_id=auth_data[1].delegated_by_user_id)
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
    project_id: str | None = None,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(
        _service(request).list_checkpoints(
            session_id=session_id, limit=limit, project_id=project_id
        )
    )


# ── Projects (web-app task 5: organizing scopes, governance-neutral) ──────────
@router.get("/api/projects")
async def list_projects(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return serialize_dto(_service(request).list_projects())


@router.post("/api/projects")
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Create a named project (human gate-manager only).

    The project root is derived server-side and always contained inside the
    workspace; a project grants no authority.
    """
    session, _principal = _auth_data
    result = _service(request).create_project(body.name, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/projects/selection")
async def select_project(
    body: SelectProjectRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Set (or clear) the active project (human gate-manager only).

    New sessions are stamped with the active project; selecting grants nothing.
    """
    session, _principal = _auth_data
    result = _service(request).select_project(body.project_id, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/projects/{project_id}")
async def get_project(
    project_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_project(project_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown project: {project_id}"
        )
    return serialize_dto(view)


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
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(
        _service(request).list_tasks(
            session_id=session_id, status=task_status, user_id=auth_data[1].delegated_by_user_id
        )
    )


@router.get("/api/models")
async def get_models(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return serialize_dto(_service(request).get_models())


@router.get("/api/connections")
async def get_connections(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Read-only status of governed service connectors (web-app task 4).

    Reports each connector's capability gate state, decision mode, whether the
    owner credential env is set, and whether its host is on the connector egress
    allowlist. Never reaches the network and never exposes a credential value.
    Enabling a connector is done through the capability-gate + decision-mode
    control plane (gate-manager only), not here.
    """
    session, _principal = _auth_data
    return serialize_dto(_service(request).get_connections(session.principal_id))


@router.get("/api/models/{profile_id}/provider-models")
async def list_provider_models(
    profile_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """On-demand listing of the models a provider serves for one profile.

    User-initiated read; provider policy (gates, egress allowlist, API key) is
    enforced before any network contact, and failures return an honest empty
    list — model names are never fabricated.
    """
    view = await _service(request).list_provider_models(profile_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model profile: {profile_id}"
        )
    return serialize_dto(view)


@router.put("/api/model-selection")
async def set_model_selection(
    body: SetModelSelectionRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Persist the operator's model selection (human gate-manager only).

    Placeholder profiles require a concrete model; provider policy is validated
    fail-closed before the selection is saved.
    """
    session, _principal = _auth_data
    result = await _service(request).set_model_selection(
        body.profile_id, body.model, session.principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/model-advisor")
async def set_model_advisor(
    body: SetModelAdvisorRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Persist (or clear) the user-owned advisor model profile (gate-manager only).

    Selecting an advisor grants nothing: the consult path is gated by the
    advisor_model_runtime capability, its decision mode (default ask), and
    provider policy (hosted/private gate + egress allowlist + key) per call.
    """
    session, _principal = _auth_data
    result = _service(request).set_model_advisor(body.profile_id, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/model-fallback")
async def set_model_fallback(
    body: SetModelFallbackRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Set the user-owned ordered model fallback sequence (human gate-manager only)."""
    session, _principal = _auth_data
    result = _service(request).set_model_fallback_sequence(body.profile_ids, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/diagnostics")
async def get_diagnostics(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    return serialize_dto(_service(request).get_diagnostics(principal.principal_id))
