"""Durable goals and Settings-owned execution profiles (PA-D01, PA-D02).

Three rules hold for every route here:

* **Owner-scoped, always.** A goal or profile id is resolved against the
  signed-in owner; another owner's id answers as one never issued.
* **Owner actions only.** Creating, accepting, starting, pausing, resuming,
  stopping and confirming a goal, and every profile change, is human-only.
  There is no model tool for any of them, so a prompt, memory, schedule or
  connector cannot set a goal running or change the boundary it runs under.
* **Each change names the revision it was made against**, and one made against
  an older copy is refused (409 ``goal_revision_stale``) rather than applied.

Nothing here grants a capability. A goal's steps run as ordinary tasks under
the policy engine, broker and approvals every task has.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import (
    CreateExecutionProfileRequest,
    CreateGoalRequest,
    ExecutionProfileBindingRequest,
    GoalActionRequest,
    GoalConfirmRequest,
    GoalSuggestionDismissRequest,
    UpdateExecutionProfileRequest,
    UpdateGoalPlanRequest,
    serialize_dto,
)
from raiker.api.wire.goals import (
    ExecutionProfileChanged,
    ExecutionProfileList,
    ExecutionProfileView,
    GoalList,
    GoalStopped,
    GoalSuggestionAnswer,
    GoalSuggestionDismissed,
    GoalSuggestionView,
    GoalView,
)
from raiker.goals import noticing
from raiker.goals import profiles as profile_store
from raiker.goals import store as goal_store
from raiker.goals.coordinator import GoalCoordinator
from raiker.goals.profiles import ProfileError
from raiker.goals.store import GoalError
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

#: Refusals that are a conflict with the goal's current state, not a bad request.
_CONFLICTS = frozenset(
    {
        "goal_revision_stale", "goal_action_not_allowed", "no_execution_profile", "profile_changed",
        "profile_blocks_model", "budget_exhausted", "execution_profile_version_stale",
    }
)


def _owner(request: Request, *, human: bool = False) -> tuple[str, Any]:
    session, principal = authenticate(request)
    if human:
        require_human(principal)
    return str(session.principal_id), principal


def _coordinator(request: Request) -> GoalCoordinator:
    return GoalCoordinator(_ws(request))


def _goal_refusal(exc: GoalError) -> Exception:
    if exc.reason == "goal_not_found":
        return refusal(status.HTTP_404_NOT_FOUND, "goal_not_found")
    code = status.HTTP_409_CONFLICT if exc.reason in _CONFLICTS else status.HTTP_422_UNPROCESSABLE_CONTENT
    return refusal(code, f"{exc.reason}:{exc.detail}" if exc.detail else exc.reason)


def _profile_refusal(exc: ProfileError) -> Exception:
    if exc.reason == "execution_profile_unknown":
        return refusal(status.HTTP_404_NOT_FOUND, exc.reason)
    code = status.HTTP_409_CONFLICT if exc.reason in _CONFLICTS else status.HTTP_422_UNPROCESSABLE_CONTENT
    return refusal(code, exc.reason)


def _view(coordinator: GoalCoordinator, owner: str, goal_id: str) -> GoalView:
    try:
        return cast(GoalView, coordinator.view(owner, goal_id))
    except GoalError as exc:
        raise _goal_refusal(exc) from None


def _check_project(store: SQLiteStore, principal: Any, project_id: str | None) -> str | None:
    if not project_id:
        return None
    if store.load_project(project_id, user_id=principal.delegated_by_user_id) is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
    return project_id


def _plan(body: CreateGoalRequest | UpdateGoalPlanRequest, has_project: bool) -> dict[str, Any]:
    try:
        return goal_store.clean_plan(
            title=body.title,
            objective=body.objective,
            criteria=[c.model_dump() for c in body.criteria],
            steps=[s.model_dump() for s in body.steps],
            has_project=has_project,
            model_profile=body.model_profile,
            model=body.model,
        )
    except GoalError as exc:
        raise _goal_refusal(exc) from None


# ── Goals ────────────────────────────────────────────────────────────────


@router.get("/api/goals/suggestion")
async def goal_suggestion(request: Request, session_id: str) -> dict[str, Any]:
    """QUI-F03 — whether this conversation's latest request is an aim worth tracking.

    Read-only and local: the answer fills nothing and creates nothing. Chat
    offers it under the latest answer; *Track it* opens the Goals form filled
    in, and *Not now* is the dismissal route below.
    """
    owner, _principal = _owner(request)
    store = SQLiteStore(_ws(request))
    found = noticing.suggestion_for(
        store, owner_principal_id=owner, user_id=store.principal_user_id(owner), session_id=session_id
    )
    answer: GoalSuggestionAnswer = {
        "session_id": session_id,
        "suggestion": cast(GoalSuggestionView, noticing.view(found)) if found is not None else None,
    }
    return serialize_dto(answer)


@router.post("/api/goals/suggestion/dismiss")
async def dismiss_goal_suggestion(body: GoalSuggestionDismissRequest, request: Request) -> dict[str, Any]:
    """QUI-F03 — *Not now*. The same aim is never offered again."""
    owner, _principal = _owner(request, human=True)
    key = noticing.dismiss(SQLiteStore(_ws(request)), owner_principal_id=owner, words=body.keywords)
    answer: GoalSuggestionDismissed = {"ok": True, "aim_key": key}
    return serialize_dto(answer)


@router.get("/api/goals")
async def list_goals(request: Request) -> dict[str, Any]:
    """Every goal with its state read back from its steps' tasks."""
    owner, _ = _owner(request)
    coordinator = _coordinator(request)
    active, _source = profile_store.resolve_for(coordinator.store, owner=owner, project_id=None)
    answer: GoalList = {
        "goals": cast(list[GoalView], coordinator.list_views(owner)),
        "archived": cast(list[GoalView], coordinator.list_views(owner, archived=True)[:40]),
        "active_profile": cast(ExecutionProfileView, active.view()) if active is not None else None,
    }
    return serialize_dto(answer)


@router.post("/api/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(body: CreateGoalRequest, request: Request) -> dict[str, Any]:
    """Intake: a draft goal. A draft has no permission to run (PA-D01)."""
    owner, principal = _owner(request, human=True)
    coordinator = _coordinator(request)
    project_id = _check_project(coordinator.store, principal, (body.project_id or "").strip())
    plan = _plan(body, bool(project_id))
    goal_id = goal_store.create_goal(coordinator.store, owner=owner, project_id=project_id, plan=plan)
    answer = _view(coordinator, owner, goal_id)
    return serialize_dto(answer)


@router.get("/api/goals/{goal_id}")
async def read_goal(goal_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _owner(request)
    coordinator = _coordinator(request)
    try:
        coordinator.advance(owner, goal_id)
    except GoalError as exc:
        raise _goal_refusal(exc) from None
    answer = _view(coordinator, owner, goal_id)
    return serialize_dto(answer)


@router.put("/api/goals/{goal_id}/plan")
async def update_goal_plan(goal_id: str, body: UpdateGoalPlanRequest, request: Request) -> dict[str, Any]:
    """Edit a draft's plan. Only a draft, only over the revision the owner saw."""
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    current = goal_store.get_goal(coordinator.store, owner=owner, goal_id=goal_id)
    if current is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "goal_not_found")
    if current["status"] != "draft":
        raise refusal(status.HTTP_409_CONFLICT, f"goal_action_not_allowed:edit:{current['status']}")
    plan = _plan(body, bool(current.get("project_id")))
    try:
        goal_store.replace_plan(
            coordinator.store, owner=owner, goal_id=goal_id, base_revision=body.base_revision, plan=plan
        )
    except GoalError as exc:
        raise _goal_refusal(exc) from None
    answer = _view(coordinator, owner, goal_id)
    return serialize_dto(answer)


async def _act(request: Request, goal_id: str, action: str, base_revision: int) -> GoalView:
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    try:
        getattr(coordinator, action)(owner, goal_id, base_revision)
    except GoalError as exc:
        raise _goal_refusal(exc) from None
    if action in {"start", "resume"}:
        wakeup = getattr(request.app.state, "scheduler_wakeup", None)
        if wakeup is not None:
            wakeup.request()
    return _view(coordinator, owner, goal_id)


@router.post("/api/goals/{goal_id}/accept")
async def accept_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    """Draft → ready under the execution profile Settings binds (PA-D02)."""
    answer = await _act(request, goal_id, "accept", body.base_revision)
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/start")
async def start_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    """The owner's intent to run: the first due steps are filed as ordinary tasks."""
    answer = await _act(request, goal_id, "start", body.base_revision)
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/pause")
async def pause_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    """Nothing new is filed; steps not yet claimed are parked; runs in flight finish."""
    answer = await _act(request, goal_id, "pause", body.base_revision)
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/resume")
async def resume_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    """Continue only after owner, profile, model chain and budget are rechecked."""
    answer = await _act(request, goal_id, "resume", body.base_revision)
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/archive")
async def archive_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    answer = await _act(request, goal_id, "archive", body.base_revision)
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/stop")
async def stop_goal(goal_id: str, body: GoalActionRequest, request: Request) -> dict[str, Any]:
    """Stop every linked task and what it delegated; report what finished and what did not."""
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    try:
        report = coordinator.stop(owner, goal_id, body.base_revision)
    except GoalError as exc:
        raise _goal_refusal(exc) from None
    answer: GoalStopped = {"ok": True, **report, "goal": _view(coordinator, owner, goal_id)}  # type: ignore[typeddict-item]
    return serialize_dto(answer)


@router.post("/api/goals/{goal_id}/criteria/{criterion_id}/confirm")
async def confirm_goal_criterion(
    goal_id: str, criterion_id: str, body: GoalConfirmRequest, request: Request
) -> dict[str, Any]:
    """The owner records that one criterion is met — evidence that is theirs, never a model's."""
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    try:
        coordinator.confirm(owner, goal_id, criterion_id, body.base_revision, body.note)
    except GoalError as exc:
        raise _goal_refusal(exc) from None
    answer = _view(coordinator, owner, goal_id)
    return serialize_dto(answer)


# ── Execution profiles (Settings) ────────────────────────────────────────


def _profiles_answer(store: SQLiteStore, owner: str) -> ExecutionProfileList:
    bound = profile_store.bindings(store, owner=owner)
    return {
        "profiles": [cast(ExecutionProfileView, p.view()) for p in profile_store.list_profiles(store, owner=owner)],
        "templates": [
            {
                "template": key, "name": str(spec["name"]), "summary": str(spec["summary"]),
                "allow_local": bool(spec["allow_local"]), "allow_hosted": bool(spec["allow_hosted"]),
                "memory_to_hosted": bool(spec["memory_to_hosted"]),
            }
            for key, spec in profile_store.TEMPLATES.items()
        ],
        "active_profile_id": bound.get(""),
        "project_bindings": [
            {"project_id": project_id, "profile_id": profile_id}
            for project_id, profile_id in sorted(bound.items()) if project_id
        ],
    }


@router.get("/api/execution-profiles")
async def list_execution_profiles(request: Request) -> dict[str, Any]:
    owner, _ = _owner(request)
    coordinator = _coordinator(request)
    answer = _profiles_answer(coordinator.store, owner)
    return serialize_dto(answer)


def _changed(coordinator: GoalCoordinator, owner: str, profile: profile_store.ExecutionProfile | None) -> ExecutionProfileChanged:
    paused = coordinator.profile_changed(owner)
    return {
        "ok": True,
        "profile": cast(ExecutionProfileView, profile.view()) if profile is not None else None,
        "goals_paused": paused,
    }


@router.post("/api/execution-profiles", status_code=status.HTTP_201_CREATED)
async def create_execution_profile(body: CreateExecutionProfileRequest, request: Request) -> dict[str, Any]:
    """A profile from a template. The owner's first one becomes active, said in the answer."""
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    fields = body.model_dump(include=body.model_fields_set - {"template"})
    try:
        profile = profile_store.create_profile(coordinator.store, owner=owner, template=body.template, fields=fields)
        if "" not in profile_store.bindings(coordinator.store, owner=owner):
            profile_store.bind(coordinator.store, owner=owner, project_id="", profile_id=profile.profile_id)
    except ProfileError as exc:
        raise _profile_refusal(exc) from None
    coordinator._audit(owner, "execution_profile_created",  # noqa: SLF001
                       {"profile_id": profile.profile_id, "template": body.template})
    answer = _changed(coordinator, owner, profile)
    return serialize_dto(answer)


@router.put("/api/execution-profiles/active")
async def set_active_execution_profile(body: ExecutionProfileBindingRequest, request: Request) -> dict[str, Any]:
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    try:
        profile_store.bind(coordinator.store, owner=owner, project_id="", profile_id=body.profile_id)
    except ProfileError as exc:
        raise _profile_refusal(exc) from None
    coordinator._audit(owner, "execution_profile_bound", {"project_id": "", "profile_id": body.profile_id})  # noqa: SLF001
    profile = (
        profile_store.get_profile(coordinator.store, owner=owner, profile_id=body.profile_id)
        if body.profile_id else None
    )
    answer = _changed(coordinator, owner, profile)
    return serialize_dto(answer)


@router.put("/api/execution-profiles/{profile_id}")
async def update_execution_profile(
    profile_id: str, body: UpdateExecutionProfileRequest, request: Request
) -> dict[str, Any]:
    """Write the next version. Goals running under the old one pause at a safe boundary (PROF-03)."""
    owner, _ = _owner(request, human=True)
    coordinator = _coordinator(request)
    fields = body.model_dump(include=body.model_fields_set - {"base_version"})
    try:
        profile = profile_store.update_profile(
            coordinator.store, owner=owner, profile_id=profile_id, base_version=body.base_version, fields=fields
        )
    except ProfileError as exc:
        raise _profile_refusal(exc) from None
    coordinator._audit(owner, "execution_profile_changed",  # noqa: SLF001
                       {"profile_id": profile_id, "version": profile.version})
    answer = _changed(coordinator, owner, profile)
    return serialize_dto(answer)


@router.put("/api/execution-profiles/projects/{project_id}")
async def bind_project_execution_profile(
    project_id: str, body: ExecutionProfileBindingRequest, request: Request
) -> dict[str, Any]:
    """Bind a profile to one project; goals filed there inherit it instead of the active one."""
    owner, principal = _owner(request, human=True)
    coordinator = _coordinator(request)
    _check_project(coordinator.store, principal, project_id)
    try:
        profile_store.bind(coordinator.store, owner=owner, project_id=project_id, profile_id=body.profile_id)
    except ProfileError as exc:
        raise _profile_refusal(exc) from None
    coordinator._audit(owner, "execution_profile_bound",  # noqa: SLF001
                       {"project_id": project_id, "profile_id": body.profile_id})
    profile = (
        profile_store.get_profile(coordinator.store, owner=owner, profile_id=body.profile_id)
        if body.profile_id else None
    )
    answer = _changed(coordinator, owner, profile)
    return serialize_dto(answer)
