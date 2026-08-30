"""Browsing and reading the repository Build is pointed at (B13).

Build could run a coding turn against a connected repository and give the owner
no way to *look* at it. Reading the result of a change meant leaving the app, so
the one thing a coding session does constantly — open a file and read it — was
the one thing the workspace could not do.

These are the two reads that fix it, and they are deliberately only reads:

* ``GET /api/code/repos/{repo_id}/browse`` — one directory at a time, the same
  shape ``/api/projects/{id}/browse`` answers, so the explorer component does not
  care which kind of root it is over.
* ``GET /api/code/repos/{repo_id}/file`` — one bounded text file.

**Nothing here writes, and nothing here is a new boundary.** Every path is
resolved through the very :class:`~raiker.tools.path_authority.PathAuthority` a
turn writes through, and then re-checked against the repository's own root, so a
repository reference cannot become a workspace-wide file browser. Content comes
back through :func:`raiker.tools.filesystem.read_file`, the same bounded read the
agent's own ``read_file`` tool performs — a binary file, a missing file and an
oversize file each get the answer they already get there, rather than a second
opinion written for the browser.

A GitHub repository is a coordinate, not a checkout: there is nothing on this
machine to walk, and saying so is the honest answer rather than an empty tree.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.knowledge.extractors import resolve_extractable_media_type
from raiker.knowledge.reconcile import IGNORED_DIRECTORY_NAMES
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, read_file
from raiker.tools.path_authority import PathAuthority

router = APIRouter()

#: Largest number of children one browse answers with, matching the project
#: explorer's cap so the two roots behave identically at scale.
MAX_BROWSE_ENTRIES = 500

#: Largest file the viewer will render. Above this the answer states the size
#: rather than streaming a megabyte into a read-only pane nobody will scroll.
MAX_VIEW_BYTES = 400_000


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


def _names_its_own_root(supplied: str) -> bool:
    """True when a path sent to a *relative* parameter names a root of its own.

    Asked of what the caller sent, before separators are trimmed: stripping the
    leading slash off ``/etc/passwd`` leaves something that looks relative and
    would then resolve under the repository. ``PureWindowsPath`` carries the
    drive and UNC spellings on every platform, so the answer does not depend on
    where Raiker is running.
    """
    return supplied.startswith("/") or bool(PureWindowsPath(supplied).drive)


def _owned_repo(request: Request, repo_id: str, principal_id: str) -> dict[str, Any]:
    repo = SQLiteStore(_ws(request)).load_code_repo(principal_id, repo_id)
    if repo is None:
        raise _not_found("repo_not_found")
    return repo


def _repo_root(request: Request, repo: dict[str, Any]) -> Path | None:
    """Where this repository is on disk, or ``None`` when there is nothing to walk.

    A GitHub repository has no checkout, and a local folder the owner has since
    moved or deleted has no directory. Both answer ``None`` so the caller states
    it rather than rendering an empty tree as "no files".
    """
    subpath = repo.get("local_subpath")
    if not subpath:
        return None
    workspace = _ws(request).resolve()
    candidate = (workspace / str(subpath)).resolve()
    if candidate != workspace and workspace not in candidate.parents:
        return None
    return candidate if candidate.is_dir() else None


def _resolved_target(
    request: Request, root: Path, supplied: str
) -> Path:
    """*supplied*, resolved inside *root* — through the authority, then re-checked.

    Two independent checks on purpose. The authority is the boundary a turn
    writes through, so the browser cannot be looser than the agent; the second
    check is what keeps a *repository* reference from becoming a workspace-wide
    file browser, which the authority alone would happily allow.
    """
    relative = (supplied or "").strip().replace("\\", "/").strip("/")
    if _names_its_own_root(supplied or "") or ".." in PurePosixPath(relative).parts:
        raise _bad_request("outside_workspace")
    try:
        resolved = PathAuthority(_ws(request)).resolve_read(
            root / relative if relative else root
        )
    except FilesystemSafetyError as exc:
        raise _bad_request(str(exc)) from exc
    if resolved.path != root and root not in resolved.path.parents:
        raise _bad_request("outside_repository")
    return resolved.path


def _missing_view(repo: dict[str, Any]) -> dict[str, Any]:
    kind = str(repo.get("kind", "local"))
    return {
        "path": "",
        "parent": None,
        "entries": [],
        "truncated": False,
        "root_kind": kind,
        "root_label": str(repo.get("label", "")),
        "root_missing": True,
        # Two different absences, and the interface says which. A coordinate was
        # never on this machine; a folder that was is a problem to fix.
        "reason_code": "repo_not_checked_out" if kind == "github" else "repo_folder_missing",
    }


@router.get("/api/code/repos/{repo_id}/browse")
async def browse_code_repo(
    repo_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        return _missing_view(repo)
    target = _resolved_target(request, root, path)
    if not target.is_dir():
        raise _not_found("directory_not_found")
    children = [
        child
        for child in sorted(
            target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )
        if child.name not in IGNORED_DIRECTORY_NAMES
    ]
    relative = target.relative_to(root).as_posix() if target != root else ""
    return {
        "path": relative,
        "parent": (
            Path(relative).parent.as_posix().replace(".", "") if relative else None
        ),
        "entries": [_entry(child, root) for child in children[:MAX_BROWSE_ENTRIES]],
        "truncated": len(children) > MAX_BROWSE_ENTRIES,
        "root_kind": str(repo.get("kind", "local")),
        "root_label": str(repo.get("label", "")),
        "root_missing": False,
    }


def _entry(child: Path, root: Path) -> dict[str, Any]:
    is_directory = child.is_dir()
    return {
        "name": child.name,
        "relative_path": child.relative_to(root).as_posix(),
        "is_directory": is_directory,
        "size_bytes": 0 if is_directory else _size(child),
        "media_type": (
            ""
            if is_directory
            else (resolve_extractable_media_type(child.name, "") or "")
        ),
        # The repository explorer has no index behind it: these are files on
        # disk, not managed documents, and inventing an index state would
        # describe a projection that does not exist.
        "index_state": None,
    }


def _size(child: Path) -> int:
    try:
        return int(child.stat().st_size)
    except OSError:
        return 0


@router.get("/api/code/repos/{repo_id}/file")
async def read_code_repo_file(
    repo_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """One bounded text file, or a stated reason it cannot be shown."""
    if not (path or "").strip():
        raise _bad_request("path_required")
    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        raise _not_found(
            "repo_not_checked_out"
            if str(repo.get("kind")) == "github"
            else "repo_folder_missing"
        )
    target = _resolved_target(request, root, path)
    if not target.exists():
        raise _not_found("file_not_found")
    if not target.is_file():
        raise _bad_request("not_a_file")
    relative = target.relative_to(root).as_posix()
    size = _size(target)
    if size > MAX_VIEW_BYTES:
        # Refused with the number in it. "Too large" without the size is a dead
        # end; the size is what tells the owner whether to open it elsewhere.
        return {
            "path": relative,
            "text": "",
            "truncated": True,
            "size_bytes": size,
            "readable": False,
            "reason_code": "file_too_large",
        }
    result = read_file(_ws(request), target, max_bytes=MAX_VIEW_BYTES)
    if result.get("status") != "success":
        error = result.get("error") or {}
        return {
            "path": relative,
            "text": "",
            "truncated": False,
            "size_bytes": size,
            "readable": False,
            "reason_code": str(error.get("type") or "unreadable"),
        }
    return {
        "path": relative,
        "text": str(result.get("text", "")),
        "truncated": bool(result.get("truncated")),
        "size_bytes": size,
        "readable": True,
        "reason_code": "",
    }
