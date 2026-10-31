from __future__ import annotations

import contextlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, NoReturn, cast

from fastapi import APIRouter, Depends, Query, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.schemas import PromoteTaskWorkspaceRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.commands import (
    CommandOutput,
    CommandReceiptAnswer,
    CommandReceiptView,
    CommandRunDetail,
    CommandRunList,
    CommandRunState,
    CommandRunView,
    CommandStopped,
    CredentialDeltaDiscarded,
    CredentialDeltaList,
    CredentialDeltaView,
    TaskWorkspaceDiscarded,
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
    }


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
    try:
        result = promote(workspace, diff)
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
