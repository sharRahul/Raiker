"""Connector vault master-key management.

The vault key encrypts connector credentials. It is set/cleared through the web
app behind an ``elevated`` session (re-auth). When the account opts into
"require MFA for Vault operations" and has MFA enrolled, a fresh TOTP code must
also accompany the change. Missing/invalid key => connectors fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, Request, status
from typing_extensions import TypedDict

from raiker.api.auth import AuthMiddleware
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.refusals import refusal
from raiker.api.schemas import VaultKeyRequest, serialize_dto
from raiker.auth.accounts import AccountService
from raiker.auth.vault_key_file import (
    VaultState,
    clear_vault_key,
    vault_status,
    write_vault_key,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

REQUIRE_MFA_KEY = "security.require_mfa_for_vault"


class VaultStatus(TypedDict):
    """Whether the connector vault has a usable key; never the key."""

    state: VaultState


def _status(ws: str | Path) -> VaultStatus:
    return {"state": vault_status(ws)}


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
    policy_on = settings.get(REQUIRE_MFA_KEY) and service.mfa_enrolled(principal_id)
    if policy_on and (not mfa_code or not service.verify_mfa_code(principal_id, mfa_code)):
        raise refusal(status.HTTP_403_FORBIDDEN, "mfa_required_for_vault")


@router.get("/api/vault/status")
async def get_vault_status(request: Request) -> dict[str, Any]:
    AuthMiddleware(_ws(request)).authenticate(request)
    return serialize_dto(_status(_ws(request)))


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
        raise refusal(status.HTTP_400_BAD_REQUEST, "connector_vault_key_invalid") from exc
    return serialize_dto(_status(ws))


@router.delete("/api/vault/key")
async def delete_vault_key(
    request: Request,
    x_mfa_code: str | None = Header(default=None),
) -> dict[str, Any]:
    # The second-factor code is taken from a header (never a query parameter) so
    # it cannot leak into access logs or browser history.
    _session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    ws = _ws(request)
    _enforce_vault_mfa_policy(ws, principal.principal_id, x_mfa_code)
    clear_vault_key(ws)
    return serialize_dto(_status(ws))
