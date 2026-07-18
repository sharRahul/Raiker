"""Same-server launcher for isolated local Raiker user instances."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.schemas import InstanceCreateRequest
from raiker.auth.accounts import AccountService, AuthError

router = APIRouter()

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def _require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in _LOOPBACK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason_code": "loopback_only"},
        )


@router.post("/api/instances")
def create_instance(body: InstanceCreateRequest, request: Request) -> dict[str, Any]:
    """Create an isolated workspace and, when supplied, its first account."""
    _require_loopback(request)
    name = body.name.strip().lower()
    if not _NAME.fullmatch(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason_code": "invalid_instance_name"},
        )
    if (body.username is None) != (body.password is None) or (
        body.username is not None and (not body.username.strip() or not body.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason_code": "username_and_password_required"},
        )
    from raiker.api.app import create_and_mount_instance

    root = Path(request.app.state.workspace_root).resolve()  # type: ignore[attr-defined]
    try:
        workspace = create_and_mount_instance(request.app, name, root)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason_code": "instance_already_exists"},
        ) from exc
    if body.username is not None:
        try:
            AccountService(workspace).register(body.username, body.password or "")
        except AuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"reason_code": "account_creation_failed"},
            ) from exc
    # The absolute workspace path is intentionally never exposed to the browser.
    return {"name": name, "url": f"/instances/{name}/"}
