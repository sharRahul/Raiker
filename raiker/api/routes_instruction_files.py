"""RAIKER.md — the owner's review of global and project-root instruction files.

Every change here is an authenticated, human-only owner action, never a model
tool: turning file instructions on for a project, approving one exact revision
(by the digest the owner saw), and disabling a file. Reading the state needs no
provider call. See ``raiker/context/raiker_md.py`` and
``docs/architecture/RAIKER_MD_INSTRUCTIONS.md``.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import (
    InstructionFileDisableRequest,
    InstructionFileReviewRequest,
    InstructionFilesEnabledRequest,
    serialize_dto,
)
from raiker.api.wire.projects import GlobalInstructionFileView, ProjectInstructionFilesView
from raiker.context import raiker_md
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _caller(request: Request, *, human: bool) -> tuple[SQLiteStore, str, str]:
    _session, principal = authenticate(request)
    if human:
        require_human(principal)
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(principal.principal_id)
    if not user_id:
        raise refusal(status.HTTP_403_FORBIDDEN, "instruction_file_user_unknown")
    return store, user_id, principal.principal_id


def _project(store: SQLiteStore, user_id: str, project_id: str) -> dict[str, Any]:
    project = store.load_project(project_id, user_id=user_id)
    if project is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
    return dict(project)


def _project_view(
    store: SQLiteStore, workspace: Any, user_id: str, owner: str, project: dict[str, Any]
) -> ProjectInstructionFilesView:
    state = raiker_md.status_for_project(store, workspace, user_id, owner, project)
    sources = []
    for source in state.sources:
        public = source.public(include_preview=True)
        # The global path is the owner's own; a project's view does not repeat it.
        public.pop("path", None)
        sources.append(cast(Any, public))
    return {
        "project_id": str(project["project_id"]),
        "enabled": state.enabled,
        "needs_review": bool(state.blocking),
        "sources": sources,
    }


def _global_view(store: SQLiteStore, workspace: Any, user_id: str) -> GlobalInstructionFileView:
    source = raiker_md.global_source(store, workspace, user_id)
    return {"source": cast(Any, source.public(include_preview=True))}


def _refuse(exc: raiker_md.InstructionFileError) -> Exception:
    code = str(exc)
    status_code = (
        status.HTTP_409_CONFLICT
        if code in {"instruction_file_changed_since_preview", "instruction_file_absent", "instruction_file_empty"}
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return refusal(status_code, code)


@router.get("/api/projects/{project_id}/instruction-files")
async def get_project_instruction_files(project_id: str, request: Request) -> dict[str, Any]:
    """Whether this project uses RAIKER.md, and the state of the global and project files."""
    store, user_id, owner = _caller(request, human=False)
    project = _project(store, user_id, project_id)
    answer: ProjectInstructionFilesView = _project_view(store, _ws(request), user_id, owner, project)
    return serialize_dto(answer)


@router.put("/api/projects/{project_id}/instruction-files")
async def set_project_instruction_files(
    project_id: str, body: InstructionFilesEnabledRequest, request: Request
) -> dict[str, Any]:
    """Turn file instructions on or off for this project. Turning on approves nothing."""
    store, user_id, owner = _caller(request, human=True)
    project = _project(store, user_id, project_id)
    raiker_md.set_project_enabled(store, user_id, project_id, body.enabled)
    answer: ProjectInstructionFilesView = _project_view(store, _ws(request), user_id, owner, project)
    return serialize_dto(answer)


@router.post("/api/projects/{project_id}/instruction-files/review")
async def review_project_instruction_file(
    project_id: str, body: InstructionFileReviewRequest, request: Request
) -> dict[str, Any]:
    """Approve the revision the owner saw; a file that changed since then conflicts."""
    store, user_id, owner = _caller(request, human=True)
    project = _project(store, user_id, project_id)
    try:
        raiker_md.review(
            store,
            _ws(request),
            user_id,
            owner,
            project=project if body.scope == "project" else None,
            digest=body.digest,
        )
    except raiker_md.InstructionFileError as exc:
        raise _refuse(exc) from None
    answer: ProjectInstructionFilesView = _project_view(store, _ws(request), user_id, owner, project)
    return serialize_dto(answer)


@router.post("/api/projects/{project_id}/instruction-files/disable")
async def disable_project_instruction_file(
    project_id: str, body: InstructionFileDisableRequest, request: Request
) -> dict[str, Any]:
    """Stop using one file. Its review is cleared, so new bytes or old ones need a review again."""
    store, user_id, owner = _caller(request, human=True)
    project = _project(store, user_id, project_id)
    raiker_md.disable(store, user_id, project_id=project_id if body.scope == "project" else None)
    answer: ProjectInstructionFilesView = _project_view(store, _ws(request), user_id, owner, project)
    return serialize_dto(answer)


@router.get("/api/instruction-files/global")
async def get_global_instruction_file(request: Request) -> dict[str, Any]:
    """The signed-in account's global RAIKER.md, with its path so the owner can edit it."""
    store, user_id, _owner = _caller(request, human=False)
    view: GlobalInstructionFileView = _global_view(store, _ws(request), user_id)
    return serialize_dto(view)


@router.post("/api/instruction-files/global/starter")
async def create_global_instruction_file(request: Request) -> dict[str, Any]:
    """Create a short starter file if none exists. It is not approved by being created."""
    store, user_id, _owner = _caller(request, human=True)
    try:
        raiker_md.create_global_starter(_ws(request), user_id)
    except (raiker_md.InstructionFileError, OSError):
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "instruction_file_not_created") from None
    view: GlobalInstructionFileView = _global_view(store, _ws(request), user_id)
    return serialize_dto(view)


@router.post("/api/instruction-files/global/review")
async def review_global_instruction_file(body: InstructionFileReviewRequest, request: Request) -> dict[str, Any]:
    """Approve the global file's revision the owner saw."""
    store, user_id, owner = _caller(request, human=True)
    try:
        raiker_md.review(store, _ws(request), user_id, owner, project=None, digest=body.digest)
    except raiker_md.InstructionFileError as exc:
        raise _refuse(exc) from None
    view: GlobalInstructionFileView = _global_view(store, _ws(request), user_id)
    return serialize_dto(view)


@router.post("/api/instruction-files/global/disable")
async def disable_global_instruction_file(request: Request) -> dict[str, Any]:
    """Stop using the global file in every project."""
    store, user_id, _owner = _caller(request, human=True)
    raiker_md.disable(store, user_id, project_id=None)
    view: GlobalInstructionFileView = _global_view(store, _ws(request), user_id)
    return serialize_dto(view)
