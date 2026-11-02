"""The llama.cpp engine in Models: install it, size each model, watch each slot.

Every route here is owner-only and loopback-local like the rest of Models. The
one route that reaches the network — installing, and checking for an update —
goes only to ggml-org's official GitHub releases, and only when the owner
presses the button; reading this page never does.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import require_human as _require_human
from raiker.api.schemas import LlamaCppInstallRequest, LocalRuntimeSettingsRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.contracts.views import View
from raiker.models import local_presence
from raiker.models.library import LocalModel, ModelLibraryService
from raiker.models.llama_cpp import hardware, installer
from raiker.models.llama_cpp.hardware import HardwareProfile
from raiker.models.llama_cpp.installer import Installation, InstallError, ResolvedExecutable
from raiker.models.llama_cpp.planner import LaunchPlan, RuntimeSettings
from raiker.models.llama_cpp.releases import (
    LICENSE_URL,
    RELEASES_PAGE,
    ReleaseError,
    fetch_release,
    select_assets,
)
from raiker.models.llama_cpp.supervisor import LaunchRefused, LlamaSupervisor, SlotHealth
from raiker.models.local_operations import (
    ModelOperationRequest,
    ModelOperationService,
    OperationWorker,
    run_operation,
)
from raiker.models.local_runtime import LOCAL_SLOTS
from raiker.models.wire import ModelOperationView
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


@dataclass(frozen=True)
class RestoreFailure(View):
    slot_profile_id: str
    model_id: str
    model_path: str
    reason_code: str


@dataclass(frozen=True)
class LlamaRuntimeOverview(View):
    installation: Installation | None
    executable: ResolvedExecutable
    hardware: HardwareProfile
    slots: tuple[SlotHealth, ...]
    restore_failures: tuple[RestoreFailure, ...]
    release_page: str
    license_url: str


@dataclass(frozen=True)
class LlamaUpdateCheck(View):
    installed_tag: str | None
    latest_tag: str
    update_available: bool
    published_at: str | None


@dataclass(frozen=True)
class ModelRuntimeSettingsView(View):
    model_id: str
    settings: RuntimeSettings
    plan: LaunchPlan | None
    #: Why no plan could be made (the engine is missing, the file unreadable).
    plan_error: str | None


def _supervisor(request: Request) -> LlamaSupervisor:
    supervisor: LlamaSupervisor = request.app.state.llama_supervisor  # type: ignore[attr-defined]
    return supervisor


def _workspace(request: Request) -> Path:
    return Path(request.app.state.workspace_root)  # type: ignore[attr-defined]


def _overview(request: Request, owner: str, *, force: bool = False) -> LlamaRuntimeOverview:
    workspace = _workspace(request)
    supervisor = _supervisor(request)
    failures = tuple(
        RestoreFailure(slot, model_id, path, reason)
        for slot, (model_id, path, reason) in sorted(supervisor.restore_failures().items())
    )
    return LlamaRuntimeOverview(
        installation=installer.current(workspace),
        executable=installer.resolve_executable(workspace),
        hardware=hardware.detect(force=force),
        slots=tuple(supervisor.slots(owner)),
        restore_failures=failures,
        release_page=RELEASES_PAGE,
        license_url=LICENSE_URL,
    )


# ── installing ─────────────────────────────────────────────────────────

#: Install failures that mean "this backend does not work here", after which an
#: automatic choice tries the next backend rather than giving up.
_FALL_THROUGH = frozenset(
    {
        "llama_cpp_backend_no_device",
        "llama_cpp_install_unrunnable",
        "llama_cpp_cuda_driver_too_old",
        "llama_cpp_asset_missing",
        "llama_cpp_backend_unsupported",
    }
)


def install_engine(op: OperationWorker, workspace: Path, backend: str, release: str | None) -> Installation:
    """Install the best working llama.cpp build for this machine (or ``backend``)."""
    profile = hardware.detect(force=True)
    if backend == "auto":
        candidates = [profile.recommended_backend] + [
            item for item in profile.backends if item != profile.recommended_backend
        ]
    else:
        candidates = [backend]
    op.progress(completed_bytes=0, total_bytes=None, phase="resolving_llama_cpp_release")
    found = fetch_release(release)
    cuda = next((gpu.cuda_version for gpu in profile.gpus if gpu.cuda_version), None)
    last: Exception = InstallError("llama_cpp_backend_unsupported")
    for choice in candidates:
        op.check_cancelled()
        try:
            selection = select_assets(
                found, os_name=profile.os, arch=profile.arch, backend=choice, cuda_driver_version=cuda
            )
            installed = installer.install(
                workspace,
                selection,
                progress=lambda done, total, phase: op.progress(
                    completed_bytes=done, total_bytes=total, phase=phase
                ),
                cancelled=op.check_cancelled,
            )
            _refresh_presence(workspace)
            return installed
        except (InstallError, ReleaseError) as exc:
            last = exc if isinstance(exc, InstallError) else InstallError(str(exc))
            if backend != "auto" or str(exc) not in _FALL_THROUGH:
                raise last from exc
    raise last


def _refresh_presence(workspace: Path) -> None:
    """Tell readiness the engine changed, so no surface keeps saying "missing"."""
    with contextlib.suppress(Exception):
        local_presence.detect(SQLiteStore(workspace), runtimes=("llama.cpp",), force=True)


def run_llama_cpp_install(
    workspace: Path, owner: str, operation_id: str, backend: str, release: str | None
) -> None:
    def work(op: OperationWorker) -> None:
        install_engine(op, workspace, backend, release)

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="installing_llama_cpp",
        failure_code="llama_cpp_install_failed",
        work=work,
    )


def start_install_operation(
    workspace: Path, owner: str, backend: str, release: str | None
) -> ModelOperationView:
    return (
        ModelOperationService(SQLiteStore(workspace))
        .start(
            owner,
            ModelOperationRequest(
                kind="install", target="llama.cpp", confirmed=True, source_url=RELEASES_PAGE
            ),
            payload={"backend": backend, "release": release or ""},
        )
        .to_dict()
    )


# ── routes ─────────────────────────────────────────────────────────────


@router.get("/api/local-runtime/llama-cpp")
def get_llama_runtime(
    request: Request,
    refresh: bool = False,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The engine, this machine's hardware, and every slot's health."""
    session, principal = auth_data
    _require_human(principal)
    overview = _overview(request, session.principal_id, force=refresh)
    return serialize_dto(overview)


@router.post("/api/local-runtime/llama-cpp/install")
def install_llama_runtime(
    body: LlamaCppInstallRequest,
    background: BackgroundTasks,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Download, verify and activate the official llama.cpp build."""
    session, principal = auth_data
    _require_human(principal)
    if body.release is not None and not body.release.strip():
        body = LlamaCppInstallRequest(backend=body.backend)
    operation: ModelOperationView = start_install_operation(
        _workspace(request), session.principal_id, body.backend, body.release
    )
    background.add_task(
        run_llama_cpp_install,
        _workspace(request),
        session.principal_id,
        operation["operation_id"],
        body.backend,
        body.release,
    )
    return serialize_dto(operation)


@router.post("/api/local-runtime/llama-cpp/update-check")
def check_llama_runtime_update(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = auth_data
    _require_human(principal)
    try:
        latest = fetch_release()
    except ReleaseError as exc:
        raise HTTPException(status_code=502, detail={"reason_code": str(exc)}) from exc
    installed = installer.current(_workspace(request))
    answer = LlamaUpdateCheck(
        installed_tag=installed.tag if installed else None,
        latest_tag=latest.tag,
        update_available=installed is None or _tag_number(latest.tag) > _tag_number(installed.tag),
        published_at=latest.published_at,
    )
    return serialize_dto(answer)


def _tag_number(tag: str) -> int:
    digits = tag.lstrip("b")
    return int(digits) if digits.isdigit() else 0


@router.delete("/api/local-runtime/llama-cpp/installation")
def uninstall_llama_runtime(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Remove Raiker's llama.cpp build. Refused while any model is served from it."""
    session, principal = auth_data
    _require_human(principal)
    supervisor = _supervisor(request)
    if supervisor.slots() or supervisor.runtime.statuses():
        raise HTTPException(status_code=409, detail={"reason_code": "local_runtime_in_use"})
    installer.uninstall(_workspace(request))
    _refresh_presence(_workspace(request))
    return serialize_dto(_overview(request, session.principal_id))


def _known_slot(profile_id: str) -> str:
    if profile_id not in {slot.profile_id for slot in LOCAL_SLOTS}:
        raise HTTPException(status_code=404, detail={"reason_code": "unknown_local_runtime_slot"})
    return profile_id


@router.post("/api/local-runtime/llama-cpp/slots/{profile_id}/stop")
def stop_llama_slot(
    profile_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Unload the model in one slot; it will not come back at the next start."""
    session, principal = auth_data
    _require_human(principal)
    slot = _known_slot(profile_id)
    _supervisor(request).stop_slot(slot)
    SQLiteStore(_workspace(request)).invalidate_model_readiness(
        session.principal_id, slot, reason_code="local_runtime_stopped"
    )
    return serialize_dto(_overview(request, session.principal_id))


@router.post("/api/local-runtime/llama-cpp/slots/{profile_id}/restart")
def restart_llama_slot(
    profile_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = auth_data
    _require_human(principal)
    try:
        health = _supervisor(request).restart_slot(_known_slot(profile_id))
    except LaunchRefused as exc:
        raise HTTPException(status_code=409, detail={"reason_code": str(exc)}) from exc
    return serialize_dto(health)


def _model(request: Request, owner: str, model_id: str) -> LocalModel:
    model = next(
        (
            item
            for item in ModelLibraryService(SQLiteStore(_workspace(request))).list_models(owner)
            if item.model_id == model_id
        ),
        None,
    )
    if model is None:
        raise HTTPException(status_code=404, detail={"reason_code": "local_model_not_found"})
    if model.format != "gguf":
        raise HTTPException(status_code=409, detail={"reason_code": "local_model_wrong_format"})
    return model


def _settings_view(
    request: Request, model: LocalModel, settings: RuntimeSettings
) -> ModelRuntimeSettingsView:
    supervisor = _supervisor(request)
    slot = next(
        (item.slot_profile_id for item in supervisor.slots() if item.model_path == str(Path(model.primary_path).resolve())),
        None,
    )
    try:
        plan = supervisor.plan(Path(model.primary_path), settings, slot=slot)
        error = None
    except (OSError, ValueError) as exc:
        plan, error = None, (str(exc) if isinstance(exc, ValueError) else "local_model_unreadable")
    return ModelRuntimeSettingsView(model.model_id, settings, plan, error)


def _parse(body: LocalRuntimeSettingsRequest) -> RuntimeSettings:
    try:
        return RuntimeSettings.from_mapping(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason_code": str(exc)}) from exc


@router.get("/api/local-runtime/llama-cpp/models/{model_id}/settings")
def get_model_runtime_settings(
    model_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    _require_human(principal)
    model = _model(request, session.principal_id, model_id)
    stored = SQLiteStore(_workspace(request)).load_local_runtime_settings(session.principal_id, model_id)
    try:
        settings = RuntimeSettings.from_mapping(stored)
    except ValueError:
        settings = RuntimeSettings()
    return serialize_dto(_settings_view(request, model, settings))


@router.put("/api/local-runtime/llama-cpp/models/{model_id}/settings")
def save_model_runtime_settings(
    model_id: str,
    body: LocalRuntimeSettingsRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Save one model's settings. A running slot picks them up on its next start."""
    session, principal = auth_data
    _require_human(principal)
    model = _model(request, session.principal_id, model_id)
    settings = _parse(body)
    SQLiteStore(_workspace(request)).save_local_runtime_settings(
        session.principal_id, model_id, settings.to_dict()
    )
    return serialize_dto(_settings_view(request, model, settings))


@router.post("/api/local-runtime/llama-cpp/models/{model_id}/plan")
def preview_model_runtime_plan(
    model_id: str,
    body: LocalRuntimeSettingsRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What these settings would start with, and whether they fit. Nothing is saved."""
    session, principal = auth_data
    _require_human(principal)
    model = _model(request, session.principal_id, model_id)
    return serialize_dto(_settings_view(request, model, _parse(body)))
