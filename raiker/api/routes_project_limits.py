"""QUI-F21 — a project's own permission limits.

Owner-scoped and human-only: a limit is set on the project's page by the owner,
never by a model, a schedule or a connector. Limits only narrow what the
owner's permissions already allow for conversations filed in the project
(`raiker/policy/project_limits.py`).
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import ProjectLimitsRequest, serialize_dto
from raiker.api.wire.projects import ProjectLimitsView
from raiker.policy import project_limits
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _project(request: Request, project_id: str, *, human: bool = False) -> SQLiteStore:
    _session, principal = authenticate(request)
    if human:
        require_human(principal)
    store = SQLiteStore(_ws(request))
    if store.load_project(project_id, user_id=store.principal_user_id(principal.principal_id)) is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
    return store


@router.get("/api/projects/{project_id}/limits")
async def get_project_limits(project_id: str, request: Request) -> dict[str, Any]:
    """What work filed in this project may reach. Empty lists limit nothing."""
    store = _project(request, project_id)
    limits = project_limits.load(store, project_id)
    answer: ProjectLimitsView = {
        "project_id": project_id,
        "limits": cast(Any, limits),
        "summary": project_limits.describe(limits),
    }
    return serialize_dto(answer)


@router.put("/api/projects/{project_id}/limits")
async def set_project_limits(project_id: str, body: ProjectLimitsRequest, request: Request) -> dict[str, Any]:
    """Replace the project's limits. Applies from the next action its conversations propose."""
    store = _project(request, project_id, human=True)
    try:
        limits = project_limits.clean(cast(dict[str, Any], body.model_dump()))
    except project_limits.LimitError as exc:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    project_limits.save(store, project_id, limits)
    answer: ProjectLimitsView = {
        "project_id": project_id,
        "limits": cast(Any, limits),
        "summary": project_limits.describe(limits),
    }
    return serialize_dto(answer)
