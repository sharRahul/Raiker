from __future__ import annotations

import json
import re
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import ValidationError

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import require_human as _require_human
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
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.api.wire.models import (
    HuggingFaceCredentialSaved,
    HuggingFaceDownloadResult,
    HuggingFaceSearch,
    HuggingFaceTrending,
    HuggingFaceVariants,
    LibraryRescanned,
    LibraryRootAdded,
    LocalRuntimes,
    ModelDecisions,
    ModelLibraryView,
    ModelOperations,
    ModelOperationView,
    ModelReadinessList,
    OperationCleared,
    OperationReview,
    PartialFilesDeleted,
    PartialFilesRefused,
    SurfaceModels,
    SurfaceModelSet,
)
from raiker.models import local_presence
from raiker.models.conversion import (
    ConversionCancelled,
    ConversionRefused,
    ModelConversionService,
    conversion_artifacts,
)
from raiker.models.decision import SURFACES as DECISION_SURFACES
from raiker.models.decision import ModelDecisionService
from raiker.models.huggingface import HfVariant, HuggingFaceAccessError, HuggingFaceService
from raiker.models.library import ModelLibraryService
from raiker.models.local_operations import (
    ModelOperation,
    ModelOperationRequest,
    ModelOperationService,
    OperationCancelled,
    OperationWorker,
    run_operation,
    run_operation_async,
)
from raiker.models.local_runtime import LOCAL_SLOTS, ManagedLlamaRuntime, slot_for_profile
from raiker.models.mlx_runtime import MLX_SLOTS, ManagedMlxRuntime
from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
from raiker.models.runtime_installers import RuntimeInstallerRegistry
from raiker.models.setup import ModelSetupState
from raiker.runtime.authority.models import Principal
from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.internal_paths import internal_io_path
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()
_OLLAMA_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


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


@router.get("/api/model-readiness")
def list_model_readiness(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    items = SQLiteStore(request.app.state.workspace_root).list_model_readiness(  # type: ignore[attr-defined]
        session.principal_id
    )
    answer: ModelReadinessList = {"items": [item.to_dict() for item in items]}
    return serialize_dto(answer)


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
    return serialize_dto(readiness)


# The work surfaces that may hold their own default model. Declared beside the
# decision contract, so the routes, the read model and the tests cannot hold
# three different opinions about what a work surface is.
SURFACES = DECISION_SURFACES


@router.get("/api/surface-models")
def get_surface_models(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    answer: SurfaceModels = {
        "surfaces": {
            surface: {"profile_id": profile_id, "model": model}
            for surface, profile_id, model in store.list_surface_model_defaults(
                session.principal_id
            )
        }
    }
    return serialize_dto(answer)


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
    answer: SurfaceModelSet
    if not profile_id:
        store.clear_surface_model_default(session.principal_id, surface)
        answer = {"ok": True, "surface": surface, "profile_id": "", "model": ""}
        return serialize_dto(answer)
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
    answer = {"ok": True, "surface": surface, "profile_id": profile.profile_id, "model": model}
    return serialize_dto(answer)


@router.get("/api/model-decision")
def get_model_decision(
    request: Request,
    surface: str = "chat",
    project_id: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The one authoritative answer to "which model, and which one will run".

    Every surface that names a model — the Models page, the composer
    picker, Chat, Build, Design and task creation — reads this rather than
    assembling its own answer from the selection store, the surface defaults,
    readiness and the fallback sequence. Those five were each individually
    correct and collectively unable to agree.

    A read, and only a read: selection is written through `/api/model-selection`
    and `/api/surface-models`, which validate against the provider factory. A
    read model that could also write would be a second way to set a model, which
    is the shape of the problem this endpoint exists to close.
    """
    session, _principal = auth_data
    requested = surface.strip() or "chat"
    if requested not in SURFACES:
        raise HTTPException(status_code=422, detail={"reason_code": "unknown_surface"})
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    decision = ModelDecisionService(
        store, readiness=_service(request), runtimes=_runtimes(request)
    ).decide(session.principal_id, requested, project_id.strip() or None)
    return serialize_dto(decision)


def _runtimes(request: Request) -> tuple[Any, ...]:
    """The host's managed local pools, so a decision reports what they run."""
    state = request.app.state
    return tuple(
        runtime
        for runtime in (
            getattr(state, "managed_llama_runtime", None),
            getattr(state, "managed_mlx_runtime", None),
        )
        if runtime is not None
    )


@router.get("/api/model-decisions")
def get_model_decisions(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Every surface's decision in one read.

    Overview answers "what powers Chat, Build and Design" as its
    first fact, which is five of the read above. Asking five times is five
    round trips and — worse — five separately-timed answers, so the page could
    render a Chat row from before a change and a Build row from after it. One
    service instance, so every surface is judged against the same readiness
    cache.
    """
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    service = ModelDecisionService(
        store, readiness=_service(request), runtimes=_runtimes(request)
    )
    answer: ModelDecisions = {
        "surfaces": {
            surface: service.decide(session.principal_id, surface).to_dict()
            for surface in SURFACES
        }
    }
    return serialize_dto(answer)


@router.get("/api/model-setup")
def get_model_setup(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    return serialize_dto(
        SQLiteStore(request.app.state.workspace_root).load_model_setup_state(  # type: ignore[attr-defined]
            session.principal_id
        )
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
    return serialize_dto(store.save_model_setup_state(
        ModelSetupState(
            owner_principal_id=session.principal_id,
            status=body.status,
            step=body.step,
            path=body.path,
            selected_profile_id=body.selected_profile_id,
            selected_model=body.selected_model,
            created_at=current.created_at,
        )
    ))


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
    answer: LocalRuntimes = {
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
    return serialize_dto(answer)


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
    answer: LocalRuntimes = {
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
    return serialize_dto(answer)


@router.post("/api/model-operations/preview")
def preview_model_operation(
    body: ModelOperationRequestBody,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = auth_data
    _require_human(principal)
    if body.kind != "install":
        review: OperationReview = {
            "kind": body.kind,
            "target": body.target,
            "action": "review_operation",
            "confirmed": False,
        }
        return serialize_dto(review)
    try:
        return serialize_dto(
            RuntimeInstallerRegistry().preview(
                body.target, platform="windows" if sys.platform == "win32" else sys.platform
            )
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
    answer: ModelOperations = {
        "items": [item.to_dict() for item in _operation_service(request).list(session.principal_id)]
    }
    return serialize_dto(answer)


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
    return serialize_dto(
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

    def work(op: OperationWorker) -> None:
        repo_id = str(payload.get("repo_id", ""))
        revision = str(payload.get("revision", ""))
        files = tuple(part for part in str(payload.get("variant", "")).split(",") if part)
        destination = Path(str(payload.get("destination", "")))
        if not repo_id or not revision or not files or not destination.name:
            raise ValueError("hugging_face_retry_payload_incomplete")
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
        op.check_cancelled()

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="downloading",
        failure_code="hugging_face_download_failed",
        work=work,
    )


@router.post("/api/model-operations/{operation_id}/cancel")
def cancel_model_operation(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    try:
        cancelled = _operation_service(request).cancel(session.principal_id, operation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc
    return serialize_dto(cancelled)


@router.post("/api/model-operations/{operation_id}/retry")
def retry_model_operation(
    operation_id: str,
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Re-queue a failed operation **and dispatch its worker again** (BUG-75).

    A retry that only re-queued the row would leave it recorded and idle. The
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
    return serialize_dto(requeued)


@router.get("/api/model-operations/{operation_id}/partial-files")
def preview_partial_files(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """What a confirmed cleanup would delete: the exact approved path and bytes."""
    session, principal = auth_data
    _require_human(principal)
    try:
        return serialize_dto(_operation_service(request).partial_files(session.principal_id, operation_id))
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
        refused: PartialFilesRefused = {"ok": False, "reason_code": "no_partial_files", **summary}
        return serialize_dto(refused)
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
    deleted: PartialFilesDeleted = {"ok": True, **summary}
    return serialize_dto(deleted)


@router.delete("/api/model-operations/{operation_id}")
def cleanup_model_operation(
    operation_id: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    try:
        cleared: OperationCleared = {
            "ok": _operation_service(request).cleanup(session.principal_id, operation_id)
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc.args[0])}) from exc
    return serialize_dto(cleared)


@router.get("/api/model-library")
def get_model_library(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    service = _library_service(request)
    answer: ModelLibraryView = {
        "roots": [{"path": path} for path in service.roots(session.principal_id)],
        "models": [model.to_dict() for model in service.list_models(session.principal_id)],
    }
    return serialize_dto(answer)


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
    added: LibraryRootAdded = {"ok": True, "path": path}
    return serialize_dto(added)


@router.delete("/api/model-library/roots")
def remove_model_library_root(
    body: ModelLibraryRootRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    removed: OperationCleared = {
        "ok": _library_service(request).remove_root(session.principal_id, Path(body.path))
    }
    return serialize_dto(removed)


@router.post("/api/model-library/rescan")
def rescan_model_library(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    models = _library_service(request).rescan(session.principal_id)
    answer: LibraryRescanned = {"ok": True, "models": [model.to_dict() for model in models]}
    return serialize_dto(answer)


def _wait_until_serving(
    op: OperationWorker, *, served: Callable[[httpx.Client], str | None], budget: float
) -> str:
    """Poll a just-started loopback server until it names what it serves.

    The readiness wait is the long part of a deploy, so it is where Cancel has
    to land.
    """
    deadline = time.monotonic() + budget
    with httpx.Client(timeout=2.0, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                name = served(client)
                if name is not None:
                    return name
            except (httpx.HTTPError, ValueError):
                pass
            op.check_cancelled()
            time.sleep(0.2)
    raise RuntimeError("local_server_not_ready")


def _run_local_deployment(
    workspace: Path,
    owner: str,
    operation_id: str,
    model_path: Path,
    approved_roots: tuple[Path, ...],
    runtime: ManagedLlamaRuntime,
    profile_id: str | None = None,
) -> None:
    def work(op: OperationWorker) -> None:
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
        # Only this deployment's own slot is stopped on failure or Cancel.
        # Another model already serving a surface must not be torn down by an
        # unrelated failure, which is exactly what a bare `stop()` would do.
        op.on_abort(lambda: runtime.stop(started.slot))
        slot = slot_for_profile(started.slot) or LOCAL_SLOTS[0]
        origin = f"http://127.0.0.1:{slot.port}"

        def served(client: httpx.Client) -> str | None:
            health = client.get(f"{origin}/health")
            models = client.get(f"{origin}/v1/models")
            ids = [str(item.get("id")) for item in models.json().get("data", [])]
            ok = health.is_success and models.is_success and slot.alias in ids
            return slot.alias if ok else None

        _wait_until_serving(op, served=served, budget=30)
        store = SQLiteStore(workspace)
        store.save_configured_model(owner, slot.profile_id, slot.alias)
        store.invalidate_model_readiness(
            owner, slot.profile_id, reason_code="local_runtime_deployed"
        )

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="starting_llama_cpp",
        failure_code="local_model_deploy_failed",
        work=work,
    )


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
    operation: ModelOperationView = (
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
    return serialize_dto(operation)


def _run_mlx_deployment(
    workspace: Path,
    owner: str,
    operation_id: str,
    model_path: Path,
    approved_roots: tuple[Path, ...],
    runtime: ManagedMlxRuntime,
    profile_id: str | None = None,
) -> None:
    def work(op: OperationWorker) -> None:
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
        op.on_abort(lambda: runtime.stop(started.slot))
        slot = next(item for item in MLX_SLOTS if item.profile_id == started.slot)

        def served(client: httpx.Client) -> str | None:
            response = client.get(f"http://127.0.0.1:{slot.port}/v1/models")
            ids = [str(item.get("id")) for item in response.json().get("data", [])]
            return ids[0] if response.is_success and ids else None

        served_model = _wait_until_serving(op, served=served, budget=60)
        store = SQLiteStore(workspace)
        store.save_configured_model(owner, slot.profile_id, served_model)
        store.invalidate_model_readiness(
            owner, slot.profile_id, reason_code="local_runtime_deployed"
        )

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="starting_mlx",
        failure_code="local_mlx_deploy_failed",
        work=work,
    )


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
    operation: ModelOperationView = (
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
    return serialize_dto(operation)


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
    saved: HuggingFaceCredentialSaved = {"configured": True}
    return serialize_dto(saved)


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
    answer: HuggingFaceSearch = {"items": list(items)}
    return serialize_dto(answer)


@router.get("/api/hugging-face/trending")
def trending_hugging_face(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Most-downloaded GGUF repositories, so the panel opens with somewhere to start.

    Registered before the `{owner}/{repository}` routes so `trending` is never
    read as a repository owner.

    **BUG-296 — an unreachable Hub is an answer here, not an error.** Every other
    Hugging Face route raises 503 when the Hub cannot be reached, which is right
    for them: an owner asked for a specific repository, a variant or a download,
    and did not get it. Nobody asks for this one. It runs on every visit to
    Models so the panel has something to open with, and a host with no route to
    `huggingface.co` therefore put `GET /api/hugging-face/trending — 503` in the
    browser console every single time.

    That console entry was the whole defect. The panel already *handles* the
    outage correctly and says so in the right place; what the 503 cost was
    somewhere else entirely — the live manual test plan requires a round to end
    with zero uncaught console errors, and several live specs assert exactly
    that. An expected, handled, correctly-reported outage was spending the
    budget that exists to catch real ones, and a round that learns to ignore one
    console error has learned to ignore the next.

    So the probe answers 200 with no items and the reason it has none. The
    request to *Raiker* did succeed; "the Hub is not reachable from this host" is
    the true answer to it. The routes an owner drives keep their 503, because
    there a failed request is a failed request.
    """
    session, principal = auth_data
    _require_human(principal)
    try:
        items = _hugging_face_service(request).trending(
            token=_hugging_face_token(request, session.principal_id)
        )
    except HuggingFaceAccessError as exc:
        unreachable: HuggingFaceTrending = {
            "items": [],
            "unreachable": {
                "reason_code": exc.code,
                "repository_url": exc.repository_url,
            },
        }
        return serialize_dto(unreachable)
    answer: HuggingFaceTrending = {"items": list(items)}
    return serialize_dto(answer)


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
    answer: HuggingFaceVariants = {"items": list(items)}
    return serialize_dto(answer)


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
        return serialize_dto(
            _hugging_face_service(request).dry_run(
                body.repo_id, variant, token=_hugging_face_token(request, session.principal_id)
            )
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

    The download never runs inside the request: a multi-gigabyte snapshot would
    hold a worker for its whole duration, and its completion must see a Cancel
    pressed meanwhile (GCR-22, GCR-23). One background worker runs the first
    attempt and every retry.
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
    try:
        conversion_output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Made before the download, so a library folder the owner cannot write
        # to is refused up front in the owner's terms, not at the end of a
        # multi-gigabyte pull as an unhandled 500.
        raise HTTPException(
            status_code=422, detail={"reason_code": "model_library_not_writable"}
        ) from exc
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
    # Both paths are derived from the approved destination and the immutable
    # revision, so they are known before a byte moves: the panel can offer the
    # conversion review the moment the operation reports `complete`.
    result: HuggingFaceDownloadResult = {
        **operation.to_dict(),
        "snapshot_path": str(destination),
        "conversion_output_path": str(conversion_output),
    }
    return serialize_dto(result)


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
        return serialize_dto(
            ModelConversionService().preview(source, output, body.revision, body.quantization)
        )
    except ConversionRefused as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc


def _run_model_conversion(
    workspace: Path, owner: str, operation_id: str, body: ModelConversionRequestBody
) -> None:
    def work(op: OperationWorker) -> None:
        service = ModelConversionService()
        preview = service.preview(
            Path(body.source), Path(body.output), body.revision, body.quantization
        )
        # GCR-24 — the flag is read before the work starts, throughout it, and
        # after: the runner polls it and stops the container by name, so Cancel
        # on a conversion that has just begun does not leave the CPU committed.
        op.check_cancelled()
        try:
            service.convert(preview, op.cancel_requested)
        except ConversionCancelled:
            raise OperationCancelled from None
        op.check_cancelled()

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="converting",
        failure_code="model_conversion_failed",
        work=work,
        then=lambda: ModelLibraryService(SQLiteStore(workspace)).rescan(owner),
    )


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
            # The short revision, as the download row beside it uses. A full
            # `snapshot@<40 hex>` is one 49-character URL-safe run, which the API
            # redactor's high-entropy fallback replaces with `[REDACTED_SECRET]`.
            # An immutable Hub revision is public, not a credential.
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
    return serialize_dto(operation)


async def _pull_ollama_model(workspace: Path, owner: str, operation_id: str, model: str) -> None:
    async def work(op: OperationWorker) -> None:
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
                # BUG-75 — checked on each streamed progress line, the tightest
                # bound this job offers, so Cancel lands within about one chunk.
                op.check_cancelled()
                raw_total = payload.get("total")
                op.progress(
                    completed_bytes=int(payload.get("completed") or 0),
                    total_bytes=int(raw_total) if raw_total is not None else None,
                    phase=str(payload.get("status") or "pulling"),
                )

    await run_operation_async(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="contacting_ollama",
        failure_code="ollama_pull_failed",
        work=work,
        then=lambda: SQLiteStore(workspace).invalidate_model_readiness(
            owner,
            "ollama-local-openai-compatible",
            reason_code="ollama_model_catalogue_changed",
        ),
    )


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
    return serialize_dto(operation)
