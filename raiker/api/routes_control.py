from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ActivateRuntimeModeRequest,
    CreateStandingGrantRequest,
    CreateTelemetryDestinationRequest,
    DisableCapabilityRequest,
    DisableRuntimeModeRequest,
    RecordThreatModelAckRequest,
    SetCapabilityDecisionModeRequest,
    SetCapabilityStateRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.storage.sqlite import store_health

router = APIRouter()


def _get_auth(request: Request) -> AuthMiddleware:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(ws)


def _get_service(request: Request) -> RuntimeControlService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    registry: ExecutorRegistry | None = getattr(request.app.state, "executor_registry", None)
    return RuntimeControlService(ws, executor_registry=registry)


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return _get_auth(request).authenticate(request)


def _deny(result_reason: str | None = None) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"ok": False, "reason_code": result_reason or "denied"},
    )


def _set_capability_decision_mode(
    capability: str,
    mode: str,
    body: SetCapabilityDecisionModeRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal],
) -> dict[str, Any]:
    session, _principal = auth_data
    service = _get_service(request)
    result = service.set_capability_decision_mode(
        capability,
        mode,
        session.principal_id,
        body.reason,
    )
    if not result.ok:
        _deny(result.reason_code)
    decision_mode = result.data.get("decision_mode", mode)
    return {"ok": True, "capability": capability, "decision_mode": decision_mode}


@router.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    """Liveness *and* whether the encrypted store can be opened (BUG-86).

    The probe used to answer ``{"status": "ok"}`` without reading anything, so
    the lock screen's status strip could call the runtime operational while
    every sign-in on the same screen failed on a store that would not open.
    ``status`` stays ``ok`` only while both are true; the response is a 200
    either way, because the *server* is answering — it is the store that is
    degraded, and the caller needs to be told which.
    """
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    health_view = store_health(ws)
    return {"status": "ok" if health_view["store"] == "ok" else "degraded", **health_view}


@router.get("/api/runtime-mode")
async def get_runtime_mode(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    service = _get_service(request)
    return serialize_dto(service.get_runtime_mode(auth_data[0].principal_id))


@router.post("/api/runtime-mode/activate")
async def activate_runtime_mode(
    body: ActivateRuntimeModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.activate_runtime_mode(body.mode_name, session.principal_id, body.reason)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, "mode_name": body.mode_name}


@router.post("/api/runtime-mode/disable")
async def disable_runtime_mode(
    body: DisableRuntimeModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.disable_runtime_mode(session.principal_id, body.reason)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True}


@router.get("/api/capability-gates")
async def list_capability_gates(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    _session, principal = _auth_data
    service = _get_service(request)
    gates = service.list_capability_gates(principal.principal_id)
    return serialize_dto(gates)


@router.get("/api/capability-gates/{capability}")
async def get_capability_gate(
    capability: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    service = _get_service(request)
    gate = service.get_capability_gate(capability, principal.principal_id)
    if gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown capability: {capability}")
    return serialize_dto(gate)


@router.post("/api/capability-gates/{capability}/set")
async def set_capability_state(
    capability: str,
    body: SetCapabilityStateRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.set_capability_state(
        capability,
        body.target_state,
        session.principal_id,
        body.reason,
        confirmation_token=body.confirmation_token,
    )
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, "capability": capability, "target_state": body.target_state}


@router.post("/api/capability-gates/{capability}/threat-ack")
async def record_threat_model_ack(
    capability: str,
    body: RecordThreatModelAckRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Record a human threat-model acknowledgement for a capability.

    This is the in-app, governed equivalent of the operator/CLI ack step that
    activation of threat-ack-gated capabilities (e.g. hosted model runtimes)
    requires. It records the acknowledgement only — it does not enable anything.
    """
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.record_threat_model_ack(capability, session.principal_id, body.reason)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, "capability": capability, "acknowledged": True}


@router.post("/api/capability-gates/{capability}/disable")
async def disable_capability(
    capability: str,
    body: DisableCapabilityRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.disable_capability(capability, session.principal_id, body.reason)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, "capability": capability}


@router.get("/api/capability-modes/{capability}")
async def get_capability_decision_mode(
    capability: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    service = _get_service(request)
    result = service.get_capability_decision_mode(capability, auth_data[0].principal_id)
    return {"ok": result.ok, **result.data}


@router.post("/api/capability-modes/{capability}/ask")
async def ask_for_capability(
    capability: str,
    body: SetCapabilityDecisionModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _set_capability_decision_mode(capability, "ask", body, request, _auth_data)


@router.post("/api/capability-modes/{capability}/allow")
async def allow_capability(
    capability: str,
    body: SetCapabilityDecisionModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _set_capability_decision_mode(capability, "allow", body, request, _auth_data)


@router.post("/api/capability-modes/{capability}/auto")
async def auto_capability(
    capability: str,
    body: SetCapabilityDecisionModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _set_capability_decision_mode(capability, "auto", body, request, _auth_data)


@router.post("/api/capability-modes/{capability}/deny")
async def deny_capability(
    capability: str,
    body: SetCapabilityDecisionModeRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _set_capability_decision_mode(capability, "deny", body, request, _auth_data)


@router.get("/api/runtime-readiness")
async def get_runtime_readiness(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    service = _get_service(request)
    readiness = service.get_runtime_readiness(principal.principal_id)
    return serialize_dto(readiness)


# ── Scoped standing approval grants (Workstream F / F3, ZT-5) ────────────────


@router.get("/api/standing-grants")
async def list_standing_grants(
    request: Request,
    include_inactive: bool = True,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """List the owner's standing grants for Security Settings (newest first)."""
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.list_standing_grants(
        session.principal_id, include_inactive=include_inactive
    )
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.post("/api/standing-grants")
async def create_standing_grant(
    body: CreateStandingGrantRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Create a scoped standing grant (a critical, human-decided action)."""
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.create_standing_grant(
        session.principal_id,
        action_type=body.action_type,
        risk_ceiling=body.risk_ceiling,
        tool_name=body.tool_name,
        scope_pattern=body.scope_pattern,
        reason=body.reason,
        ttl_days=body.ttl_days,
    )
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.post("/api/standing-grants/{grant_id}/revoke")
async def revoke_standing_grant(
    grant_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Revoke a standing grant. Immediate — the resting state is deny."""
    session, _principal = _auth_data
    service = _get_service(request)
    result = service.revoke_standing_grant(grant_id, session.principal_id)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, "grant_id": grant_id}


# ── Audit export (BUG-231) ───────────────────────────────────────────────────
# Raiker keeps an append-only, account-scoped audit log and calls it evidence.
# Evidence that cannot leave the product is evidence that cannot be used in a
# review, an incident write-up, or a second tool. These three routes are how it
# leaves: ask for one, list what has been produced, and download one file.
#
# The export itself is a governed action — it passes the `audit_export`
# capability gate, the policy review and the posture check, and appears in the
# log it exported. Scope is the acting principal's own account, resolved inside
# the executor from the principal rather than from any argument, and every
# payload is redacted exactly as the on-screen record is.


@router.post("/api/audit/export")
async def create_audit_export(
    request: Request,
    session_id: str | None = None,
    project_id: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Produce a redacted export of the acting principal's own audit log."""
    session, _principal = auth_data
    result = _get_service(request).export_audit_log(
        session.principal_id, session_id=session_id, project_id=project_id
    )
    if not result.ok:
        if result.reason_code == "audit_export_empty":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"ok": False, "reason_code": "audit_export_empty"},
            )
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.get("/api/audit/exports")
async def list_audit_exports(
    request: Request,
    limit: int = 20,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """The manifests already produced, newest first.

    Metadata only: the id, the content hash over the exact event ids and scope,
    the event count, the window, and whether it was redacted. Never the events.
    """
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    from raiker.storage.sqlite import SQLiteStore

    rows = SQLiteStore(ws).list_audit_exports(limit=max(1, min(limit, 200)))
    return [
        {
            "export_id": str(row["export_id"]),
            "manifest_hash": str(row["manifest_hash"]),
            "event_count": int(row["event_count"] or 0),
            "redacted": bool(row["redacted"]),
            "first_timestamp": row["first_timestamp"],
            "last_timestamp": row["last_timestamp"],
            "exported_by": row["exported_by"],
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


# ── Telemetry export (compatibility backlog #18) ─────────────────────────────
# Raiker records more per governed action than any compared product exports, and
# had no wire to carry it anywhere. These four routes are that wire's controls:
# list the collectors, add one, remove one, and run a delivery.
#
# The delivery is a governed action — it passes the `telemetry_export` gate, the
# policy review and the posture check, and appears in the log it exported.
# Metadata only unless the owner opted into redacted content, and the credential
# is an environment-variable *name* rather than a value.


@router.get("/api/telemetry/destinations")
async def list_telemetry_destinations(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """The acting principal's own OTLP destinations, newest first."""
    session, _principal = auth_data
    result = _get_service(request).list_telemetry_destinations(session.principal_id)
    if not result.ok:
        _deny(result.reason_code)
    return list(result.data.get("destinations", []))


@router.post("/api/telemetry/destinations")
async def create_telemetry_destination(
    request: Request,
    body: CreateTelemetryDestinationRequest,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    result = _get_service(request).create_telemetry_destination(
        session.principal_id,
        name=body.name,
        endpoint_url=body.endpoint_url,
        header_ref=body.header_ref,
        include_content=body.include_content,
    )
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.delete("/api/telemetry/destinations/{destination_id}")
async def delete_telemetry_destination(
    destination_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    result = _get_service(request).delete_telemetry_destination(
        session.principal_id, destination_id
    )
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.post("/api/telemetry/destinations/{destination_id}/export")
async def run_telemetry_export(
    destination_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Deliver every governed event this destination has not had yet."""
    session, _principal = auth_data
    result = _get_service(request).run_telemetry_export(session.principal_id, destination_id)
    if not result.ok:
        _deny(result.reason_code)
    return {"ok": True, **result.data}


@router.get("/api/audit/exports/{export_id}/download")
async def download_audit_export(
    export_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> FileResponse:
    """Hand the export file over.

    The path is read from the manifest row and re-resolved against this
    workspace's own exports directory, so a stored value can never address a
    file outside it.
    """
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(ws)
    row = store.load_audit_export(export_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown export: {export_id}"
        )
    exports_dir = (EventLogWriter(store).events_dir.parent / "exports").resolve()
    path = (exports_dir / f"{export_id}.jsonl").resolve()
    if path.parent != exports_dir or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "audit_export_file_missing"},
        )
    return FileResponse(
        path, media_type="application/x-ndjson", filename=f"{export_id}.jsonl"
    )
