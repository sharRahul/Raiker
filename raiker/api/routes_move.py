"""Move Raiker to another machine (RU-17).

``POST /api/move/export`` hands the owner a passphrase-sealed move file to
save; it carries the workspace key inside the seal, so it takes a recent
step-up, as rotating that key does.

``GET /api/move/status`` and ``POST /api/move/import`` are first run's *I have
a backup*. They take no session, because there is no account yet, and stand on
what the lock screen's recovery stands on (``routes_recovery``): only from
this machine, only from Raiker's own page, and only while the workspace has no
account — ``import_move`` checks that again before it switches anything in.
The file arrives as the raw request body and the passphrase in a header; a
cross-site page cannot send either without a preflight this server never
answers.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.routes_recovery import _require_this_machine
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.control import MoveStatusView
from raiker.runtime.authority.models import Principal
from raiker.storage.move import (
    MAX_BYTES,
    MIN_PASSPHRASE,
    MoveError,
    export_move,
    import_move,
    workspace_has_account,
)

router = APIRouter()



class MoveExportRequest(StrictRequest):
    passphrase: str


def _workspace(request: Request) -> Path:
    return Path(request.app.state.workspace_root)  # type: ignore[attr-defined]


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host", ""):
        raise refusal(status.HTTP_403_FORBIDDEN, "move_cross_origin")


@router.post("/api/move/export")
async def move_export(
    body: MoveExportRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    session, _principal = auth_data
    if session.scope != "elevated":
        raise refusal(status.HTTP_403_FORBIDDEN, "move_requires_step_up")
    workspace = _workspace(request)
    from raiker.storage.sqlite import SQLiteStore

    out = workspace / ".raiker" / "moving-out"
    try:
        exported = await asyncio.to_thread(
            lambda: export_move(SQLiteStore(workspace).connect(), workspace, out, body.passphrase)
        )
        data = exported.path.read_bytes()
    except MoveError as exc:
        raise refusal(status.HTTP_409_CONFLICT if exc.reason != "move_passphrase_short" else 422, exc.reason) from exc
    finally:
        shutil.rmtree(out, ignore_errors=True)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{exported.path.name}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/api/move/status")
async def move_status(request: Request) -> dict[str, Any]:
    """Whether this Raiker can open a move file now: first run, from this machine."""
    _require_this_machine(request)
    in_use = await asyncio.to_thread(workspace_has_account, _workspace(request))
    answer: MoveStatusView = {"can_import": not in_use, "min_passphrase": MIN_PASSPHRASE, "max_bytes": MAX_BYTES}
    return serialize_dto(answer)


@router.post("/api/move/import")
async def move_import(request: Request) -> dict[str, Any]:
    _require_this_machine(request)
    _require_same_origin(request)
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/octet-stream":
        raise refusal(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "move_file_required")
    passphrase = request.headers.get("x-raiker-move-passphrase", "")
    if not passphrase:
        raise refusal(422, "move_passphrase_required")
    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_BYTES:
        raise refusal(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "move_file_too_large")
    blob = await request.body()
    try:
        result = await asyncio.to_thread(import_move, _workspace(request), blob, passphrase)
    except MoveError as exc:
        code = {
            "move_workspace_in_use": status.HTTP_409_CONFLICT,
            "move_file_too_large": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        }.get(exc.reason, 422)
        raise refusal(code, exc.reason) from exc
    return serialize_dto(
        {
            "ok": True,
            "created_at": result.created_at,
            "counts": result.counts,
            "keys_removed": result.keys_removed,
            "quarantine": result.quarantine,
        }
    )


__all__ = ["MoveExportRequest", "router"]
