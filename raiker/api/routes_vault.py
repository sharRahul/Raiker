"""Connector vault master-key management.

The vault key encrypts connector credentials. It is set/cleared through the web
app behind an ``elevated`` session (re-auth). When the account opts into
"require MFA for Vault operations" and has MFA enrolled, a fresh TOTP code must
also accompany the change. Missing/invalid key => connectors fail closed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import VaultKeyRequest
from raiker.auth.accounts import AccountService
from raiker.auth.vault_key_file import (
    VAULT_KEY_ENV,
    clear_vault_key,
    load_vault_key_into_env,
    vault_status,
    write_vault_key,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

REQUIRE_MFA_KEY = "security.require_mfa_for_vault"


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _settings(ws: str | Path, principal_id: str) -> dict[str, Any]:
    row = SQLiteStore(ws).get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _enforce_vault_mfa_policy(ws: str | Path, principal_id: str, mfa_code: str | None) -> None:
    settings = _settings(ws, principal_id)
    service = AccountService(ws)
    if settings.get(REQUIRE_MFA_KEY) and service.mfa_enrolled(principal_id):
        if not mfa_code or not service.verify_mfa_code(principal_id, mfa_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"ok": False, "reason_code": "mfa_required_for_vault"},
            )


@router.get("/api/vault/status")
async def get_vault_status(request: Request) -> dict[str, Any]:
    AuthMiddleware(_ws(request)).authenticate(request)
    return {"state": vault_status(_ws(request))}


@router.put("/api/vault/key")
async def set_vault_key(body: VaultKeyRequest, request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    ws = _ws(request)
    _enforce_vault_mfa_policy(ws, principal.principal_id, body.mfa_code)
    try:
        write_vault_key(ws, body.key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "connector_vault_key_invalid"},
        ) from exc
    # Make the new key effective for this process (env unset case).
    os.environ.pop(VAULT_KEY_ENV, None)
    load_vault_key_into_env(ws)
    return {"state": vault_status(ws)}


@router.delete("/api/vault/key")
async def delete_vault_key(request: Request, mfa_code: str | None = None) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    ws = _ws(request)
    _enforce_vault_mfa_policy(ws, principal.principal_id, mfa_code)
    clear_vault_key(ws)
    os.environ.pop(VAULT_KEY_ENV, None)
    return {"state": vault_status(ws)}
