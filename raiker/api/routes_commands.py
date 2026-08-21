from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.execution.commands.models import CommandReceipt, StoredCommandRun
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.execution.commands.store import ReceiptImmutable
from raiker.runtime.authority.models import Principal

router = APIRouter()


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(request.app.state.workspace_root).authenticate(request)


def _service(request: Request) -> CommandService:
    service = getattr(request.app.state, "command_service", None)
    if service is None:
        service = CommandService.for_workspace(request.app.state.workspace_root)
        request.app.state.command_service = service
    return service


def _run_view(run: StoredCommandRun) -> dict[str, Any]:
    value = asdict(run)
    value["state"] = run.state.value
    value.pop("owner_principal_id", None)
    value.pop("acting_principal_id", None)
    value.pop("template_digest", None)
    return value


def _receipt_view(receipt: CommandReceipt) -> dict[str, Any]:
    return {
        "run_id": receipt.run_id,
        "state": receipt.state.value,
        "exit_code": receipt.exit_code,
        "termination_reason": receipt.termination_reason,
        "completed_at": receipt.completed_at,
        "evidence": receipt.evidence,
        "digest": receipt.digest,
    }


def _raise_service(exc: CommandServiceError) -> NoReturn:
    code = status.HTTP_404_NOT_FOUND if exc.reason_code == "command_run_not_found" else status.HTTP_409_CONFLICT
    raise HTTPException(
        status_code=code,
        detail={"ok": False, "reason_code": exc.reason_code},
    ) from exc


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
    return {"runs": [_run_view(run) for run in runs]}


@router.get("/api/command-runs/{run_id}")
def get_command(
    run_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    run = _service(request).store.load(auth_data[0].principal_id, run_id)
    if run is None:
        _raise_service(CommandServiceError("command_run_not_found"))
    return {"run": _run_view(run)}


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
    return {"chunks": chunks, "next_after": chunks[-1]["sequence"] if chunks else after}


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
    return {"receipt": _receipt_view(receipt) if receipt else None}


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
    return {"ok": True, "run": _run_view(run)}


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
    deltas: list[dict[str, Any]] = []
    for row in rows:
        try:
            manifest = json.loads(str(row["safe_manifest_json"]))
        except (TypeError, ValueError):
            manifest = {"files": []}
        deltas.append(
            {
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
    return {"deltas": deltas}


@router.post("/api/credential-deltas/{run_id}/discard")
def discard_credential_delta(
    run_id: str,
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    decision_id = str(body.get("decision_id", "")).strip()
    if not decision_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": "credential_delta_decision_required"},
        )
    try:
        changed = _service(request).store.resolve_credential_delta(
            auth_data[0].principal_id,
            run_id,
            decision_id=decision_id,
            resolution="discarded",
        )
    except ReceiptImmutable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "credential_delta_not_found"},
        )
    return {"ok": True, "receipt": _service(request).store.get_delta_receipt(auth_data[0].principal_id, run_id)}
