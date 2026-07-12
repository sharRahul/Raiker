from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ToolAction
from raiker.runtime.authority.models import Principal
from raiker.runtime.connector_ecosystem import (
    ConnectorCatalog,
    ConnectorInvoker,
    ConnectorVault,
    compile_manifest,
    credential_status,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


class CredentialRequest(BaseModel):
    values: dict[str, str] = Field(min_length=1, max_length=12)
    expires_at: str | None = None


class ManifestRequest(BaseModel):
    manifest: dict[str, Any]


class ConnectorActionRequest(BaseModel):
    operation_id: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str = Field(default="connector_store", max_length=200)


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _installation(store: SQLiteStore, principal_id: str, connector_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM connector_installations WHERE principal_id=? AND connector_id=?",
            (principal_id, connector_id),
        ).fetchone()
    return dict(row) if row else None


def _credential_meta(store: SQLiteStore, principal_id: str, connector_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT expires_at, updated_at FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            (principal_id, connector_id),
        ).fetchone()
    return dict(row) if row else None


@router.get("/api/connector-store")
async def connector_store(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    items: list[dict[str, Any]] = []
    for definition in ConnectorCatalog().list():
        installed = _installation(store, session.principal_id, definition.connector_id)
        credential = _credential_meta(store, session.principal_id, definition.connector_id)
        auth_status = credential_status(credential.get("expires_at")) if credential else "not_connected"
        with store.connect() as connection:
            activity = connection.execute(
                """SELECT status, operation_id, started_at FROM connector_invocations
                   WHERE principal_id=? AND connector_id=? ORDER BY started_at DESC LIMIT 1""",
                (session.principal_id, definition.connector_id),
            ).fetchone()
        items.append(
            {
                "connector_id": definition.connector_id,
                "display_name": definition.name,
                "category": definition.category,
                "description": definition.description,
                "auth_type": definition.auth_type,
                "host": definition.host,
                "installed": installed is not None,
                "enabled": bool(installed and installed["enabled"]),
                "auth_status": auth_status,
                "vault_configured": ConnectorVault.configured(),
                "activity_status": activity["status"] if activity else "idle",
                "active_operation": activity["operation_id"] if activity else None,
                "last_invoked_at": activity["started_at"] if activity else None,
            }
        )
    return {"connectors": items, "count": len(items), "vault_configured": ConnectorVault.configured()}


@router.post("/api/connector-store/{connector_id}/install")
async def install_connector(
    connector_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    try:
        ConnectorCatalog().get(connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"reason_code": str(exc)}) from exc
    now = utc_now()
    store = SQLiteStore(_ws(request))
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO connector_installations
               (principal_id, connector_id, enabled, auth_status, installed_at, updated_at)
               VALUES (?, ?, 0, 'not_connected', ?, ?)
               ON CONFLICT(principal_id, connector_id) DO UPDATE SET updated_at=excluded.updated_at""",
            (session.principal_id, connector_id, now, now),
        )
    return {"ok": True, "connector_id": connector_id, "installed": True, "enabled": False}


@router.delete("/api/connector-store/{connector_id}")
async def uninstall_connector(
    connector_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    with store.connect() as connection:
        connection.execute(
            "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            (session.principal_id, connector_id),
        )
        cursor = connection.execute(
            "DELETE FROM connector_installations WHERE principal_id=? AND connector_id=?",
            (session.principal_id, connector_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail={"reason_code": "connector_not_installed"})
    return {"ok": True, "connector_id": connector_id, "installed": False}


@router.put("/api/connector-store/{connector_id}/enabled")
async def set_connector_enabled(
    connector_id: str,
    enabled: bool,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    credential = _credential_meta(store, session.principal_id, connector_id)
    if enabled and (credential is None or credential_status(credential.get("expires_at")) != "connected"):
        raise HTTPException(status_code=409, detail={"reason_code": "connector_auth_required"})
    with store.connect() as connection:
        cursor = connection.execute(
            "UPDATE connector_installations SET enabled=?, updated_at=? WHERE principal_id=? AND connector_id=?",
            (int(enabled), utc_now(), session.principal_id, connector_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail={"reason_code": "connector_not_installed"})
    return {"ok": True, "connector_id": connector_id, "enabled": enabled}


@router.put("/api/connector-store/{connector_id}/credentials")
async def set_connector_credentials(
    connector_id: str,
    body: CredentialRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    ConnectorCatalog().get(connector_id)
    store = SQLiteStore(_ws(request))
    if _installation(store, session.principal_id, connector_id) is None:
        raise HTTPException(status_code=409, detail={"reason_code": "connector_not_installed"})
    try:
        ConnectorVault(store).put(session.principal_id, connector_id, body.values, body.expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"reason_code": str(exc)}) from exc
    with store.connect() as connection:
        connection.execute(
            "UPDATE connector_installations SET auth_status='connected', updated_at=? WHERE principal_id=? AND connector_id=?",
            (utc_now(), session.principal_id, connector_id),
        )
    return {"ok": True, "connector_id": connector_id, "auth_status": "connected"}


@router.post("/api/connector-store/{connector_id}/manifest")
async def register_connector_manifest(
    connector_id: str,
    body: ManifestRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    try:
        compiled = compile_manifest(body.manifest)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"reason_code": str(exc)}) from exc
    raw = json.dumps(body.manifest, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    store = SQLiteStore(_ws(request))
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO connector_manifests
               (connector_id, manifest_json, manifest_sha256, installed_by, installed_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(connector_id) DO UPDATE SET manifest_json=excluded.manifest_json,
               manifest_sha256=excluded.manifest_sha256, installed_by=excluded.installed_by,
               installed_at=excluded.installed_at""",
            (connector_id, raw, digest, session.principal_id, utc_now()),
        )
    return {"ok": True, "connector_id": connector_id, "manifest_sha256": digest, **compiled}


@router.post("/api/connector-store/{connector_id}/actions")
async def invoke_connector_action(
    connector_id: str,
    body: ConnectorActionRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    installation = _installation(store, session.principal_id, connector_id)
    if installation is None or not installation["enabled"]:
        raise HTTPException(status_code=409, detail={"reason_code": "connector_not_enabled"})
    invoker = ConnectorInvoker(store)
    try:
        operation, _base_url = invoker._operation(connector_id, body.operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"reason_code": str(exc)}) from exc
    if operation["requires_confirmation"]:
        action_id = new_id("act_")
        approval_id = new_id("appr_")
        intent_id = new_id("cwi_")
        action = ToolAction(
            action_id=action_id,
            tool_name="connector_write",
            arguments={
                "connector_id": connector_id,
                "operation_id": body.operation_id,
                "arguments": body.arguments,
            },
            risk_level="high",
            requires_approval=True,
            proposed_by=session.principal_id,
        )
        store.insert_tool_action(action, body.session_id, None, "approval_required")
        store.insert_approval(approval_id, action)
        with store.connect() as connection:
            connection.execute(
                """INSERT INTO connector_write_intents
                   (intent_id, approval_id, principal_id, connector_id, operation_id,
                    arguments_json, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending_approval', ?)""",
                (
                    intent_id,
                    approval_id,
                    session.principal_id,
                    connector_id,
                    body.operation_id,
                    json.dumps(body.arguments, sort_keys=True),
                    utc_now(),
                ),
            )
        return {
            "status": "approval_required",
            "approval_id": approval_id,
            "intent_id": intent_id,
            "connector_id": connector_id,
            "operation_id": body.operation_id,
            "executes_action": False,
        }
    try:
        result = await invoker.invoke(
            session.principal_id, connector_id, body.operation_id, body.arguments
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"reason_code": str(exc)}) from exc
    return {"status": "completed", **result}
