from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import ValidationError

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    HuggingFaceCredentialRequest,
    HuggingFaceSelectionRequest,
    LocalModelDeployRequest,
    ModelConversionRequestBody,
    ModelLibraryRootRequest,
    ModelOperationRequestBody,
    ModelReadinessCheckRequest,
    ModelSetupUpdateRequest,
    OllamaPullRequestBody,
    SurfaceModelDefaultRequest,
)
from raiker.api.sessions import ApiSession
from raiker.models import local_presence
from raiker.models.conversion import (
    ConversionRefused,
    ModelConversionService,
    conversion_artifacts,
)
from raiker.models.huggingface import HfVariant, HuggingFaceAccessError, HuggingFaceService
from raiker.models.library import ModelLibraryService
from raiker.models.local_operations import (
    ModelOperation,
    ModelOperationRequest,
    ModelOperationService,
)
from raiker.models.local_runtime import LOCAL_SLOTS, ManagedLlamaRuntime, slot_for_profile
from raiker.models.mlx_runtime import MLX_SLOTS, ManagedMlxRuntime
from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
from raiker.models.runtime_installers import RuntimeInstallerRegistry
from raiker.models.setup import ModelSetupState
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()
_OLLAMA_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


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
    return HuggingFaceService(
        cache_dir=internal_io_path(root / ".raiker" / "models" / "huggingface")
    )


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


# The work surfaces that may hold their own default model. Chat and Build are
# conversational surfaces; Tasks and Schedule capture the model onto the task
# they create, so a scheduled run keeps the model chosen when it was scheduled.
SURFACES = ("chat", "build", "tasks", "schedule")


@router.get("/api/surface-models")
def get_surface_models(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return {
        "surfaces": {
            surface: {"profile_id": profile_id, "model": model}
            for surface, profile_id, model in store.list_surface_model_defaults(
                session.principal_id
            )
        }
    }


@router.put("/api/surface-models")
def set_surface_model(
    body: SurfaceModelDefaultRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Choose where one surface's model picker starts.

    This is a preference. It never grants readiness: the turn a surface submits
    still names its exact profile and model, and the gate judges that pair on
    its own evidence.
    """
    session, principal = auth_data
    _require_human(principal)
    surface = body.surface.strip()
    if surface not in SURFACES:
        raise HTTPException(status_code=422, detail={"reason_code": "unknown_surface"})
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    profile_id = body.profile_id.strip()
    if not profile_id:
        store.clear_surface_model_default(session.principal_id, surface)
        return {"ok": True, "surface": surface, "profile_id": "", "model": ""}
    from raiker.models.registry import ModelProfileRegistry

    try:
        profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
    except Exception as exc:  # noqa: BLE001 — an unknown profile fails closed
        raise HTTPException(
            status_code=422, detail={"reason_code": f"unknown_profile:{profile_id}"}
        ) from exc
    model = body.model.strip() or profile.model
    if not model or "<" in model:
        raise HTTPException(
            status_code=422, detail={"reason_code": f"model_required_for_profile:{profile_id}"}
        )
    store.save_surface_model_default(session.principal_id, surface, profile.profile_id, model)
    return {"ok": True, "surface": surface, "profile_id": profile.profile_id, "model": model}


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


@router.get("/api/local-runtimes")
def list_local_runtimes(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What local model runtimes were last found on this machine (BUG-270).

    A pure row read. The detection that wrote those rows is a PATH lookup and
    never a connection, so neither this route nor the dashboard read it feeds
    can contact a provider (FIXED-357).
    """
    _session, principal = auth_data
    _require_human(principal)
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return {
        "runtimes": [
            {
                "runtime": result.runtime,
                "present": result.present,
                "executable": result.executable,
                "detected_at": result.detected_at,
            }
            for result in sorted(local_presence.cached(store).values(), key=lambda r: r.runtime)
        ]
    }


@router.post("/api/local-runtimes/detect")
def detect_local_runtimes(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Look again, now — the owner just installed something (BUG-270).

    Detection is cached for an hour so a status read costs a row read rather
    than a PATH scan. That cache is exactly wrong in the one minute after an
    owner installs Ollama, so this forces a fresh look and nothing else.
    """
    _session, principal = auth_data
    _require_human(principal)
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    return {
        "runtimes": [
            {
                "runtime": result.runtime,
                "present": result.present,
                "executable": result.executable,
                "detected_at": result.detected_at,
            }
            for result in sorted(
                local_presence.detect(store, force=True).values(), key=lambda r: r.runtime
            )
        ]
    }


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


def _dispatch_operation(
    background: BackgroundTasks,
    request: Request,
    owner: str,
    operation: ModelOperation,
) -> None:
    """Reconstruct and schedule the worker one re-queued operation needs.

    Dispatch is by *kind*, from the typed payload persisted when the operation
    started. Nothing secret was stored: a Hugging Face retry re-reads the token
    from the vault, and a pull or a conversion never held one.
    """
    workspace = Path(request.app.state.workspace_root)  # type: ignore[attr-defined]
    payload = operation.payload()
    operation_id = operation.operation_id
    if operation.kind == "pull":
        background.add_task(
            _pull_ollama_model, workspace, owner, operation_id, str(payload.get("model", ""))
        )
        return
    if operation.kind == "convert":
        try:
            body = ModelConversionRequestBody(
                source=str(payload.get("source", "")),
                output=str(payload.get("output", "")),
                revision=str(payload.get("revision", "")),
                quantization=payload.get("quantization"),  # type: ignore[arg-type]
                confirmed=True,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail={"reason_code": "operation_payload_invalid"}
            ) from exc
        background.add_task(_run_model_conversion, workspace, owner, operation_id, body)
        return
    if operation.kind == "deploy":
        framework = str(payload.get("framework", "llama.cpp"))
        if framework == "mlx":
            background.add_task(
                _run_mlx_deployment,
                workspace,
                owner,
                operation_id,
                Path(str(payload.get("model_path", ""))),
                tuple(Path(path) for path in _library_service(request).roots(owner)),
                request.app.state.managed_mlx_runtime,  # type: ignore[attr-defined]
                payload.get("profile_id"),
            )
            return
        arguments = (
            workspace,
            owner,
            operation_id,
            Path(str(payload.get("model_path", ""))),
            tuple(Path(path) for path in _library_service(request).roots(owner)),
            request.app.state.managed_llama_runtime,  # type: ignore[attr-defined]
        )
        if payload.get("profile_id"):
            background.add_task(_run_local_deployment, *arguments, payload["profile_id"])
        else:
            background.add_task(_run_local_deployment, *arguments)
        return
    if operation.kind == "download":
        background.add_task(
            _run_hugging_face_download,
            workspace,
            owner,
            operation_id,
            dict(payload),
            _hugging_face_token(request, owner),
            _hugging_face_service(request),
        )


def _run_hugging_face_download(
    workspace: Path,
    owner: str,
    operation_id: str,
    payload: dict[str, Any],
    token: str | None,
    service: HuggingFaceService,
) -> None:
    """Run one Hugging Face snapshot download from its persisted payload.

    The only downloader: the first attempt and every retry are this worker
    (GCR-22), so cancellation, failure and completion mean the same thing
    whichever one the owner is watching.
    """
    operations = ModelOperationService(SQLiteStore(workspace))
    try:
        if operations.running(owner, operation_id, phase="downloading").state != "running":
            # Cancelled before this worker could claim it, or already settled by
            # another. Either way it is not this worker's job any more.
            return
        repo_id = str(payload.get("repo_id", ""))
        revision = str(payload.get("revision", ""))
        files = tuple(part for part in str(payload.get("variant", "")).split(",") if part)
        destination = Path(str(payload.get("destination", "")))
        if not repo_id or not revision or not files or not destination.name:
            raise ValueError("hugging_face_retry_payload_incomplete")
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
        variant = next(
            (
                item
                for item in service.variants(repo_id, revision=revision, token=token)
                if item.revision == revision and item.files == files and item.complete
            ),
            None,
        )
        if variant is None:
            raise ValueError("hugging_face_selection_changed")
        service.download(repo_id, variant, destination, token=token)
        ModelLibraryService(SQLiteStore(workspace)).rescan(owner)
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
        operations.complete(owner, operation_id)
    except Exception:  # noqa: BLE001 - durable operation exposes only a bounded code
        operations.fail(owner, operation_id, code="hugging_face_download_failed")


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
    operation_id: str,
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Re-queue a failed operation **and dispatch its worker again** (BUG-75).

    Retry used to reset the durable row to `queued` and stop there, so an
    operation that had failed sat honestly recorded and permanently idle. The
    typed payload persisted at start is what makes the real dispatch possible:
    the same job, reconstructed by kind, with the credential re-read from the
    vault rather than remembered.
    """
    session, principal = auth_data
    _require_human(principal)
    service = _operation_service(request)
    try:
        service.require(session.principal_id, operation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc
    try:
        # The re-queue *is* the claim (GCR-21): only one of two simultaneous
        # presses can take a terminal operation, so only one worker is
        # dispatched below.
        requeued = service.retry(session.principal_id, operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc
    _dispatch_operation(background, request, session.principal_id, requeued)
    return requeued.to_dict()


@router.get("/api/model-operations/{operation_id}/partial-files")
def preview_partial_files(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """What a confirmed cleanup would delete: the exact approved path and bytes."""
    session, principal = auth_data
    _require_human(principal)
    try:
        return _operation_service(request).partial_files(session.principal_id, operation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc


@router.post("/api/model-operations/{operation_id}/delete-partial-files")
def delete_partial_files(
    operation_id: str,
    request: Request,
    confirmed: bool = False,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Delete the incomplete files an abandoned operation left behind.

    Separate from **Clear record**, which stays metadata-only: removing bytes
    from disk is its own decision, so it takes its own confirmation and names
    every exact path and the total size first. Only the paths the operation
    recorded as its own are removed (GCR-19) — never the library directory it
    wrote them into — and each must still resolve *strictly inside* one of the
    owner's approved model-library roots. Anything else is refused rather than
    deleted.
    """
    session, principal = auth_data
    _require_human(principal)
    if not confirmed:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    service = _operation_service(request)
    try:
        operation = service.require(session.principal_id, operation_id)
        summary = service.partial_files(session.principal_id, operation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc
    paths = [str(item) for item in summary.get("paths") or []]
    if not paths or not summary.get("exists"):
        return {"ok": False, "reason_code": "no_partial_files", **summary}
    # Re-read what this operation owns rather than trusting the summary: the
    # deletion set is the recorded one, checked again at the moment of deletion.
    owned = {str(Path(item).resolve()) for item in operation.cleanup_targets()}
    roots = [Path(root).resolve() for root in _library_service(request).roots(session.principal_id)]
    targets: list[Path] = []
    for path in paths:
        target = Path(path).resolve()
        # `root in target.parents` and not `target == root`: an approved root is
        # the boundary of the check, never a thing the check permits deleting.
        if str(target) not in owned or not any(root in target.parents for root in roots):
            raise HTTPException(
                status_code=422, detail={"reason_code": "destination_not_in_model_library"}
            )
        targets.append(target)
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    _library_service(request).rescan(session.principal_id)
    return {"ok": True, **summary}


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


def _run_local_deployment(
    workspace: Path,
    owner: str,
    operation_id: str,
    model_path: Path,
    approved_roots: tuple[Path, ...],
    runtime: ManagedLlamaRuntime,
    profile_id: str | None = None,
) -> None:
    operations = ModelOperationService(SQLiteStore(workspace))
    started_slot: str | None = None
    try:
        if operations.running(owner, operation_id, phase="starting_llama_cpp").state != "running":
            return
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
        executable = shutil.which("llama-server")
        if executable is None:
            raise RuntimeError("llama_server_missing")
        # Deploying a second model adds a server rather than replacing the
        # first, so the slot — and therefore the port, the served name, and the
        # profile the owner will select — is decided by the runtime.
        started = runtime.start(
            model_path,
            executable=Path(executable),
            approved_roots=approved_roots,
            profile_id=profile_id,
        )
        started_slot = started.slot
        slot = slot_for_profile(started.slot) or LOCAL_SLOTS[0]
        origin = f"http://127.0.0.1:{slot.port}"
        deadline = time.monotonic() + 30
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                try:
                    health = client.get(f"{origin}/health")
                    models = client.get(f"{origin}/v1/models")
                    ids = [str(item.get("id")) for item in models.json().get("data", [])]
                    if health.is_success and models.is_success and slot.alias in ids:
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                # The readiness wait is the long part of a deploy, so it is where
                # Cancel has to land. `RuntimeError` unwinds into the handler
                # below, which stops the slot this deployment started.
                if operations.cancel_requested(owner, operation_id):
                    raise RuntimeError("local_model_deploy_cancelled")
                time.sleep(0.2)
            else:
                raise RuntimeError("llama_server_not_ready")
        store = SQLiteStore(workspace)
        store.save_configured_model(owner, slot.profile_id, slot.alias)
        store.invalidate_model_readiness(
            owner,
            slot.profile_id,
            reason_code="local_runtime_deployed",
        )
        operations.complete(owner, operation_id)
    except Exception as exc:  # noqa: BLE001 - durable operation exposes only a bounded code
        # Only this deployment's own slot is stopped. Another model already
        # serving a surface must not be torn down by an unrelated failure, which
        # is exactly what a bare `stop()` would now do.
        if started_slot is not None:
            runtime.stop(started_slot)
        if str(exc) == "local_model_deploy_cancelled":
            operations.cancelled(owner, operation_id)
        else:
            operations.fail(owner, operation_id, code="local_model_deploy_failed")


@router.post("/api/model-library/{model_id:path}/deploy")
def deploy_local_model(
    model_id: str,
    background: BackgroundTasks,
    request: Request,
    body: LocalModelDeployRequest | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
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
    if model.format != "gguf":
        raise HTTPException(status_code=409, detail={"reason_code": "local_model_wrong_format"})
    profile_id = body.profile_id if body is not None else None
    if profile_id is not None and profile_id not in {slot.profile_id for slot in LOCAL_SLOTS}:
        raise HTTPException(status_code=422, detail={"reason_code": "unknown_local_runtime_slot"})
    operation = (
        _operation_service(request)
        .start(
            session.principal_id,
            ModelOperationRequest(
                kind="deploy", target=model.model_id, confirmed=True, destination=model.primary_path
            ),
            payload={
                "model_id": model.model_id,
                "model_path": model.primary_path,
                "framework": "llama.cpp",
                "profile_id": profile_id,
            },
        )
        .to_dict()
    )
    roots = tuple(Path(path) for path in _library_service(request).roots(session.principal_id))
    arguments = (
        Path(request.app.state.workspace_root),
        session.principal_id,
        operation["operation_id"],
        Path(model.primary_path),
        roots,
        request.app.state.managed_llama_runtime,
    )
    if profile_id is not None:
        background.add_task(_run_local_deployment, *arguments, profile_id)
    else:
        background.add_task(_run_local_deployment, *arguments)
    return operation


def _run_mlx_deployment(
    workspace: Path,
    owner: str,
    operation_id: str,
    model_path: Path,
    approved_roots: tuple[Path, ...],
    runtime: ManagedMlxRuntime,
    profile_id: str | None = None,
) -> None:
    operations = ModelOperationService(SQLiteStore(workspace))
    started_slot: str | None = None
    try:
        if operations.running(owner, operation_id, phase="starting_mlx").state != "running":
            return
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
        if sys.platform != "darwin":
            raise RuntimeError("mlx_requires_apple_silicon")
        executable = shutil.which("mlx_lm.server") or shutil.which("mlx_lm")
        if executable is None:
            raise RuntimeError("mlx_lm_server_missing")
        started = runtime.start(
            model_path,
            executable=Path(executable),
            profile_id=profile_id,
            approved_roots=approved_roots,
        )
        started_slot = started.slot
        slot = next(item for item in MLX_SLOTS if item.profile_id == started.slot)
        origin = f"http://127.0.0.1:{slot.port}"
        served_model: str | None = None
        deadline = time.monotonic() + 60
        with httpx.Client(timeout=2.0, trust_env=False) as client:
            while time.monotonic() < deadline:
                try:
                    response = client.get(f"{origin}/v1/models")
                    ids = [str(item.get("id")) for item in response.json().get("data", [])]
                    if response.is_success and ids:
                        served_model = ids[0]
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                if operations.cancel_requested(owner, operation_id):
                    raise RuntimeError("local_model_deploy_cancelled")
                time.sleep(0.2)
            else:
                raise RuntimeError("mlx_server_not_ready")
        store = SQLiteStore(workspace)
        store.save_configured_model(owner, slot.profile_id, served_model or str(model_path))
        store.invalidate_model_readiness(
            owner, slot.profile_id, reason_code="local_runtime_deployed"
        )
        operations.complete(owner, operation_id)
    except Exception as exc:  # noqa: BLE001
        if started_slot is not None:
            runtime.stop(started_slot)
        if str(exc) == "local_model_deploy_cancelled":
            operations.cancelled(owner, operation_id)
        else:
            operations.fail(owner, operation_id, code="local_mlx_deploy_failed")


@router.post("/api/model-library/{model_id:path}/deploy-mlx")
def deploy_mlx_model(
    model_id: str,
    background: BackgroundTasks,
    request: Request,
    body: LocalModelDeployRequest | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
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
    if model is None or not model.complete or model.format != "mlx":
        raise HTTPException(status_code=409, detail={"reason_code": "local_mlx_not_deployable"})
    profile_id = body.profile_id if body is not None else None
    if profile_id is not None and profile_id not in {slot.profile_id for slot in MLX_SLOTS}:
        raise HTTPException(status_code=422, detail={"reason_code": "unknown_mlx_runtime_slot"})
    operation = (
        _operation_service(request)
        .start(
            session.principal_id,
            ModelOperationRequest(
                kind="deploy", target=model.model_id, confirmed=True, destination=model.primary_path
            ),
            payload={
                "model_id": model.model_id,
                "model_path": model.primary_path,
                "framework": "mlx",
                "profile_id": profile_id,
            },
        )
        .to_dict()
    )
    roots = tuple(Path(path) for path in _library_service(request).roots(session.principal_id))
    background.add_task(
        _run_mlx_deployment,
        Path(request.app.state.workspace_root),
        session.principal_id,
        operation["operation_id"],
        Path(model.primary_path),
        roots,
        request.app.state.managed_mlx_runtime,
        profile_id,
    )
    return operation


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


@router.get("/api/hugging-face/trending")
def trending_hugging_face(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Most-downloaded GGUF repositories, so the panel opens with somewhere to start.

    Registered before the `{owner}/{repository}` routes so `trending` is never
    read as a repository owner.
    """
    session, principal = auth_data
    _require_human(principal)
    try:
        items = _hugging_face_service(request).trending(
            token=_hugging_face_token(request, session.principal_id)
        )
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
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Queue one immutable snapshot download and return its durable operation.

    The download used to run inside this request: a multi-gigabyte snapshot held
    a request worker for its whole duration, and the completion it wrote at the
    end could not see a Cancel the owner had pressed in the meantime, so the row
    ended `complete` against the owner's decision (GCR-22, GCR-23). Retry
    already had a background worker that checked cancellation; there is one
    worker now, and the first attempt is the same job as the second.
    """
    session, principal = auth_data
    _require_human(principal)
    if not body.confirmed or not body.destination:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    library_root = Path(body.destination).resolve()
    roots = [Path(root).resolve() for root in _library_service(request).roots(session.principal_id)]
    if library_root not in roots:
        raise HTTPException(
            status_code=422, detail={"reason_code": "destination_not_in_model_library"}
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", body.repo_id):
        raise HTTPException(
            status_code=422, detail={"reason_code": "invalid_hugging_face_repository"}
        )
    if not re.fullmatch(r"[0-9a-fA-F]{40}", body.revision):
        raise HTTPException(
            status_code=422, detail={"reason_code": "hugging_face_revision_not_immutable"}
        )
    destination = (
        library_root
        / ".raiker-hf"
        / body.repo_id.replace("/", "--")
        / body.revision[0:10].lower()
        / body.revision[10:20].lower()
        / body.revision[20:30].lower()
        / body.revision[30:40].lower()
    ).resolve()
    conversion_output = (library_root / "converted").resolve()
    # Resolved before anything is queued: a selection that has changed under the
    # owner is refused here, with its own reason, rather than becoming a failed
    # background job they have to go and read.
    try:
        _resolve_hugging_face_selection(body, request, session.principal_id)
    except (ValueError, HuggingFaceAccessError) as exc:
        code = exc.code if isinstance(exc, HuggingFaceAccessError) else str(exc)
        raise HTTPException(status_code=422, detail={"reason_code": code}) from exc
    conversion_output.mkdir(parents=True, exist_ok=True)
    operation = _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(
            kind="download",
            target=f"{body.repo_id}@{body.revision[:12]}",
            confirmed=True,
            source_url=f"https://huggingface.co/{body.repo_id}",
            destination=str(destination),
        ),
        payload={
            "repo_id": body.repo_id,
            "revision": body.revision,
            "variant": ",".join(body.files or []),
            "destination": str(destination),
        },
    )
    _dispatch_operation(background, request, session.principal_id, operation)
    result = operation.to_dict()
    # Both paths are derived from the approved destination and the immutable
    # revision, so they are known before a byte moves: the panel can offer the
    # conversion review the moment the operation reports `complete`.
    result["snapshot_path"] = str(destination)
    result["conversion_output_path"] = str(conversion_output)
    return result


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
        if operations.running(owner, operation_id, phase="converting").state != "running":
            return
        service = ModelConversionService()
        preview = service.preview(
            Path(body.source), Path(body.output), body.revision, body.quantization
        )
        # Conversion is one bounded subprocess, so it has exactly two points at
        # which it can co-operate: before it commits the CPU, and after. Both are
        # checked rather than neither.
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
        service.convert(preview)
        if operations.cancel_requested(owner, operation_id):
            operations.cancelled(owner, operation_id)
            return
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
        preview = ModelConversionService().preview(
            source, output, body.revision, body.quantization
        )
    except ConversionRefused as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc
    operation = _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(
            kind="convert",
            # The short revision, as the download row beside it already uses.
            # Found live 2026-09-05: `snapshot@<40 hex>` is 49 URL-safe
            # characters in one run, so the API redactor's high-entropy fallback
            # replaced the whole label with `[REDACTED_SECRET]` and every
            # conversion of the same snapshot became indistinguishable in
            # Activity. An immutable Hub revision is public, not a credential —
            # and twelve characters is the convention the product already had.
            target=f"{source.name}@{body.revision[:12]}",
            confirmed=True,
            destination=str(output),
        ),
        payload={
            "source": str(source),
            "output": str(output),
            "revision": body.revision,
            "quantization": body.quantization,
            "destination": str(output),
            # GCR-19 — the three files this conversion can create, recorded
            # before it runs. `output` is the owner's shared library directory
            # and is deliberately *not* a cleanup boundary: it holds the models
            # earlier conversions succeeded at.
            "artifacts": [str(path) for path in conversion_artifacts(preview)],
        },
    )
    background.add_task(
        _run_model_conversion,
        Path(request.app.state.workspace_root),
        session.principal_id,
        operation.operation_id,
        body,
    )
    return operation.to_dict()


async def _pull_ollama_model(workspace: Path, owner: str, operation_id: str, model: str) -> None:
    operations = ModelOperationService(SQLiteStore(workspace))
    try:
        if operations.running(owner, operation_id, phase="contacting_ollama").state != "running":
            return
        timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)
        async with (
            httpx.AsyncClient(timeout=timeout, trust_env=False) as client,
            client.stream(
                "POST",
                "http://127.0.0.1:11434/api/pull",
                json={"model": model, "stream": True},
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("error"):
                    raise RuntimeError("ollama_pull_rejected")
                # BUG-75 — cancellation is cooperative, so every worker has to
                # co-operate. Checking on each streamed progress line is the
                # tightest bound this job offers, so Cancel reaches a terminal
                # state in about one chunk rather than at the end of the pull.
                if operations.cancel_requested(owner, operation_id):
                    await response.aclose()
                    operations.cancelled(owner, operation_id)
                    return
                completed = int(payload.get("completed") or 0)
                raw_total = payload.get("total")
                total = int(raw_total) if raw_total is not None else None
                operations.progress(
                    owner,
                    operation_id,
                    completed_bytes=completed,
                    total_bytes=total,
                    phase=str(payload.get("status") or "pulling"),
                )
        operations.complete(owner, operation_id)
        SQLiteStore(workspace).invalidate_model_readiness(
            owner,
            "ollama-local-openai-compatible",
            reason_code="ollama_model_catalogue_changed",
        )
    except Exception:
        operations.fail(owner, operation_id, code="ollama_pull_failed")


@router.post("/api/ollama/pull")
def pull_ollama_model(
    body: OllamaPullRequestBody,
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    model = body.model.strip()
    if not body.confirmed:
        raise HTTPException(status_code=409, detail={"reason_code": "confirmation_required"})
    if not _OLLAMA_MODEL.fullmatch(model) or "//" in model:
        raise HTTPException(status_code=422, detail={"reason_code": "invalid_ollama_model"})
    operation = _operation_service(request).start(
        session.principal_id,
        ModelOperationRequest(kind="pull", target=model, confirmed=True),
        payload={"model": model},
    )
    background.add_task(
        _pull_ollama_model,
        Path(request.app.state.workspace_root),
        session.principal_id,
        operation.operation_id,
        model,
    )
    return operation.to_dict()
