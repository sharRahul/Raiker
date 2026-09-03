"""What Raiker says about its own build, and about updating it.

BUG-44. The distribution design's release bar is that an owner can *understand
whether it is running* and *safely control or remove it*. Half of understanding
is knowing what "it" is: a signed release from a known channel, an unsigned test
build, or a source checkout. That answer has to come from the build that produced
the installation rather than from anything typed afterwards, and it has to be
able to say "no evidence" — which is precisely what a source checkout gets.

Two routes, and a deliberate asymmetry between them. ``GET /api/host/update``
never touches the network: it reads the installation record, the pinned channel,
and the retained recovery points, so opening the panel cannot cause an outbound
request. ``POST /api/host/update/check`` is the one that asks, and only when the
owner has pinned a channel — Raiker contacts no update service by default.

Applying an update is deliberately **not** a route. Replacing the tree that the
process is executing from, from a request that process is serving, is the wrong
place for that decision; ``raiker-app update --apply`` does it from outside the
running host, and the panel says so.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.app.installation import (
    detect_installation,
    read_last_check,
    record_check,
    update_status,
)
from raiker.app.release import TARGETS
from raiker.app.update_handoff import start_update_handoff
from raiker.app.updater import check_for_update
from raiker.runtime.authority.models import Principal

router = APIRouter()


class ApplyUpdateRequest(BaseModel):
    confirm: bool = False


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _view(payload: dict[str, Any], workspace: str | Path) -> dict[str, Any]:
    payload["targets"] = [target.to_dict() for target in TARGETS]
    payload["last_check"] = read_last_check(workspace)
    return payload


@router.get("/api/host/update")
async def get_update_status(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Provenance, channel, and recovery points. Local reads only."""
    workspace = _ws(request)
    status = update_status(workspace, installation=detect_installation())
    return _view(status.to_dict(), workspace)


@router.post("/api/host/update/check")
async def check_update(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Ask the pinned channel once, and record what it said.

    A source checkout, an unsigned build, or an unpinned channel is answered
    without a request — the refusal is local and is the same one the status read
    already gives, so pressing the button on a development host is not a way to
    make Raiker talk to the internet.
    """
    workspace = _ws(request)
    status = check_for_update(workspace)
    if status.checked_at is not None:
        record_check(workspace, status)
    return _view({"ok": status.state != "unreachable", **status.to_dict()}, workspace)


@router.post("/api/host/update/apply")
async def apply_update(
    body: ApplyUpdateRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Hand a verified update to a detached helper, then stop this host.

    The helper waits for this process to exit before it re-checks the signed
    channel and changes the installation.  This response is deliberately sent
    before scheduling the stop so the browser can state why its connection is
    about to close.
    """
    from raiker.api.routes_host import _schedule_stop
    from raiker.app.host import HostControl

    workspace = _ws(request)
    running = HostControl(workspace).status(running=True).to_dict()
    if running["waiting"] and not body.confirm:
        return {
            "ok": False,
            "updating": False,
            "reason_code": "waiting_work",
            "message": "Update would interrupt work in progress. Confirm to continue.",
            **running,
        }
    checked = check_for_update(workspace)
    if checked.checked_at is not None:
        record_check(workspace, checked)
    if checked.state != "available" or checked.available is None:
        return _view(
            {
                "ok": False,
                "updating": False,
                "reason_code": f"update_{checked.state}",
                **checked.to_dict(),
            },
            workspace,
        )
    try:
        start_update_handoff(workspace, parent_pid=os.getpid())
    except OSError:
        return _view(
            {
                "ok": False,
                "updating": False,
                "reason_code": "update_handoff_unavailable",
                "message": "Raiker could not start the verified update helper.",
                **checked.to_dict(),
            },
            workspace,
        )
    _schedule_stop(request, 0)
    return _view(
        {
            "ok": True,
            "updating": True,
            "version": checked.available.version,
            **checked.to_dict(),
        },
        workspace,
    )
