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

from fastapi import APIRouter, Request

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import SettingsRequest
from raiker.auth.accounts import AccountService
from raiker.auth.vault_key_file import vault_status
from raiker.contracts.ids import utc_now
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
