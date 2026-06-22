from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ActivateRuntimeModeRequest,
    DisableCapabilityRequest,
    DisableRuntimeModeRequest,
    SetCapabilityStateRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.control.service import RuntimeControlService
from raiker.runtime.authority.models import Principal
from raiker.runtime.executors.registry import ExecutorRegistry

router = APIRouter()


def _get_auth(request: Request) -> AuthMiddleware:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(ws)


def _get_service(request: Request) -> RuntimeControlService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    registry: ExecutorRegistry | None = getattr(request.app.state, "executor_registry", None)
    return RuntimeControlService(ws, executor_registry=registry)


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return _get_auth(request).authenticate(request)


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/runtime-mode")
async def get_runtime_mode(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    service = _get_service(request)
    return serialize_dto(service.get_runtime_mode())


@router.post("/api/runtime-mode/activate")
async def activate_runtime_mode(
    body: ActivateRuntimeModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.activate_runtime_mode(body.mode_name, session.principal_id, body.reason)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code or "denied"},
        )
    return {"ok": True, "mode_name": body.mode_name}


@router.post("/api/runtime-mode/disable")
async def disable_runtime_mode(
    body: DisableRuntimeModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.disable_runtime_mode(session.principal_id, body.reason)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code or "denied"},
        )
    return {"ok": True}


@router.get("/api/capability-gates")
async def list_capability_gates(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    session, principal = _auth_data
    service = _get_service(request)
    gates = service.list_capability_gates(principal.principal_id)
    return serialize_dto(gates)


@router.get("/api/capability-gates/{capability}")
async def get_capability_gate(
    capability: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = _auth_data
    service = _get_service(request)
    gate = service.get_capability_gate(capability, principal.principal_id)
    if gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown capability: {capability}")
    return serialize_dto(gate)


@router.post("/api/capability-gates/{capability}/set")
async def set_capability_state(
    capability: str,
    body: SetCapabilityStateRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.set_capability_state(
        capability,
        body.target_state,
        session.principal_id,
        body.reason,
        confirmation_token=body.confirmation_token,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code or "denied"},
        )
    return {"ok": True, "capability": capability, "target_state": body.target_state}


@router.post("/api/capability-gates/{capability}/disable")
async def disable_capability(
    capability: str,
    body: DisableCapabilityRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.disable_capability(capability, session.principal_id, body.reason)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code or "denied"},
        )
    return {"ok": True, "capability": capability}


@router.get("/api/runtime-readiness")
async def get_runtime_readiness(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = _auth_data
    service = _get_service(request)
    readiness = service.get_runtime_readiness(principal.principal_id)
    return serialize_dto(readiness)
