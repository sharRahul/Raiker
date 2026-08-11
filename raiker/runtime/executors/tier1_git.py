from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult
from raiker.tools.git import (
    create_branch,
    create_commit,
    push_branch,
    repository_label,
    resolve_repository_root,
    selected_repository_subpath,
)


def _legacy_credential() -> bool:
    """True when this host still carries the token in its environment."""
    import os

    from raiker.runtime.git_credential import LEGACY_TOKEN_ENV

    return bool(os.environ.get(LEGACY_TOKEN_ENV, "").strip())

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore


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

    def __init__(self, workspace_root: str | Path, store: SQLiteStore | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    # BUG-66 — the same resolution the broker used to compute the proposal. An
    # execution that fell back to the workspace root would record the change in a
    # repository the owner never saw named in the approval.
    def _repo_root(self, principal: Principal) -> Path:
        return resolve_repository_root(
            self._workspace_root,
            selected_repository_subpath(self._store, self._owner_scope(principal)),
        )

    def _owner_scope(self, principal: Principal) -> str | None:
        if self._store is None:
            return None
        try:
            return self._store.account_scope(principal.principal_id) or principal.principal_id
        except Exception:  # noqa: BLE001 — a storage failure falls back to the workspace
            return None

    def _repository(self, root: Path) -> str:
        return repository_label(self._workspace_root, root)

    def _in_repository(self, root: Path) -> str:
        """" in <repository>", or nothing when the repository *is* the workspace.

        A workspace with one repository is the common case, and naming it there
        would be noise in the one sentence the owner reads after approving.
        """
        label = self._repository(root)
        return "" if label == "." else f" in {label}"

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = action.action_type
        try:
            root = self._repo_root(principal)
            if operation == "git_branch":
                return self._branch(action, root)
            if operation == "git_commit":
                return self._commit(action, root)
        except Exception as exc:  # noqa: BLE001 — every failure is reported, never raised
            return self._fail(action.action_id, f"git_write_failed:{type(exc).__name__}")
        return self._fail(action.action_id, f"unknown_git_operation:{operation or 'missing'}")

    def _branch(self, action: GovernedAction, root: Path) -> ExecutionResult:
        name = str(action.arguments.get("name", "")).strip()
        base_value = action.arguments.get("base")
        result = create_branch(
            root, name, str(base_value).strip() if base_value else None
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
            f"(from {result['previous_branch'] or result['head']})"
            f"{self._in_repository(root)}."
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
                "repository": self._repository(root),
            },
        )

    def _commit(self, action: GovernedAction, root: Path) -> ExecutionResult:
        message = str(action.arguments.get("message", ""))
        result = create_commit(root, message, action.arguments.get("paths"))
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
            f"on {result['branch']}{self._in_repository(root)}."
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
                "repository": self._repository(root),
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action_id,
            reason_code=reason_code,
            summary="Git write failed closed.",
            artifacts={},
        )


class GitPushExecutor:
    """Real executor for ``git_push_execution`` — one governed push (BUG-67).

    B11 let the agent create a branch and record a commit on it, and stopped
    there: the branch existed only on this machine, and ``github_write`` could
    not open a pull request for a head GitHub had never seen. This executor is
    the missing motion.

    It is deliberately *not* part of ``git_write_execution``. A commit is local
    and the owner can undo it in git; a push carries repository content off the
    machine under the owner's credential and nothing unsends it. So it answers to
    its own switch, and to two boundaries the switch cannot substitute for: the
    remote's host must be on the owner's connector egress allowlist, and the
    owner's credential must be configured. Both are checked again here, against
    the repository as it is now rather than as the approval found it.
    """

    capability = "git_push_execution"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def _repo_root(self, principal: Principal) -> Path:
        scope: str | None = None
        if self._store is not None:
            try:
                scope = self._store.account_scope(principal.principal_id) or principal.principal_id
            except Exception:  # noqa: BLE001 — a storage failure falls back to the workspace
                scope = None
        return resolve_repository_root(
            self._workspace_root, selected_repository_subpath(self._store, scope)
        )

    def _lend(
        self, principal: Principal, action: GovernedAction
    ) -> tuple[str | None, Callable[[], Any]] | ExecutionResult:
        """The credential for this push, and the callable that ends the loan.

        Returns an :class:`ExecutionResult` instead when the owner has not
        approved one — a refusal the model can read and act on, rather than an
        exception.
        """
        from raiker.runtime.git_credential import (
            RUNTIME_TOKEN_VAR,
            GitCredentialBroker,
            GitCredentialError,
        )

        if self._store is None:
            # No store means no grant can exist to check, so the only honest
            # path is the legacy environment credential.
            return None, lambda: None
        broker = GitCredentialBroker(self._store, principal.principal_id)
        loan = broker.lend(session_id=action.arguments.get("session_id"))
        try:
            environment = loan.__enter__()
        except GitCredentialError as exc:
            if exc.reason == "git_grant_required" and _legacy_credential():
                return None, lambda: None
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=exc.reason, summary=exc.message, artifacts={},
            )
        return environment.get(RUNTIME_TOKEN_VAR), lambda: loan.__exit__(None, None, None)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        if action.action_type not in ("git_push", "git_push_execution"):
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"unknown_git_operation:{action.action_type or 'missing'}",
                summary="Git push failed closed.", artifacts={},
            )
        try:
            root = self._repo_root(principal)
            remote = action.arguments.get("remote")
            branch = action.arguments.get("branch")
            remote_name = str(remote).strip() if remote else None
            branch_name = str(branch).strip() if branch else None
            # RAIKER-2022 — the credential is lent for this one command, under a
            # grant the owner made. `lend()` refuses without one, registers the
            # exact value with the redactor for the length of the call, and
            # consumes a one-shot grant on the way out.
            #
            # A host still configured the old way (RAIKER_GITHUB_TOKEN in the
            # environment, no grant row) keeps working: the push falls back to
            # it. This adds a control without taking a working deployment away.
            granted = self._lend(principal, action)
            if isinstance(granted, ExecutionResult):
                return granted
            lent, release = granted
            try:
                result = push_branch(root, remote_name, branch_name, credential=lent)
            finally:
                release()
        except Exception as exc:  # noqa: BLE001 — every failure is reported, never raised
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"git_push_failed:{type(exc).__name__}",
                summary="Git push failed closed.", artifacts={},
            )
        repository = repository_label(self._workspace_root, root)
        if result["status"] != "success":
            error = result["error"]
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"push_failed:{error['type']}",
                summary="Push refused; nothing left this machine.",
                artifacts={"error": error, "repository": repository},
            )
        created = " (new remote branch)" if result["created_remote_branch"] else ""
        summary = (
            f"Pushed {result['commit_count']} commit(s) on {result['branch']} to "
            f"{result['remote']} ({result['host']}){created}."
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=summary,
            artifacts={
                "summary": summary,
                "remote": result["remote"],
                "host": result["host"],
                "branch": result["branch"],
                "head": result["head"],
                "commit_count": result["commit_count"],
                "created_remote_branch": result["created_remote_branch"],
                "repository": repository,
            },
        )
