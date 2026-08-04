"""Executors for the two local planning mutations an approval can carry out.

BUG-62: ``create_task`` and ``assign_session_project`` reached the approval path
correctly — the owner was shown a real high-risk decision naming the task — and
then nothing happened, because neither capability was in
``EXECUTABLE_ON_APPROVAL``. The owner approved and got a record. These two
executors are what makes that approval mean what it says.

Both mutations are exactly the shape the relay exists for: **local, reversible,
owner-scoped rows**. A task can be stopped and deleted in Tasks; a project
assignment is a label on a conversation that grants nothing and is changed back
in one click. Neither reaches the network, the filesystem, or another account.

Governance is unchanged and re-applied at execution time by the relay: each runs
under its own capability gate, its own decision mode, a fresh PolicyEngine
review, and the posture check on the approving session. Artifacts are metadata
plus the receipt the surface links from — never the task's instructions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_TITLE_LEN = 500


def _failed(capability: str, action_id: str, reason_code: str, summary: str) -> ExecutionResult:
    return ExecutionResult(
        ok=False,
        capability=capability,
        action_id=action_id,
        reason_code=reason_code,
        summary=summary,
        artifacts={},
    )


def _optional_str(arguments: dict[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return str(value).strip()


class TaskManagementExecutor:
    """Real, local-only executor for ``task_management_runtime``.

    Creates one task in the caller's server-owned Inbox session through the same
    :class:`~raiker.control.dashboard.DashboardService` entry point the **Tasks →
    Plan work** form uses, so a task the agent asked for and a task the owner
    typed are the same row with the same scheduling and the same stop control.
    """

    capability = "task_management_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.control.dashboard import DashboardService

        title = action.arguments.get("title")
        if not isinstance(title, str) or not title.strip():
            return _failed(
                self.capability, action.action_id, "missing_argument:title",
                "Task creation failed closed: no title.",
            )
        if len(title) > _MAX_TITLE_LEN:
            return _failed(
                self.capability, action.action_id, "title_too_long",
                "Task creation failed closed: the title exceeds the bound.",
            )
        for key in ("description", "scheduled_at", "reminder_at", "recurrence", "project_id"):
            value = action.arguments.get(key)
            if value is not None and not isinstance(value, str):
                return _failed(
                    self.capability, action.action_id, f"invalid_argument:{key}",
                    f"Task creation failed closed: {key} is not a string.",
                )
        # `TaskRecord.objective` is a required contract field, so a proposal that
        # carried only a title would fail *after* the owner approved it — the one
        # outcome BUG-62 exists to remove. A task with no stated instruction is a
        # task to do what its title says, which is what the title is.
        objective = str(action.arguments.get("description", "") or "").strip() or title.strip()
        service = DashboardService(self._workspace_root)
        try:
            task = service.create_task(
                title=title.strip(),
                objective=objective,
                user_id=self._store.principal_user_id(principal.principal_id),
                principal_id=principal.principal_id,
                scheduled_at=_optional_str(action.arguments, "scheduled_at"),
                reminder_at=_optional_str(action.arguments, "reminder_at"),
                recurrence=_optional_str(action.arguments, "recurrence"),
                project_id=_optional_str(action.arguments, "project_id"),
            )
        except ValueError as exc:
            return _failed(
                self.capability, action.action_id, str(exc),
                "Task creation failed closed; nothing was created.",
            )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Task created locally in Tasks; its instructions stay out of runtime artifacts.",
            artifacts={
                "task_id": task.task_id,
                "receipt": {
                    "kind": "task",
                    "title": task.title,
                    "href": "#/tasks",
                    "label": "Review in Tasks",
                },
            },
        )


class ProjectAssignmentExecutor:
    """Real, local-only executor for ``project_assignment_runtime``.

    Moves **the conversation the approval came from** into a project. The session
    is never a model argument (a model must not be able to name someone else's
    chat): it is read from ``origin_session_id``, which the approval relay carries
    across from the approval row, so the conversation moved is the one the owner
    saw named in the decision.

    ``DashboardService.set_session_project`` is human-only and account-scoped, and
    the principal here is the approving human — which is exactly the authority the
    move needs.
    """

    capability = "project_assignment_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.control.dashboard import DashboardService

        project_id = action.arguments.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            return _failed(
                self.capability, action.action_id, "missing_argument:project_id",
                "Project assignment failed closed: no project_id.",
            )
        session_id = action.origin_session_id or action.session_id
        if not session_id:
            return _failed(
                self.capability, action.action_id, "missing_origin_session",
                "Project assignment failed closed: the proposing conversation is unknown.",
            )
        service = DashboardService(self._workspace_root)
        result = service.set_session_project(
            session_id, project_id.strip(), principal.principal_id
        )
        if not result.ok:
            return _failed(
                self.capability, action.action_id, str(result.reason_code),
                "Project assignment failed closed; the conversation was not moved.",
            )
        project = self._store.load_project(
            project_id.strip(), user_id=self._store.principal_user_id(principal.principal_id)
        )
        name = str(project.get("name")) if project else project_id.strip()
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Conversation moved into the project; the move grants nothing.",
            artifacts={
                "session_id": session_id,
                "project_id": project_id.strip(),
                "receipt": {
                    "kind": "project_assignment",
                    "title": name,
                    "href": "#/projects",
                    "label": "Review in Projects",
                },
            },
        )
