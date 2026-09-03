"""The menu-bar control, as an API the web app and the CLI both use.

BUG-40. The distribution design requires a tray/menu-bar control that reports
``running`` / ``paused`` / ``needs attention`` / ``stopped`` and offers Open,
Pause, Restart and Quit — with quitting *reporting any waiting work before it
stops*. These routes are that control's contract. The same answers back
``raiker-app status`` in a terminal, so there is one source of truth about the
host rather than one per surface.

Two of these routes stop or restart the process serving them, which deserves its
justification. They are owner-authenticated exactly like every other route, the
host binds loopback by default, and the alternative — telling an owner to find
and kill a process id — is precisely the "asking a person to operate a service"
problem ``raiker-app`` exists to end. The stop itself is a ``SIGTERM`` to this
process, so uvicorn's own graceful shutdown runs the lifespan teardown and
in-flight governed work reaches a safe boundary. Nothing here force-kills.

**Restart is refused when it would be a lie.** A host started from a terminal has
nothing that would start it again, so ``/api/host/restart`` returns
``not_registered`` and says so, rather than exiting and leaving the owner with a
dead URL. When Raiker *is* registered with ``launchd`` or ``systemd --user``, the
process exits with :data:`RESTART_EXIT_CODE` — a status both managers are
configured to treat as "start it again" — and the platform does the restart.
"""

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from raiker.api.auth import AuthMiddleware
from raiker.api.routes_instances import _require_loopback
from raiker.api.sessions import ApiSession
from raiker.app.host import HostControl
from raiker.app.service import registration
from raiker.runtime.authority.models import Principal

router = APIRouter()

# Exit status meaning "the owner asked for a restart". Chosen to be non-zero so
# launchd's `KeepAlive → SuccessfulExit: false` restarts, and pinned in the
# systemd unit's `RestartForceExitStatus` so it restarts there too.
RESTART_EXIT_CODE = 75
# How long to let the HTTP response finish before signalling the process. Long
# enough for the client to have the answer in hand, short enough that Quit feels
# like Quit.
_STOP_DELAY_SECONDS = 0.35


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request, required_scope="host_control")


def _control(request: Request) -> HostControl:
    return HostControl(_ws(request))


def _port(request: Request) -> int:
    saved = _control(request).record().get("port")
    return saved if isinstance(saved, int) else 8765


class PauseHostRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class StopHostRequest(BaseModel):
    # False is the safe default: the first press reports what is in flight, and
    # the owner decides again knowing it.
    confirm: bool = False


def _payload(request: Request) -> dict[str, Any]:
    control = _control(request)
    # The host answering this request *is* running, whatever the record says: a
    # workspace opened before background registration existed has no record file,
    # and reporting "stopped" to a browser loaded from this very process would be
    # the one state that is provably wrong. Pause and needs-attention are still
    # decided from the workspace, so the override cannot mask either.
    view = control.status(running=True).to_dict()
    if view["pid"] is None:
        view["pid"] = os.getpid()
    service = registration(control.workspace_root, port=_port(request))
    view["service"] = service.to_dict()
    view["restartable"] = service.registered
    return view


@router.get("/api/host")
async def get_host(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """State, in-flight work, and whether the host starts on its own."""
    return _payload(request)


@router.post("/api/host/pause")
async def pause_host(
    body: PauseHostRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Stop starting new background work. Approved continuations still finish."""
    _control(request).pause(body.reason)
    return {"ok": True, **_payload(request)}


@router.post("/api/host/resume")
async def resume_host(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Start scheduled work again from the next tick."""
    _control(request).resume()
    return {"ok": True, **_payload(request)}


@router.post("/api/host/quit")
async def quit_host(
    body: StopHostRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Stop the host, reporting what that interrupts unless already confirmed."""
    view = _payload(request)
    if view["waiting"] and not body.confirm:
        return {"ok": False, "reason_code": "waiting_work", "stopping": False, **view}
    _schedule_stop(request, 0)
    return {"ok": True, "stopping": True, **view}


@router.post("/api/host/restart")
async def restart_host(
    body: StopHostRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Stop with the status the platform's service manager restarts on."""
    view = _payload(request)
    if not view["restartable"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "ok": False,
                "reason_code": "not_registered",
                "message": (
                    "Raiker is not registered to start in the background, so "
                    "nothing would start it again. Run `raiker-app service "
                    "install` first, or quit and start it yourself."
                ),
            },
        )
    if view["waiting"] and not body.confirm:
        return {"ok": False, "reason_code": "waiting_work", "restarting": False, **view}
    _schedule_stop(request, RESTART_EXIT_CODE)
    return {"ok": True, "restarting": True, **view}


def _schedule_stop(request: Request, exit_code: int) -> None:
    """Signal this process to shut down gracefully, just after the response.

    The exit status is left on ``app.state`` for the launcher to return, which is
    what turns "the owner pressed Restart" into an exit code the service manager
    understands. Signalling is best-effort: a host running under a test client or
    an embedded server has no signal handler to receive it, and must not have its
    request fail because of that.
    """
    request.app.state.exit_code = exit_code
    loop = asyncio.get_running_loop()

    def stop() -> None:
        with suppress(OSError, ValueError, AttributeError):
            os.kill(os.getpid(), getattr(signal, "SIGTERM", signal.SIGINT))

    loop.call_later(_STOP_DELAY_SECONDS, stop)


# --- Browsing for a folder (BUG-251) ------------------------------------------
#
# Four fields asked the owner to *type* a filesystem location: attaching an
# existing project folder, approving a models folder, naming a workspace file in
# the task composer, and picking a Build repository. There was no way to browse
# to one, so every one of them required knowing how to spell a directory.
#
# A browser cannot solve this. `<input type="file">` yields file *contents*,
# `webkitdirectory` yields relative names, and the File System Access API yields
# an opaque handle and only in Chromium. None of them can produce ``D:\Models``,
# because the path is resolved by this host and not by the browser. So the host
# answers it, which is what a local application in this position needs anyway.
#
# The narrowness is the point:
#
# * It lists **names**, never contents. Nothing here reads a byte of a file.
# * It **changes nothing**. Every existing approval path still governs what may
#   actually be read or written once a path has been chosen.
# * It is **loopback-only and owner-authenticated**, like every other route, so
#   it is reachable by exactly the person who can already open a file manager on
#   this machine.
#
# It is deliberately not restricted to the workspace. The fields it serves exist
# precisely to name a location *outside* it — that is what "approve this folder"
# means — and a picker that cannot reach the folder being approved would send
# the owner back to typing.

# One page of a directory. Large enough for a real source tree, small enough
# that a folder with a hundred thousand entries cannot stall the dialog.
MAX_PATH_ENTRIES = 500

# Never offered. These are noise in a folder picker on every platform, and the
# owner who genuinely wants one can still type it.
_HIDDEN_BY_CONVENTION = {"$RECYCLE.BIN", "System Volume Information", "__pycache__"}


def _drive_roots() -> list[dict[str, Any]]:
    """The top level of this machine: drive letters on Windows, ``/`` elsewhere."""
    if os.name == "nt":
        roots: list[dict[str, Any]] = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            # `exists()` on an empty optical drive can block; `is_dir()` on the
            # root is the cheap question and answers the same thing here.
            with suppress(OSError):
                if drive.is_dir():
                    roots.append({"name": f"{letter}:", "path": str(drive), "is_directory": True})
        return roots
    return [{"name": "/", "path": "/", "is_directory": True}]


def _home_shortcuts() -> list[dict[str, Any]]:
    """Where an owner actually keeps things, so the picker does not open at a drive root."""
    shortcuts: list[dict[str, Any]] = []
    with suppress(OSError, RuntimeError):
        home = Path.home()
        if home.is_dir():
            shortcuts.append({"name": "Home", "path": str(home), "is_directory": True})
            for child in ("Documents", "Desktop", "Downloads"):
                candidate = home / child
                with suppress(OSError):
                    if candidate.is_dir():
                        shortcuts.append(
                            {"name": child, "path": str(candidate), "is_directory": True}
                        )
    return shortcuts


def _listable(child: Path) -> bool:
    if child.name in _HIDDEN_BY_CONVENTION:
        return False
    # A dotfile is hidden on POSIX and a nuisance in a picker; `.github` and
    # friends are still reachable by typing. Windows hidden files are left to
    # the same rule rather than a second one, so both platforms behave alike.
    return not child.name.startswith(".")


@router.get("/api/host/paths")
async def browse_host_paths(
    request: Request,
    path: str = "",
    files: bool = False,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """List the directories (and optionally files) under one host location.

    ``path`` empty means "the top": drives or ``/``, plus the owner's home and
    the folders they keep things in. Anything else is listed as given, and a
    location that has gone away is reported as such rather than as an empty
    folder — the two mean very different things to the person looking at it.
    """
    _require_loopback(request)
    workspace = Path(_ws(request)).resolve()
    if not path.strip():
        # The workspace comes first because it is the answer to more of these
        # fields than anything else on the machine, and it is the one place the
        # owner should not have to go looking for.
        top = [{"name": "Raiker workspace", "path": str(workspace), "is_directory": True}]
        return {
            "path": "",
            "parent": None,
            "separator": os.sep,
            "workspace_root": str(workspace),
            "entries": top + _home_shortcuts() + _drive_roots(),
            "truncated": False,
            "missing": False,
        }
    target = Path(path.strip()).expanduser()
    try:
        target = target.resolve()
    except OSError:
        return _missing_path(path, workspace)
    try:
        if not target.is_dir():
            return _missing_path(str(target), workspace)
        children = sorted(
            (child for child in target.iterdir() if _listable(child)),
            key=lambda item: (not _is_dir(item), item.name.lower()),
        )
    except OSError:
        # Permission denied, a disconnected network share, a device that is not
        # ready. All of them mean "this cannot be listed", and saying which is
        # more use than a 500.
        return _missing_path(str(target), workspace)
    kept = [child for child in children if files or _is_dir(child)]
    parent = str(target.parent) if target.parent != target else ""
    return {
        "path": str(target),
        "parent": parent,
        "separator": os.sep,
        "workspace_root": str(workspace),
        "entries": [
            {"name": child.name, "path": str(child), "is_directory": _is_dir(child)}
            for child in kept[:MAX_PATH_ENTRIES]
        ],
        "truncated": len(kept) > MAX_PATH_ENTRIES,
        "missing": False,
    }


def _is_dir(child: Path) -> bool:
    # A broken symlink or a path that vanished mid-listing is not a directory,
    # and must not raise in the middle of building the answer.
    try:
        return child.is_dir()
    except OSError:
        return False


def _missing_path(path: str, workspace: Path) -> dict[str, Any]:
    return {
        "path": path,
        "parent": str(Path(path).parent) if path else "",
        "separator": os.sep,
        "workspace_root": str(workspace),
        "entries": [],
        "truncated": False,
        "missing": True,
    }
