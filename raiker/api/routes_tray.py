from __future__ import annotations

import hashlib
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, Request, status
from pydantic import Field

from raiker.api.refusals import refusal
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.sessions import ApiSessionStore
from raiker.api.wire.settings import TraySession
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


class TraySessionRequest(StrictRequest):
    secret: str = Field(min_length=1, max_length=512)


@router.post("/api/tray/session")
def exchange_tray_session(body: TraySessionRequest, request: Request) -> dict[str, object]:
    expected = getattr(request.app.state, "tray_bootstrap_digest", None)
    expires = float(getattr(request.app.state, "tray_bootstrap_expires", 0.0))
    used = bool(getattr(request.app.state, "tray_bootstrap_used", False))
    supplied = hashlib.sha256(body.secret.encode()).hexdigest()
    if used or time.monotonic() > expires or not isinstance(expected, str) or not secrets.compare_digest(supplied, expected):
        raise refusal(status.HTTP_401_UNAUTHORIZED, "tray_bootstrap_invalid")
    principals = [
        principal
        for principal in SQLiteStore(request.app.state.workspace_root).list_principals()  # type: ignore[attr-defined]
        if principal.get("principal_type") == "human" and "rl_owner" in principal.get("role_ids", ())
    ]
    if len(principals) != 1:
        raise refusal(status.HTTP_409_CONFLICT, "tray_owner_unavailable")
    request.app.state.tray_bootstrap_used = True
    token, session = ApiSessionStore(Path(request.app.state.workspace_root)).create_session(  # type: ignore[attr-defined]
        str(principals[0]["principal_id"]),
        scopes=("host_control",),
        expires_in_seconds=3600,
        absolute_expires_in_seconds=3600,
        scope="host_control",
        device_label="Raiker native tray",
    )
    answer: TraySession = {"token": token, "expires_at": session.expires_at, "scope": session.scope}
    return serialize_dto(answer)
