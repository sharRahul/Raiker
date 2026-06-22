from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import ResolveApprovalRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.approvals import ApprovalInbox
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# resolve() raises these on bad input; map each to a stable HTTP status + reason_code.
_RESOLVE_ERRORS = {
    "approval_not_found": status.HTTP_404_NOT_FOUND,
    "approval_already_resolved": status.HTTP_409_CONFLICT,
    "approval_payload_tampered": status.HTTP_409_CONFLICT,
}


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _service(request: Request) -> DashboardService:
    return DashboardService(_ws(request))


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


@router.get("/api/approvals")
async def list_approvals(
    request: Request,
    status_filter: str = "pending",
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_approvals(status=status_filter))


@router.get("/api/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_approval(approval_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown approval: {approval_id}"
        )
    return serialize_dto(view)


@router.post("/api/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: str,
    body: ResolveApprovalRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    inbox = ApprovalInbox(store, EventLogWriter(store))
    try:
        resolution = inbox.resolve(
            approval_id,
            approve=body.approve,
            resolved_by=session.principal_id,
            reason=body.reason,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=_RESOLVE_ERRORS.get(code, status.HTTP_400_BAD_REQUEST),
            detail={"ok": False, "reason_code": code},
        ) from exc
    # The response states the metadata-only limitation explicitly: a decision was recorded,
    # the action was NOT executed.
    return {
        "approval_id": resolution.approval_id,
        "action_id": resolution.action_id,
        "status": resolution.status,
        "executes_action": resolution.executes_action,
        "reason": body.reason,
    }
