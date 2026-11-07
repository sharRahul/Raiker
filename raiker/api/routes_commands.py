from __future__ import annotations

import contextlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, NoReturn, cast

from fastapi import APIRouter, Depends, Query, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.schemas import (
    CommandEgressRequest,
    CommandSandboxRequest,
    PromoteTaskWorkspaceRequest,
    WslSetupRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.api.wire.commands import (
    CommandEgressView,
    CommandOutput,
    CommandReceiptAnswer,
    CommandReceiptView,
    CommandRunDetail,
    CommandRunList,
    CommandRunState,
    CommandRunView,
    CommandSandboxView,
    CommandStopped,
    CredentialDeltaDiscarded,
    CredentialDeltaList,
    CredentialDeltaView,
    TaskWorkspaceDiscarded,
    TaskWorkspaceFileDiff,
    TaskWorkspaceList,
    TaskWorkspacePromoted,
    TaskWorkspaceView,
)
from raiker.execution.commands.models import (
    TERMINAL_COMMAND_STATES,
    CommandReceipt,
    StoredCommandRun,
)
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.execution.commands.store import ReceiptImmutable
from raiker.execution.workspaces import (
    TaskWorkspace,
    TaskWorkspaceRegistry,
    WorkspaceError,
    diff_workspace,
    promote,
    promotion_conflicts,
)
from raiker.runtime.authority.models import Principal

router = APIRouter()


def _service(request: Request) -> CommandService:
    service = getattr(request.app.state, "command_service", None)
    if service is None:
        service = CommandService.for_workspace(request.app.state.workspace_root)
        request.app.state.command_service = service
    return service


def _run_view(run: StoredCommandRun) -> CommandRunView:
    value = asdict(run)
    value["state"] = run.state.value
    value.pop("owner_principal_id", None)
    value.pop("acting_principal_id", None)
    value.pop("template_digest", None)
    return cast(CommandRunView, value)


def _receipt_view(receipt: CommandReceipt) -> CommandReceiptView:
    return {
        "run_id": receipt.run_id,
        "state": cast(CommandRunState, receipt.state.value),
        "exit_code": receipt.exit_code,
        "termination_reason": receipt.termination_reason,
        "completed_at": receipt.completed_at,
        "evidence": receipt.evidence,
        "digest": receipt.digest,
    }


def _raise_service(exc: CommandServiceError) -> NoReturn:
    code = status.HTTP_404_NOT_FOUND if exc.reason_code == "command_run_not_found" else status.HTTP_409_CONFLICT
    raise refusal(code, exc.reason_code) from exc


@router.get("/api/command-runs")
def list_commands(
    request: Request,
    session_id: str | None = Query(default=None, max_length=200),
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _ = auth_data
    service = _service(request)
    service.recover_owner(session.principal_id)
    runs = service.store.list_runs(session.principal_id, session_id=session_id)
    listed: CommandRunList = {"runs": [_run_view(run) for run in runs]}
    return serialize_dto(listed)


@router.get("/api/command-runs/{run_id}")
def get_command(
    run_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    run = _service(request).store.load(auth_data[0].principal_id, run_id)
    if run is None:
        _raise_service(CommandServiceError("command_run_not_found"))
    detail: CommandRunDetail = {"run": _run_view(run)}
    return serialize_dto(detail)


@router.get("/api/command-runs/{run_id}/output")
def get_command_output(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    service = _service(request)
    owner = auth_data[0].principal_id
    if service.store.load(owner, run_id) is None:
        _raise_service(CommandServiceError("command_run_not_found"))
    chunks = [asdict(chunk) for chunk in service.store.read_output(owner, run_id, after=after)]
    output = cast(
        CommandOutput,
        {"chunks": chunks, "next_after": chunks[-1]["sequence"] if chunks else after},
    )
    return serialize_dto(output)


@router.get("/api/command-runs/{run_id}/receipt")
def get_command_receipt(
    run_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    service = _service(request)
    owner = auth_data[0].principal_id
    if service.store.load(owner, run_id) is None:
        _raise_service(CommandServiceError("command_run_not_found"))
    receipt = service.store.get_receipt(owner, run_id)
    answer: CommandReceiptAnswer = {"receipt": _receipt_view(receipt) if receipt else None}
    return serialize_dto(answer)


@router.post("/api/command-runs/{run_id}/stop")
def stop_command(
    run_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    try:
        run = _service(request).stop(auth_data[0].principal_id, run_id)
    except CommandServiceError as exc:
        _raise_service(exc)
    stopped: CommandStopped = {"ok": True, "run": _run_view(run)}
    return serialize_dto(stopped)


@router.get("/api/credential-deltas")
def list_credential_deltas(
    request: Request,
    environment_profile_id: str = Query(..., min_length=1, max_length=200),
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Return safe metadata only; encrypted handles and matcher material stay internal."""
    rows = _service(request).store.list_unresolved_deltas(
        auth_data[0].principal_id, environment_profile_id
    )
    deltas: list[CredentialDeltaView] = []
    for row in rows:
        try:
            manifest = json.loads(str(row["safe_manifest_json"]))
        except (TypeError, ValueError):
            manifest = {"files": []}
        deltas.append(
            {  # type: ignore[typeddict-item]
                "run_id": row["run_id"],
                "environment_profile_id": row["environment_profile_id"],
                "state": row["state"],
                "manifest": manifest,
                "delta_digest": row["delta_digest"],
                "scan_digest": row["scan_digest"],
                "scan_rule_version": row["scan_rule_version"],
                "cleanup_status": row["cleanup_status"],
                "created_at": row["created_at"],
                "recipient_boundary": "disposable_container_tcb",
            }
        )
    listed: CredentialDeltaList = {"deltas": deltas}
    return serialize_dto(listed)


@router.post("/api/credential-deltas/{run_id}/discard")
def discard_credential_delta(
    run_id: str,
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    decision_id = str(body.get("decision_id", "")).strip()
    if not decision_id:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "credential_delta_decision_required")
    try:
        changed = _service(request).store.resolve_credential_delta(
            auth_data[0].principal_id,
            run_id,
            decision_id=decision_id,
            resolution="discarded",
        )
    except ReceiptImmutable as exc:
        raise refusal(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not changed:
        raise refusal(status.HTTP_404_NOT_FOUND, "credential_delta_not_found")
    discarded: CredentialDeltaDiscarded = {
        "ok": True,
        "receipt": _service(request).store.get_delta_receipt(auth_data[0].principal_id, run_id),
    }
    return serialize_dto(discarded)


# ── Allow-listed downloads for sandboxed commands ────────────────────────────


def _egress_view(settings: Any) -> CommandEgressView:
    from raiker.execution.commands.egress_runtime import DEFAULT_DOWNLOAD_DOMAINS  # noqa: PLC0415

    return {
        "enabled": settings.enabled,
        "domains": list(settings.domains),
        "defaults": list(DEFAULT_DOWNLOAD_DOMAINS),
    }


@router.get("/api/command-egress")
def get_command_egress(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    from raiker.execution.commands.egress_runtime import load_settings  # noqa: PLC0415

    view: CommandEgressView = _egress_view(load_settings(request.app.state.workspace_root))
    return serialize_dto(view)


@router.put("/api/command-egress")
def put_command_egress(
    body: CommandEgressRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The owner's choice; every later sandboxed run reads it at launch."""
    from raiker.execution.commands.egress_runtime import save_settings  # noqa: PLC0415

    owner = auth_data[0].principal_id
    try:
        settings = save_settings(request.app.state.workspace_root, body.enabled, body.domains)
    except ValueError as exc:
        raise refusal(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    _audit_workspace(
        request, owner, "", "command_egress_changed",
        {"enabled": settings.enabled, "domain_count": len(settings.domains)},
    )
    view: CommandEgressView = _egress_view(settings)
    return serialize_dto(view)


# ── Which boundary sandboxed commands use (Windows) ─────────────────────────

#: `--wsl-status` fields that must be true, named for the owner when not.
_WSL_REQUIREMENTS = (
    "distribution_present",
    "wsl_conf_current",
    "runner_installed",
    "bubblewrap_present",
)


def _sandbox_view(request: Request, choice: str) -> CommandSandboxView:
    import sys  # noqa: PLC0415

    from raiker.execution.commands.backends.native import NativeSandboxDriver  # noqa: PLC0415

    applies = sys.platform == "win32"
    driver = NativeSandboxDriver(request.app.state.workspace_root)
    status = driver.wsl_status() if applies else None
    runner, _ = driver.locate()
    linux_runner = driver.wsl_runner() if applies else None
    setup = (
        f'"{runner}" --setup-wsl --linux-runner "{linux_runner}" --rootfs <rootfs.tar>'
        if runner is not None and linux_runner is not None
        else None
    )
    configured = bool(status and status.get("configured") is True)
    missing = (
        []
        if configured or not applies
        else [name for name in _WSL_REQUIREMENTS if not (status or {}).get(name)]
    )
    return {
        "windows_backend": choice,
        "applies": applies,
        "wsl_configured": configured,
        "wsl_missing": missing,
        "wsl_setup_command": setup,
    }


@router.get("/api/command-sandbox")
def get_command_sandbox(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    from raiker.execution.commands.sandbox_backend import load_windows_backend  # noqa: PLC0415

    view: CommandSandboxView = _sandbox_view(
        request, load_windows_backend(request.app.state.workspace_root)
    )
    return serialize_dto(view)


@router.put("/api/command-sandbox")
def put_command_sandbox(
    body: CommandSandboxRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The owner's choice; every later command probes and launches with it.

    Choosing WSL2 before it is set up is allowed and fails closed: commands
    refuse (`native_sandbox_wsl_unconfigured`) rather than fall back.
    """
    from raiker.execution.commands.sandbox_backend import save_windows_backend  # noqa: PLC0415

    choice = save_windows_backend(request.app.state.workspace_root, body.windows_backend)
    _audit_workspace(
        request, auth_data[0].principal_id, "", "command_sandbox_backend_changed",
        {"windows_backend": choice},
    )
    view: CommandSandboxView = _sandbox_view(request, choice)
    return serialize_dto(view)


@router.post("/api/command-sandbox/wsl/setup")
def setup_command_sandbox_wsl(
    body: WslSetupRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Import and configure Raiker's own WSL2 distribution (Windows).

    Runs the runner's `--setup-wsl` with the Linux runner this install ships.
    No elevation is needed. It can take several minutes (the import, and
    installing Bubblewrap inside), so the answer comes when it is done.
    """
    from raiker.execution.commands.backends.native import NativeSandboxDriver  # noqa: PLC0415
    from raiker.execution.commands.sandbox_backend import load_windows_backend  # noqa: PLC0415

    root = request.app.state.workspace_root
    ok, reason = NativeSandboxDriver(root).setup_wsl(Path(body.rootfs_path))
    _audit_workspace(
        request, auth_data[0].principal_id, "", "command_sandbox_wsl_setup",
        {"ok": ok, "reason_code": reason or None},
    )
    if not ok:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, reason)
    view: CommandSandboxView = _sandbox_view(request, load_windows_backend(root))
    return serialize_dto(view)


@router.post("/api/command-sandbox/wsl/remove")
def remove_command_sandbox_wsl(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Unregister Raiker's WSL2 distribution and every task copy inside it.

    Commands move back to the sandbox account, so nothing is left pointing at
    a distribution that no longer exists.
    """
    from raiker.execution.commands.backends.native import NativeSandboxDriver  # noqa: PLC0415
    from raiker.execution.commands.sandbox_backend import save_windows_backend  # noqa: PLC0415

    root = request.app.state.workspace_root
    ok, reason = NativeSandboxDriver(root).reset_wsl()
    _audit_workspace(
        request, auth_data[0].principal_id, "", "command_sandbox_wsl_removed",
        {"ok": ok, "reason_code": reason or None},
    )
    if not ok:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, reason)
    choice = save_windows_backend(root, "account")
    view: CommandSandboxView = _sandbox_view(request, choice)
    return serialize_dto(view)


# ── Disposable task workspaces: review, promote, discard ─────────────────────


def _workspaces(request: Request) -> TaskWorkspaceRegistry:
    from raiker.execution.commands.backends.native import task_workspace_registry  # noqa: PLC0415

    return task_workspace_registry(request.app.state.workspace_root)


def _workspace_view(
    request: Request, key: str, session_id: str, workspace: TaskWorkspace
) -> TaskWorkspaceView:
    diff = diff_workspace(workspace)
    root = Path(request.app.state.workspace_root).resolve()
    try:
        source = workspace.source.relative_to(root).as_posix() or "."
    except ValueError:
        source = workspace.source.name
    return {
        "workspace_id": key,
        "session_id": session_id,
        "source": source,
        "created_at": workspace.created_at,
        "created": list(diff.created),
        "modified": list(diff.modified),
        "deleted": list(diff.deleted),
        "rejected": [{"path": path, "reason": reason} for path, reason in diff.rejected],
        "conflicts": _safe_conflicts(workspace, diff),
    }


def _safe_conflicts(workspace: TaskWorkspace, diff: Any) -> list[str]:
    """The listing must not fail because one project path became a link: that
    path is refused at Apply anyway, so it is reported as a conflict here."""
    try:
        return list(promotion_conflicts(workspace, diff))
    except WorkspaceError as exc:
        return [exc.detail] if exc.detail else []


def _refuse_while_running(request: Request, owner: str, session_id: str) -> None:
    """A copy a command is still writing cannot be reviewed as finished."""
    for run in _service(request).store.list_runs(owner, limit=500):
        if run.session_id == session_id and run.state not in TERMINAL_COMMAND_STATES:
            raise refusal(status.HTTP_409_CONFLICT, "workspace_in_use")


def _audit_workspace(
    request: Request, owner: str, session_id: str, event_type: str, payload: dict[str, Any]
) -> None:
    """Paths and counts only — never file content."""
    from raiker.events.types import make_event  # noqa: PLC0415
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415
    from raiker.storage.sqlite import SQLiteStore  # noqa: PLC0415

    store = SQLiteStore(request.app.state.workspace_root)
    audit_session = f"sess_inbox_{owner}"
    with contextlib.suppress(Exception):
        store.create_session(audit_session, str(request.app.state.workspace_root), title="Inbox")
    EventLogWriter(store).append(
        make_event(
            session_id=audit_session,
            turn_id=None,
            event_type=event_type,
            actor="owner",
            payload={"principal_id": owner, "task_session_id": session_id, **payload},
        )
    )


@router.get("/api/command-workspaces")
def list_task_workspaces(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    owner = auth_data[0].principal_id
    listed: TaskWorkspaceList = {
        "workspaces": [
            _workspace_view(request, key, session_id, workspace)
            for key, session_id, workspace in _workspaces(request).entries(owner)
        ]
    }
    return serialize_dto(listed)


@router.get("/api/command-workspaces/{workspace_id}/diff")
def task_workspace_file_diff(
    workspace_id: str,
    request: Request,
    path: str = Query(..., min_length=1, max_length=4096),
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """One changed file's unified diff, project against copy, for review.

    Only a path in the copy's change set is answered, so this reads nothing
    the review does not already list.
    """
    from raiker.execution.workspaces import file_diff  # noqa: PLC0415

    owner = auth_data[0].principal_id
    try:
        workspace = _workspaces(request).load(owner, workspace_id)
        changed = file_diff(workspace, diff_workspace(workspace), path)
    except WorkspaceError as exc:
        raise refusal(status.HTTP_404_NOT_FOUND, exc.reason_code) from exc
    if changed is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "workspace_path_unchanged")
    answer: TaskWorkspaceFileDiff = {
        "workspace_id": workspace_id,
        "path": changed.path,
        "status": cast(Literal["created", "modified", "deleted"], changed.status),
        "diff": changed.text,
        "binary": changed.binary,
        "truncated": changed.truncated,
    }
    return serialize_dto(answer)


@router.post("/api/command-workspaces/{workspace_id}/promote")
def promote_task_workspace(
    workspace_id: str,
    body: PromoteTaskWorkspaceRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Apply the reviewed change set to the project, all or nothing."""
    owner = auth_data[0].principal_id
    registry = _workspaces(request)
    try:
        workspace = registry.load(owner, workspace_id)
    except WorkspaceError as exc:
        raise refusal(status.HTTP_404_NOT_FOUND, exc.reason_code) from exc
    session_id = next(
        (session for key, session, _ in registry.entries(owner) if key == workspace_id), ""
    )
    _refuse_while_running(request, owner, session_id)
    diff = diff_workspace(workspace)
    reviewed = (sorted(body.created), sorted(body.modified), sorted(body.deleted))
    if reviewed != (list(diff.created), list(diff.modified), list(diff.deleted)):
        raise refusal(status.HTTP_409_CONFLICT, "workspace_review_stale")
    overwrite = frozenset(body.overwrite)
    try:
        if not overwrite <= set(promotion_conflicts(workspace, diff)):
            # An overwrite the owner did not see as a conflict is not consent.
            raise WorkspaceError("workspace_review_stale")
        result = promote(workspace, diff, overwrite=overwrite)
    except WorkspaceError as exc:
        raise refusal(status.HTTP_409_CONFLICT, exc.reason_code) from exc
    registry.release(owner, workspace_id)
    _audit_workspace(
        request, owner, session_id, "task_workspace_promoted",
        {
            "workspace_id": workspace_id,
            "created": list(result.created),
            "modified": list(result.modified),
            "deleted": list(result.deleted),
            "rejected_count": len(diff.rejected),
            "overwritten": sorted(overwrite),
        },
    )
    promoted: TaskWorkspacePromoted = {
        "ok": True,
        "workspace_id": workspace_id,
        "created": list(result.created),
        "modified": list(result.modified),
        "deleted": list(result.deleted),
    }
    return serialize_dto(promoted)


@router.post("/api/command-workspaces/{workspace_id}/discard")
def discard_task_workspace(
    workspace_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Throw the copy away. The project is unchanged."""
    owner = auth_data[0].principal_id
    registry = _workspaces(request)
    try:
        workspace = registry.load(owner, workspace_id)
    except WorkspaceError as exc:
        raise refusal(status.HTTP_404_NOT_FOUND, exc.reason_code) from exc
    session_id = next(
        (session for key, session, _ in registry.entries(owner) if key == workspace_id), ""
    )
    _refuse_while_running(request, owner, session_id)
    diff = diff_workspace(workspace)
    registry.release(owner, workspace_id)
    _audit_workspace(
        request, owner, session_id, "task_workspace_discarded",
        {
            "workspace_id": workspace_id,
            "changed_count": len(diff.created) + len(diff.modified) + len(diff.deleted),
        },
    )
    discarded: TaskWorkspaceDiscarded = {"ok": True, "workspace_id": workspace_id}
    return serialize_dto(discarded)
