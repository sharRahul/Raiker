from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import ModelReadinessCheckRequest, ModelSetupUpdateRequest
from raiker.api.sessions import ApiSession
from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
from raiker.models.setup import ModelSetupState
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    workspace: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(workspace).authenticate(request)


def _service(request: Request) -> ModelReadinessService:
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return ModelReadinessService(store, probe=ProviderCatalogueProbe(store))


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
