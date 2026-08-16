"""Per-account settings (the 9-section settings taxonomy).

Settings are stored per ``principal_id`` as a single JSON blob, so each local
account has its own settings — fully isolated from other accounts on the device.
The client owns the section structure; the server persists and returns it as-is,
plus derived read-only status the UI needs (vault state, MFA enrollment).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import ComposerApprovalModeRequest, SettingsRequest
from raiker.auth.accounts import AccountService
from raiker.auth.vault_key_file import vault_status
from raiker.contracts.ids import utc_now
from raiker.contracts.models import ContractValidationError, normalize_approval_mode
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _load(ws: str | Path, principal_id: str) -> dict[str, Any]:
    row = SQLiteStore(ws).get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def load_reasoning_retention(ws: str | Path, principal_id: str) -> bool:
    """Whether this owner has asked for the model's working to be kept (BUG-215).

    **Off by default, and that default is the posture rather than an oversight.**
    Reasoning can restate anything the prompt contained and it is the one part of
    a turn an owner may specifically not want on disk, so it is retained only on
    an explicit decision. Off does not mean the surface pretends there was none:
    the turn still records *how much* working it produced, so a re-opened turn
    says the working was not kept rather than showing nothing.
    """
    return SQLiteStore(ws).reasoning_retention_enabled(principal_id)


def load_composer_approval_mode(ws: str | Path, principal_id: str) -> str:
    composer = _load(ws, principal_id).get("composer")
    if not isinstance(composer, dict):
        return "manual"
    approval_mode = composer.get("approval_mode")
    if not isinstance(approval_mode, str):
        return "manual"
    try:
        return normalize_approval_mode(approval_mode)
    except ContractValidationError:
        return "manual"


@router.get("/api/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    ws = _ws(request)
    return {
        "settings": _load(ws, principal.principal_id),
        "status": {
            "vault": vault_status(ws),
            "mfa_enrolled": AccountService(ws).mfa_enrolled(principal.principal_id),
            "username": principal.display_name,
        },
    }


@router.put("/api/settings")
async def put_settings(body: SettingsRequest, request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    ws = _ws(request)
    SQLiteStore(ws).put_user_settings(
        principal.principal_id, json.dumps(body.settings), utc_now()
    )
    return {"settings": body.settings}


@router.get("/api/settings/composer-approval-mode")
async def get_composer_approval_mode(request: Request) -> dict[str, str]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    return {"approval_mode": load_composer_approval_mode(_ws(request), principal.principal_id)}


@router.put("/api/settings/composer-approval-mode")
async def put_composer_approval_mode(
    body: ComposerApprovalModeRequest, request: Request
) -> dict[str, str]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        approval_mode = normalize_approval_mode(body.approval_mode)
    except ContractValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None

    ws = _ws(request)
    settings = _load(ws, principal.principal_id)
    composer = settings.get("composer")
    if not isinstance(composer, dict):
        composer = {}
        settings["composer"] = composer
    composer["approval_mode"] = approval_mode
    SQLiteStore(ws).put_user_settings(principal.principal_id, json.dumps(settings), utc_now())
    return {"approval_mode": approval_mode}
