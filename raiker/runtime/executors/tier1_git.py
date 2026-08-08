from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult
from raiker.tools.git import create_branch, create_commit

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class GitWriteExecutor:
    """Real executor for ``git_write_execution`` — one governed branch or commit (B11).

    Build could describe a change it could neither commit nor propose: the git
    surface was ``status``/``diff``/``log`` and stopped there. This executor is
    the write half, and it is reached only through ``route_action`` — so the
    capability gate, the decision mode, policy review and the approval the owner
    resolved have all already been applied by the time it runs.

    Both operations re-derive their own proposal before mutating anything, so a
    repository that moved between the approval and the execution fails closed
    with a named reason instead of recording something the owner never saw.
    Repository hooks are disabled for the invocation (see ``raiker.tools.git``):
    a governed write must not become an un-governed code-execution path.
    """

    capability = "git_write_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = action.action_type
        try:
            if operation == "git_branch":
                return self._branch(action)
            if operation == "git_commit":
                return self._commit(action)
        except Exception as exc:  # noqa: BLE001 — every failure is reported, never raised
            return self._fail(action.action_id, f"git_write_failed:{type(exc).__name__}")
        return self._fail(action.action_id, f"unknown_git_operation:{operation or 'missing'}")

    def _branch(self, action: GovernedAction) -> ExecutionResult:
        name = str(action.arguments.get("name", "")).strip()
        base_value = action.arguments.get("base")
        result = create_branch(
            self._workspace_root, name, str(base_value).strip() if base_value else None
        )
        if result["status"] != "success":
            error = result["error"]
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"branch_failed:{error['type']}",
                summary="Branch rejected; the repository was not changed.",
                artifacts={"name": name, "error": error},
            )
        summary = (
            f"Created and checked out {result['branch']} "
            f"(from {result['previous_branch'] or result['head']})."
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=summary,
            artifacts={
                # The sentence travels with the artifacts as well as on the
                # result, because the approval inbox reads artifacts: an owner
                # who just approved a repository change should be told which
                # branch or commit now exists, not only that something ran.
                "summary": summary,
                "branch": result["branch"],
                "base": result["base"],
                "previous_branch": result["previous_branch"],
                "head": result["head"],
            },
        )

    def _commit(self, action: GovernedAction) -> ExecutionResult:
        message = str(action.arguments.get("message", ""))
        result = create_commit(self._workspace_root, message, action.arguments.get("paths"))
        if result["status"] != "success":
            error = result["error"]
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"commit_failed:{error['type']}",
                summary="Commit rejected; nothing was recorded.",
                artifacts={"error": error},
            )
        summary = (
            f"Committed {result['file_count']} file(s) as {result['commit']} "
            f"on {result['branch']}."
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=summary,
            artifacts={
                "summary": summary,
                "commit": result["commit"],
                "branch": result["branch"],
                "subject": result["subject"],
                "file_count": result["file_count"],
                "files": [entry["path"] for entry in result["files"]],
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action_id,
            reason_code=reason_code,
            summary="Git write failed closed.",
            artifacts={},
        )
