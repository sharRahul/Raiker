from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.schemas import SetupBackupRequest, SetupUpdateRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.models import SetupBackupCreated, SetupSystemReadiness, SetupVerification
from raiker.app.backup import create_local_backup
from raiker.contracts.ids import utc_now
from raiker.models.setup import SetupState
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


@router.get("/api/setup")
def get_setup(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, _ = auth_data
    return serialize_dto(
        SQLiteStore(request.app.state.workspace_root).load_setup_state(session.principal_id)  # type: ignore[attr-defined]
    )


@router.put("/api/setup")
def update_setup(
    body: SetupUpdateRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _ = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    current = store.load_setup_state(session.principal_id)
    privacy_ack = current.privacy_acknowledged_at
    if body.stage in {"backup", "finish"} and body.privacy_mode and not privacy_ack:
        privacy_ack = utc_now()
    return serialize_dto(store.save_setup_state(
        SetupState(
            owner_principal_id=session.principal_id,
            status=body.status,
            stage=body.stage,
            selected_profile_id=body.selected_profile_id,
            selected_model=body.selected_model,
            model_deferred=body.model_deferred,
            privacy_mode=body.privacy_mode,
            privacy_acknowledged_at=privacy_ack,
            backup_mode=body.backup_mode,
            backup_target=body.backup_target,
            backup_verified_at=current.backup_verified_at,
            background_service_enabled=body.background_service_enabled,
            created_at=current.created_at,
        )
    ))


@router.post("/api/setup/backup/create")
def create_setup_backup(
    body: SetupBackupRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _ = auth_data
    try:
        result = create_local_backup(request.app.state.workspace_root, body.target)  # type: ignore[attr-defined]
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason_code": "backup_target_unwritable"},
        ) from exc
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    current = store.load_setup_state(session.principal_id)
    saved = store.save_setup_state(
        SetupState(
            **(
                current.to_dict()
                | {
                    "backup_mode": "local",
                    "backup_target": str(Path(body.target).expanduser().resolve()),
                    "backup_verified_at": result.created_at,
                    "updated_at": None,
                }
            )
        )
    )
    answer: SetupBackupCreated = {"ok": True, "path": str(result.path), "setup": saved}
    return serialize_dto(answer)


@router.get("/api/setup/system")
def get_setup_system(
    request: Request, _auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """DIST-05 — what this machine can do. Local measurements only; no egress."""
    from raiker.app.system_check import system_readiness

    workspace = Path(request.app.state.workspace_root)  # type: ignore[attr-defined]
    answer = cast(SetupSystemReadiness, system_readiness(workspace))
    return serialize_dto(answer)


@router.post("/api/setup/verify")
def verify_setup(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """DIST-06 — whether each mandatory component works, checked from inside.

    Changes nothing and grants nothing: it reads the store, the permission
    registry and the packaged components. A model request is the wizard's own
    separate act (the model readiness check), so this needs no network.
    """
    from raiker.app.system_check import installation_checks

    session, _ = auth_data
    state = request.app.state
    answer = cast(
        SetupVerification,
        installation_checks(
            Path(state.workspace_root),
            principal_id=session.principal_id,
            ui_dir=getattr(state, "instance_ui_dir", None),
            executor_registry=getattr(state, "executor_registry", None),
        ),
    )
    return serialize_dto(answer)
