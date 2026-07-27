from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import ResolveApprovalRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.approvals import ApprovalInbox
from raiker.approvals.execution import ApprovalExecutionBridge
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.runtime.authority.router import RuntimeAuthority
from raiker.runtime.connector_ecosystem import ConnectorInvoker
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# resolve() raises these on bad input; map each to a stable HTTP status + reason_code.
_RESOLVE_ERRORS = {
    "approval_not_found": status.HTTP_404_NOT_FOUND,
    "approval_already_resolved": status.HTTP_409_CONFLICT,
    "approval_payload_tampered": status.HTTP_409_CONFLICT,
    "approval_expired": status.HTTP_409_CONFLICT,
}

# The relay reports the same refusals by reason code rather than by exception, so
# an execution that is turned away maps to the identical status the metadata-only
# path would have returned. Anything else is a conflict carrying its reason code.
_EXECUTION_ERRORS = {
    **_RESOLVE_ERRORS,
    "critical_approval_requires_lifecycle": status.HTTP_400_BAD_REQUEST,
    "posture_degraded:session_revoked": status.HTTP_403_FORBIDDEN,
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
    session, _principal = _auth_data
    user_id = SQLiteStore(_ws(request)).principal_user_id(session.principal_id)
    return serialize_dto(
        _service(request).list_approvals(
            status=status_filter, user_id=user_id, principal_id=session.principal_id
        )
    )


@router.get("/api/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    user_id = SQLiteStore(_ws(request)).principal_user_id(session.principal_id)
    view = _service(request).get_approval(
        approval_id, user_id=user_id, principal_id=session.principal_id
    )
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
    session, principal = _auth_data
    store = SQLiteStore(_ws(request))
    inbox = ApprovalInbox(store, EventLogWriter(store))
    user_id = store.principal_user_id(session.principal_id)
    with store.connect() as connection:
        pending_intent_row = connection.execute(
            "SELECT * FROM connector_write_intents WHERE approval_id=?", (approval_id,)
        ).fetchone()
    if pending_intent_row is not None and pending_intent_row["principal_id"] != session.principal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "connector_intent_principal_mismatch"},
        )
    # A connector-store write is owned by the principal named on its intent
    # (checked above), not by a chat session: those actions are recorded against
    # the synthetic "connector_store" session id, which has no sessions row to
    # scope by. Everything else is owned via its session's user.
    owner_user_id = None if pending_intent_row is not None else user_id
    approval_row = store.load_approval(approval_id, user_id=owner_user_id)
    if approval_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"ok": False, "reason_code": "approval_not_found"})

    # BUG-06 — an approved file mutation is actually performed. The relay needs
    # the approval still `pending` (it claims it atomically), so this runs
    # *before* the metadata-only inbox would resolve it. Everything the inbox
    # checks — critical lifecycle, TTL, payload hash, single resolution — the
    # relay re-checks itself, and it adds the posture check and a fresh gate +
    # policy review of the target at execution time.
    bridge = ApprovalExecutionBridge(store, EventLogWriter(store))
    if (
        body.approve
        and pending_intent_row is None
        and bridge.executes_on_resolution(
            str(approval_row.get("tool_name", "")),
            session.principal_id,
            critical=bool(approval_row.get("critical")),
        )
    ):
        execution = bridge.execute(
            approval_row, principal, session_id=session.session_id, reason=body.reason
        )
        if not execution.ok:
            raise HTTPException(
                status_code=_EXECUTION_ERRORS.get(
                    execution.reason_code or "", status.HTTP_409_CONFLICT
                ),
                detail={"ok": False, "reason_code": execution.reason_code},
            )
        return {
            "approval_id": approval_id,
            "action_id": str(approval_row.get("action_id", "")),
            "status": execution.status,
            "executes_action": True,
            "reason": body.reason,
            "execution": {
                "capability": execution.capability,
                "path": execution.artifacts.get("path"),
            },
        }

    try:
        resolution = inbox.resolve(
            approval_id,
            approve=body.approve,
            resolved_by=session.principal_id,
            reason=body.reason,
            user_id=owner_user_id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=_RESOLVE_ERRORS.get(code, status.HTTP_400_BAD_REQUEST),
            detail={"ok": False, "reason_code": code},
        ) from exc
    # Connector write intents are the deliberately narrow exception to Raiker's
    # metadata-only approval resolution. The intent is immutable, principal-
    # bound, single-use, and executes only after this exact approval is accepted.
    if pending_intent_row is not None:
        intent = dict(pending_intent_row)
        if not body.approve:
            with store.connect() as connection:
                connection.execute(
                    "UPDATE connector_write_intents SET status='denied' WHERE intent_id=? AND status='pending_approval'",
                    (intent["intent_id"],),
                )
        else:
            with store.connect() as connection:
                claimed = connection.execute(
                    "UPDATE connector_write_intents SET status='executing' WHERE intent_id=? AND status='pending_approval'",
                    (intent["intent_id"],),
                )
            if claimed.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"ok": False, "reason_code": "connector_intent_already_consumed"},
                )
            try:
                output = await ConnectorInvoker(store).invoke(
                    session.principal_id,
                    str(intent["connector_id"]),
                    str(intent["operation_id"]),
                    json.loads(intent["arguments_json"]),
                )
            except (ValueError, json.JSONDecodeError) as exc:
                with store.connect() as connection:
                    connection.execute(
                        "UPDATE connector_write_intents SET status='failed', executed_at=? WHERE intent_id=?",
                        (utc_now(), intent["intent_id"]),
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"ok": False, "reason_code": str(exc)},
                ) from exc
            with store.connect() as connection:
                connection.execute(
                    "UPDATE connector_write_intents SET status='executed', executed_at=? WHERE intent_id=?",
                    (utc_now(), intent["intent_id"]),
                )
            return {
                "approval_id": resolution.approval_id,
                "action_id": resolution.action_id,
                "status": "executed",
                "executes_action": True,
                "reason": body.reason,
                "connector_result": output,
            }
    return {
        "approval_id": resolution.approval_id,
        "action_id": resolution.action_id,
        "status": resolution.status,
        "executes_action": resolution.executes_action,
        "reason": body.reason,
    }


@router.post("/api/approvals/{approval_id}/resolve-critical")
async def resolve_critical_approval(
    approval_id: str,
    body: ResolveApprovalRequest,
    request: Request,
) -> dict[str, Any]:
    """Resolve a critical approval only through a fresh elevated API session."""
    session, principal = AuthMiddleware(_ws(request)).authenticate(request, required_scope="elevated")
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(session.principal_id)
    approval = store.load_approval(approval_id, user_id=user_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "approval_not_found"},
        )
    if not approval.get("critical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "not_a_critical_approval"},
        )

    result = RuntimeAuthority(store, EventLogWriter(store)).resolve_critical_approval(
        approval_id,
        principal,
        approve=body.approve,
        step_up_verified=True,
        session_id=session.session_id,
        reason=body.reason,
    )
    current = store.load_approval(approval_id, user_id=user_id)
    return {
        "approval_id": approval_id,
        "status": str((current or approval).get("status", "pending")),
        "decision": result.decision,
        "message": result.message,
        "executes_action": result.message == "critical_action_executed",
    }
