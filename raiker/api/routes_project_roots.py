"""Attaching, indexing and browsing a project's root.

One explorer serves both root kinds, so these routes answer the same shape for a
managed project and an attached one. What differs is only what the answer says:
where the root is, whether Raiker may write there, and whether the index behind
it is current.

Browse resolves through the very `PathAuthority` a turn writes through, not a
second containment check written for the API. A boundary implemented twice is a
boundary that eventually disagrees with itself, and the half a browser can reach
is the wrong half to get wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.control.dashboard import DashboardService
from raiker.control.project_roots import authority_for_project, resolve_project_root
from raiker.knowledge.extractors import resolve_extractable_media_type
from raiker.knowledge.reconcile import IGNORED_DIRECTORY_NAMES, reconcile_attached_root
from raiker.knowledge.watcher import WatchState
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError

router = APIRouter()

#: Largest number of children one browse answers with. A directory of a hundred
#: thousand files is listed as its first page plus `truncated`, rather than as a
#: response that neither end can hold.
MAX_BROWSE_ENTRIES = 500


def _ws(request: Request) -> Path:
    return Path(str(request.app.state.workspace_root))


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _not_found(reason_code: str) -> HTTPException:
    """404 for everything the caller may not see, so an id cannot be probed."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "reason_code": reason_code},
    )


def _bad_request(reason_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"ok": False, "reason_code": reason_code},
    )


def _owned_project(
    request: Request, project_id: str, auth_data: tuple[ApiSession, Principal]
) -> dict[str, Any]:
    """The project, or a 404 — authenticated first, resolved second."""
    store = SQLiteStore(_ws(request))
    project = store.load_project(
        project_id, user_id=auth_data[1].delegated_by_user_id
    )
    if project is None:
        raise _not_found("project_not_found")
    return project


def _watch_state(request: Request, project_id: str) -> WatchState:
    """What the host's watcher knows, or the honest default when there is none.

    An embedded host with no lifespan worker is not watching, and saying so is
    the point: the interface must never imply freshness it cannot deliver.
    """
    watcher = getattr(request.app.state, "attached_root_watcher", None)
    if watcher is None:
        return WatchState(False, "not_started", "")
    return watcher.state(project_id)  # type: ignore[no-any-return]


@router.get("/api/projects/{project_id}/browse")
async def browse_project(
    project_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    workspace = _ws(request)
    store = SQLiteStore(workspace)
    project = _owned_project(request, project_id, auth_data)
    owner = auth_data[0].principal_id
    grants = store.list_brain_source_grants(owner)
    root = resolve_project_root(project, grants, workspace)
    if root.path is None or root.missing:
        # A revoked grant, a detached project, or a folder the owner moved. The
        # explorer has to say so; an empty tree would read as "no files".
        return {
            "path": "",
            "parent": None,
            "entries": [],
            "truncated": False,
            "root_kind": root.kind,
            "root_label": _label(root),
            "root_missing": True,
        }
    relative = (path or "").strip().replace("\\", "/").strip("/")
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        # Refused before it reaches the authority, because an absolute path in a
        # *relative* parameter is a caller naming a root this project was never
        # given, not a traversal the authority should be asked to adjudicate.
        raise _bad_request("outside_workspace")
    authority = authority_for_project(project, grants, workspace)
    try:
        target = authority.resolve_read(root.path / relative if relative else root.path)
    except FilesystemSafetyError as exc:
        raise _bad_request(str(exc)) from exc
    if not target.path.is_dir():
        raise _not_found("directory_not_found")
    indexed = {
        str(row["relative_path"]): str(row["index_state"])
        for row in store.list_managed_files(
            owner, scope_kind="project", project_id=project_id
        )
    }
    children = [
        child
        for child in sorted(
            target.path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )
        if child.name not in IGNORED_DIRECTORY_NAMES
    ]
    entries = [_entry(child, root.path, indexed) for child in children[:MAX_BROWSE_ENTRIES]]
    return {
        "path": relative,
        "parent": Path(relative).parent.as_posix().replace(".", "") if relative else None,
        "entries": entries,
        "truncated": len(children) > MAX_BROWSE_ENTRIES,
        "root_kind": root.kind,
        "root_label": _label(root),
        "root_missing": False,
    }


def _entry(child: Path, root: Path, indexed: dict[str, str]) -> dict[str, Any]:
    relative = child.relative_to(root).as_posix()
    is_directory = child.is_dir()
    return {
        "name": child.name,
        "relative_path": relative,
        "is_directory": is_directory,
        "size_bytes": 0 if is_directory else _size(child),
        "media_type": "" if is_directory else (resolve_extractable_media_type(relative, "") or ""),
        # Absent rather than "not indexed": a file Raiker cannot read has no
        # index state to report, and inventing one would suggest a failure.
        "index_state": indexed.get(relative),
    }


def _size(child: Path) -> int:
    try:
        return int(child.stat().st_size)
    except OSError:
        return 0


def _label(root: Any) -> str:
    if root.path is not None:
        return str(root.path.name or root.path)
    return str(root.root_id)


@router.get("/api/projects/{project_id}/root/status")
async def project_root_status(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    workspace = _ws(request)
    store = SQLiteStore(workspace)
    project = _owned_project(request, project_id, auth_data)
    owner = auth_data[0].principal_id
    root = resolve_project_root(project, store.list_brain_source_grants(owner), workspace)
    state = _watch_state(request, project_id)
    return {
        "ok": True,
        "project_id": project_id,
        "root_kind": root.kind,
        "root_label": _label(root),
        "root_path": str(root.path) if root.kind == "attached" and root.path else None,
        "root_missing": root.missing,
        "writable": root.writable,
        "watching": state.watching,
        "watch_reason": state.reason,
        "last_scanned_at": state.last_scanned_at,
        "indexed_files": len(
            store.list_managed_files(owner, scope_kind="project", project_id=project_id)
        ),
    }


@router.post("/api/projects/{project_id}/root/index")
async def index_project_root(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    workspace = _ws(request)
    store = SQLiteStore(workspace)
    project = _owned_project(request, project_id, auth_data)
    owner = auth_data[0].principal_id
    root = resolve_project_root(project, store.list_brain_source_grants(owner), workspace)
    if root.kind != "attached":
        # A managed project's files arrive by import, which indexes them on the
        # way in. A scan would find only what Raiker itself wrote.
        raise _bad_request("project_root_not_attached")
    if root.path is None or root.missing:
        raise _bad_request("project_root_missing")
    report = reconcile_attached_root(workspace, store, project, owner)
    return {
        "ok": True,
        "project_id": project_id,
        "indexed": report.indexed,
        "updated": report.updated,
        "retired": report.retired,
        "skipped": report.skipped,
        "truncated": report.truncated,
        "scanned_at": report.scanned_at,
    }


@router.post("/api/projects/{project_id}/root/attach")
async def attach_project_root(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    body = await _body(request)
    _owned_project(request, project_id, auth_data)
    result = DashboardService(_ws(request)).attach_project_folder(
        project_id,
        str(body.get("path", "")),
        auth_data[0].principal_id,
        writable=bool(body.get("writable", True)),
    )
    if not result.ok:
        raise _bad_request(str(result.reason_code))
    return {"ok": True, **result.data}


@router.delete("/api/projects/{project_id}/root")
async def detach_project_root(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _owned_project(request, project_id, auth_data)
    result = DashboardService(_ws(request)).detach_project_folder(
        project_id, auth_data[0].principal_id
    )
    if not result.ok:
        raise _bad_request(str(result.reason_code))
    return {"ok": True, **result.data}


async def _body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001 - any malformed body is one refusal
        raise _bad_request("invalid_body") from exc
    if not isinstance(payload, dict):
        raise _bad_request("invalid_body")
    return payload
