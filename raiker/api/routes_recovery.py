"""Restoring a workspace from the lock screen, when its database will not open (BUG-323).

FIXED-789 to FIXED-792 made, verified and restored backups from Settings →
Account. The case that most needs one — a database this key does not open
(``store_unreadable``) or one a newer Raiker has shaped (``store_schema_newer``)
— stops at the lock screen, which cannot sign anybody in and so cannot reach
Account. These two routes are that lock screen's way back.

They take no session, because there is no store to hold one. What stands in its
place, all of it checked on every call:

* **Only while the store will not open, for a reason a backup can fix.** The
  same probe ``/api/health`` answers is read first; a workspace that opens gets
  ``409 recovery_not_needed`` and nothing about its backups. A missing key is
  not one of those reasons: every backup needs that key.
* **Only from this machine.** The socket peer must be loopback and the host must
  be bound to loopback, as ``/api/instances`` already requires. Forwarding
  headers are not consulted.
* **Only from Raiker's own page.** A restore is a JSON body from a same-origin
  page: a cross-site form cannot send ``application/json`` without a preflight
  this server never answers, and an ``Origin`` that is not this host's is
  refused.
* **Reversible.** The database that would not open is moved into
  ``.raiker/quarantine/``, never deleted (``raiker.storage.backup``).

What the list says is a backup's manifest — when, why, how large, how many rows
of each kind, and whether this build can open it. No content is read.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.wire.control import RecoveryBackupsView, RecoveryRestored
from raiker.control.views.security import BackupView
from raiker.storage.store_errors import STORE_SCHEMA_NEWER, STORE_UNREADABLE

router = APIRouter()

#: Store conditions a backup can repair. A missing key is not one: every
#: backup opens with that key, so restoring one would open nothing either.
RECOVERABLE = (STORE_UNREADABLE, STORE_SCHEMA_NEWER)

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


class RecoveryRestoreRequest(StrictRequest):
    backup_id: str


def _workspace(request: Request) -> Path:
    return Path(request.app.state.workspace_root)  # type: ignore[attr-defined]


def _refuse(code: int, reason: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"reason_code": reason})


def _require_this_machine(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in _LOOPBACK or not bool(getattr(request.app.state, "loopback_only", True)):
        raise _refuse(status.HTTP_403_FORBIDDEN, "recovery_loopback_only")


def _require_same_origin(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        raise _refuse(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "recovery_json_required")
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host", ""):
        raise _refuse(status.HTTP_403_FORBIDDEN, "recovery_cross_origin")


def _store_condition(workspace: Path) -> str:
    """The reason the store will not open, or ``""`` when it opens."""
    from raiker.storage.sqlite import store_health

    health = store_health(workspace)
    return "" if health["store"] == "ok" else str(health.get("reason", ""))


def _require_recoverable(workspace: Path) -> str:
    reason = _store_condition(workspace)
    if reason not in RECOVERABLE:
        raise _refuse(status.HTTP_409_CONFLICT, "recovery_not_needed" if not reason else "recovery_not_possible")
    return reason


@router.get("/api/recovery/backups")
async def recovery_backups(request: Request) -> dict[str, Any]:
    """The backups a locked workspace could be restored from, read from their manifests."""
    _require_this_machine(request)
    workspace = _workspace(request)
    reason = await asyncio.to_thread(_require_recoverable, workspace)
    from raiker.storage.backup import key_fingerprint, list_backups
    from raiker.storage.migrations import SCHEMA_GENERATION

    answer = cast(
        RecoveryBackupsView,
        {
            "reason": reason,
            "key_fingerprint": key_fingerprint(workspace),
            "schema_generation": SCHEMA_GENERATION,
            "backups": [cast(BackupView, record.to_dict()) for record in list_backups(workspace)],
        },
    )
    return serialize_dto(answer)


@router.post("/api/recovery/restore")
async def recovery_restore(body: RecoveryRestoreRequest, request: Request) -> dict[str, Any]:
    """Verify one backup, quarantine the database that will not open, and switch the copy in."""
    _require_this_machine(request)
    _require_same_origin(request)
    workspace = _workspace(request)
    await asyncio.to_thread(_require_recoverable, workspace)
    from raiker.storage.backup import BackupError, restore_in_place

    try:
        restored = await asyncio.to_thread(restore_in_place, workspace, body.backup_id)
    except BackupError as exc:
        code = status.HTTP_404_NOT_FOUND if exc.reason == "unknown_backup" else status.HTTP_409_CONFLICT
        raise HTTPException(
            status_code=code, detail={"reason_code": exc.reason, "detail": str(exc)}
        ) from exc
    answer = cast(
        RecoveryRestored,
        {
            "ok": True,
            "backup_id": restored.backup_id,
            # The quarantine folder by name only: the page needs to say where
            # the old file went, not the workspace's absolute path.
            "quarantine": ".raiker/quarantine/" + Path(restored.quarantine).name,
            "counts": restored.counts,
            "deletions_applied": restored.deletions_applied,
        },
    )
    return serialize_dto(answer)
