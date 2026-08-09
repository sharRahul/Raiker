from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ModelOperationRequestBody,
    ModelReadinessCheckRequest,
    ModelSetupUpdateRequest,
)
from raiker.api.sessions import ApiSession
from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
from raiker.models.runtime_installers import RuntimeInstallerRegistry
from raiker.models.setup import ModelSetupState
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    workspace: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(workspace).authenticate(request)


def _service(request: Request) -> ModelReadinessService:
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return ModelReadinessService(store, probe=ProviderCatalogueProbe(store))


def _operation_service(request: Request) -> ModelOperationService:
    return ModelOperationService(SQLiteStore(request.app.state.workspace_root))  # type: ignore[attr-defined]


def _require_human(principal: Principal) -> None:
    if principal.principal_type != PrincipalType.HUMAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "human_principal_required"},
        )


@router.get("/api/model-readiness")
def list_model_readiness(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    items = SQLiteStore(request.app.state.workspace_root).list_model_readiness(  # type: ignore[attr-defined]
        session.principal_id
    )
    return {"items": [item.to_dict() for item in items]}


@router.post("/api/model-readiness/check")
async def check_model_readiness(
    body: ModelReadinessCheckRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    try:
        readiness = await _service(request).check_selected(
            session.principal_id,
            body.profile_id,
            body.model.strip(),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason_code": "unknown_model_profile"},
        ) from exc
    return readiness.to_dict()


@router.get("/api/model-setup")
def get_model_setup(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    return SQLiteStore(request.app.state.workspace_root).load_model_setup_state(  # type: ignore[attr-defined]
        session.principal_id
    ).to_dict()


@router.put("/api/model-setup")
def update_model_setup(
    body: ModelSetupUpdateRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    current = store.load_model_setup_state(session.principal_id)
    return store.save_model_setup_state(
        ModelSetupState(
            owner_principal_id=session.principal_id,
            status=body.status,
            step=body.step,
            path=body.path,
            selected_profile_id=body.selected_profile_id,
            selected_model=body.selected_model,
            created_at=current.created_at,
        )
    ).to_dict()


@router.post("/api/model-operations/preview")
def preview_model_operation(
    body: ModelOperationRequestBody,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = auth_data
    _require_human(principal)
    if body.kind != "install":
        return {"kind": body.kind, "target": body.target, "action": "review_operation", "confirmed": False}
    try:
        return RuntimeInstallerRegistry().preview(
            body.target, platform="windows" if sys.platform == "win32" else sys.platform
        ).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc)}) from exc


@router.get("/api/model-operations")
def list_model_operations(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    return {"items": [item.to_dict() for item in _operation_service(request).list(session.principal_id)]}


@router.post("/api/model-operations")
def start_model_operation(
    body: ModelOperationRequestBody,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    if not body.confirmed:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    return _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(
            kind=body.kind, target=body.target, confirmed=body.confirmed,
            source_url=body.source_url, destination=body.destination,
        ),
    ).to_dict()


def _operation_action(
    action: str,
    operation_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal],
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    service = _operation_service(request)
    try:
        if action == "cancel":
            return service.cancel(session.principal_id, operation_id).to_dict()
        if action == "retry":
            return service.retry(session.principal_id, operation_id).to_dict()
        return {"ok": service.cleanup(session.principal_id, operation_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc


@router.post("/api/model-operations/{operation_id}/cancel")
def cancel_model_operation(operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    return _operation_action("cancel", operation_id, request, auth_data)


@router.post("/api/model-operations/{operation_id}/retry")
def retry_model_operation(operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    return _operation_action("retry", operation_id, request, auth_data)


@router.delete("/api/model-operations/{operation_id}")
def cleanup_model_operation(operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    return _operation_action("cleanup", operation_id, request, auth_data)
