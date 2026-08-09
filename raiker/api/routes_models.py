from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    HuggingFaceCredentialRequest,
    HuggingFaceSelectionRequest,
    ModelConversionRequestBody,
    ModelLibraryRootRequest,
    ModelOperationRequestBody,
    ModelReadinessCheckRequest,
    ModelSetupUpdateRequest,
)
from raiker.api.sessions import ApiSession
from raiker.models.conversion import ConversionRefused, ModelConversionService
from raiker.models.huggingface import HfVariant, HuggingFaceAccessError, HuggingFaceService
from raiker.models.library import ModelLibraryService
from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
from raiker.models.runtime_installers import RuntimeInstallerRegistry
from raiker.models.setup import ModelSetupState
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.connector_ecosystem import ConnectorVault
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


def _library_service(request: Request) -> ModelLibraryService:
    return ModelLibraryService(SQLiteStore(request.app.state.workspace_root))  # type: ignore[attr-defined]


def _hugging_face_service(request: Request) -> HuggingFaceService:
    root = Path(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return HuggingFaceService(cache_dir=root / ".raiker" / "models" / "huggingface")


def _hugging_face_token(request: Request, owner: str) -> str | None:
    credential = ConnectorVault(SQLiteStore(request.app.state.workspace_root)).get(
        owner, "huggingface"
    )  # type: ignore[attr-defined]
    return credential.get("token") if credential else None


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
    return (
        SQLiteStore(request.app.state.workspace_root)
        .load_model_setup_state(  # type: ignore[attr-defined]
            session.principal_id
        )
        .to_dict()
    )


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
        return {
            "kind": body.kind,
            "target": body.target,
            "action": "review_operation",
            "confirmed": False,
        }
    try:
        return (
            RuntimeInstallerRegistry()
            .preview(body.target, platform="windows" if sys.platform == "win32" else sys.platform)
            .to_dict()
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc)}) from exc


@router.get("/api/model-operations")
def list_model_operations(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    return {
        "items": [item.to_dict() for item in _operation_service(request).list(session.principal_id)]
    }


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
    return (
        _operation_service(request)
        .start(
            session.principal_id,
            ModelOperationRequest(
                kind=body.kind,
                target=body.target,
                confirmed=body.confirmed,
                source_url=body.source_url,
                destination=body.destination,
            ),
        )
        .to_dict()
    )


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
def cancel_model_operation(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    return _operation_action("cancel", operation_id, request, auth_data)


@router.post("/api/model-operations/{operation_id}/retry")
def retry_model_operation(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    return _operation_action("retry", operation_id, request, auth_data)


@router.delete("/api/model-operations/{operation_id}")
def cleanup_model_operation(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    return _operation_action("cleanup", operation_id, request, auth_data)


@router.get("/api/model-library")
def get_model_library(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    service = _library_service(request)
    return {
        "roots": [{"path": path} for path in service.roots(session.principal_id)],
        "models": [model.to_dict() for model in service.list_models(session.principal_id)],
    }


@router.post("/api/model-library/roots")
def add_model_library_root(
    body: ModelLibraryRootRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    try:
        path = _library_service(request).add_root(session.principal_id, Path(body.path))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc
    return {"ok": True, "path": path}


@router.delete("/api/model-library/roots")
def remove_model_library_root(
    body: ModelLibraryRootRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    return {"ok": _library_service(request).remove_root(session.principal_id, Path(body.path))}


@router.post("/api/model-library/rescan")
def rescan_model_library(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    models = _library_service(request).rescan(session.principal_id)
    return {"ok": True, "models": [model.to_dict() for model in models]}


@router.post("/api/model-library/{model_id:path}/deploy")
def deploy_local_model(
    model_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    model = next(
        (
            item
            for item in _library_service(request).list_models(session.principal_id)
            if item.model_id == model_id
        ),
        None,
    )
    if model is None or not model.complete:
        raise HTTPException(status_code=409, detail={"reason_code": "local_model_not_deployable"})
    return (
        _operation_service(request)
        .start(
            session.principal_id,
            ModelOperationRequest(
                kind="deploy", target=model.model_id, confirmed=True, destination=model.primary_path
            ),
        )
        .to_dict()
    )


@router.put("/api/hugging-face/credential")
def save_hugging_face_credential(
    body: HuggingFaceCredentialRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, bool]:
    session, principal = auth_data
    _require_human(principal)
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=422, detail={"reason_code": "credential_empty"})
    ConnectorVault(SQLiteStore(request.app.state.workspace_root)).put(
        session.principal_id, "huggingface", {"token": token}
    )  # type: ignore[attr-defined]
    return {"configured": True}


@router.get("/api/hugging-face/search")
def search_hugging_face(
    query: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    if not query.strip():
        raise HTTPException(status_code=422, detail={"reason_code": "hugging_face_query_required"})
    try:
        items = _hugging_face_service(request).search(
            query, token=_hugging_face_token(request, session.principal_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc
    except HuggingFaceAccessError as exc:
        raise HTTPException(
            status_code=503, detail={"reason_code": exc.code, "repository_url": exc.repository_url}
        ) from exc
    return {"items": [item.to_dict() for item in items]}


@router.get("/api/hugging-face/{owner}/{repository}/variants")
def list_hugging_face_variants(
    owner: str,
    repository: str,
    request: Request,
    revision: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    repo_id = f"{owner}/{repository}"
    try:
        items = _hugging_face_service(request).variants(
            repo_id, revision=revision, token=_hugging_face_token(request, session.principal_id)
        )
    except (ValueError, HuggingFaceAccessError) as exc:
        code = exc.code if isinstance(exc, HuggingFaceAccessError) else str(exc)
        link = (
            exc.repository_url
            if isinstance(exc, HuggingFaceAccessError)
            else f"https://huggingface.co/{repo_id}"
        )
        raise HTTPException(
            status_code=409, detail={"reason_code": code, "repository_url": link}
        ) from exc
    return {"items": [item.to_dict() for item in items]}


def _variant_from_body(body: HuggingFaceSelectionRequest) -> HfVariant:
    return HfVariant(
        body.repo_id, body.revision, tuple(body.files), "gguf", None, 0, 0, False, None, True
    )


def _resolve_hugging_face_selection(
    body: HuggingFaceSelectionRequest, request: Request, owner: str
) -> HfVariant:
    requested = _variant_from_body(body)
    variants = _hugging_face_service(request).variants(
        body.repo_id, revision=body.revision, token=_hugging_face_token(request, owner)
    )
    match = next(
        (
            item
            for item in variants
            if item.revision == requested.revision
            and item.files == requested.files
            and item.complete
        ),
        None,
    )
    if match is None:
        raise ValueError("hugging_face_selection_changed")
    return match


@router.post("/api/hugging-face/download/preview")
def preview_hugging_face_download(
    body: HuggingFaceSelectionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    try:
        variant = _resolve_hugging_face_selection(body, request, session.principal_id)
        return (
            _hugging_face_service(request)
            .dry_run(
                body.repo_id, variant, token=_hugging_face_token(request, session.principal_id)
            )
            .to_dict()
        )
    except (ValueError, HuggingFaceAccessError) as exc:
        code = exc.code if isinstance(exc, HuggingFaceAccessError) else str(exc)
        raise HTTPException(status_code=422, detail={"reason_code": code}) from exc


@router.post("/api/hugging-face/download")
def download_hugging_face_model(
    body: HuggingFaceSelectionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    if not body.confirmed or not body.destination:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    destination = Path(body.destination).resolve()
    roots = [Path(root).resolve() for root in _library_service(request).roots(session.principal_id)]
    if not any(destination == root or root in destination.parents for root in roots):
        raise HTTPException(
            status_code=422, detail={"reason_code": "destination_not_in_model_library"}
        )
    operation = _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(
            kind="download",
            target=f"{body.repo_id}@{body.revision}",
            confirmed=True,
            source_url=f"https://huggingface.co/{body.repo_id}",
            destination=str(destination),
        ),
    )
    operations = _operation_service(request)
    try:
        variant = _resolve_hugging_face_selection(body, request, session.principal_id)
        operations.running(session.principal_id, operation.operation_id, phase="downloading")
        _hugging_face_service(request).download(
            body.repo_id,
            variant,
            destination,
            token=_hugging_face_token(request, session.principal_id),
        )
        _library_service(request).rescan(session.principal_id)
        return operations.complete(session.principal_id, operation.operation_id).to_dict()
    except Exception as exc:
        operations.fail(
            session.principal_id, operation.operation_id, code="hugging_face_download_failed"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "reason_code": "hugging_face_download_failed",
                "operation_id": operation.operation_id,
            },
        ) from exc


def _require_approved_conversion_paths(
    request: Request, owner: str, source: Path, output: Path
) -> None:
    roots = [Path(root).resolve() for root in _library_service(request).roots(owner)]
    source = source.resolve()
    output = output.resolve()
    if not any(source == root or root in source.parents for root in roots):
        raise HTTPException(status_code=422, detail={"reason_code": "source_not_in_model_library"})
    if not any(output == root or root in output.parents for root in roots):
        raise HTTPException(status_code=422, detail={"reason_code": "output_not_in_model_library"})


@router.post("/api/model-conversion/preview")
def preview_model_conversion(
    body: ModelConversionRequestBody,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    source, output = Path(body.source), Path(body.output)
    _require_approved_conversion_paths(request, session.principal_id, source, output)
    try:
        return (
            ModelConversionService()
            .preview(source, output, body.revision, body.quantization)
            .to_dict()
        )
    except ConversionRefused as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc


def _run_model_conversion(
    workspace: Path, owner: str, operation_id: str, body: ModelConversionRequestBody
) -> None:
    operations = ModelOperationService(SQLiteStore(workspace))
    try:
        operations.running(owner, operation_id, phase="converting")
        service = ModelConversionService()
        preview = service.preview(
            Path(body.source), Path(body.output), body.revision, body.quantization
        )
        service.convert(preview)
        operations.complete(owner, operation_id)
        ModelLibraryService(SQLiteStore(workspace)).rescan(owner)
    except Exception:
        operations.fail(owner, operation_id, code="model_conversion_failed")


@router.post("/api/model-conversion")
def start_model_conversion(
    body: ModelConversionRequestBody,
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    if not body.confirmed:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    source, output = Path(body.source), Path(body.output)
    _require_approved_conversion_paths(request, session.principal_id, source, output)
    try:
        ModelConversionService().preview(source, output, body.revision, body.quantization)
    except ConversionRefused as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc
    operation = _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(
            kind="convert",
            target=f"{source.name}@{body.revision}",
            confirmed=True,
            destination=str(output),
        ),
    )
    background.add_task(
        _run_model_conversion,
        Path(request.app.state.workspace_root),
        session.principal_id,
        operation.operation_id,
        body,
    )
    return operation.to_dict()
