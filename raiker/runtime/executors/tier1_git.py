from __future__ import annotations

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

    # BUG-66 — the same resolution the broker computed the proposal with. An
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

    def repository_target(self, action: GovernedAction, principal: Principal) -> dict[str, Any] | None:
        """The GitHub repository and branch this branch or commit is on (BUG-337).

        Branch and commit are the specification's other two delegable
        operations (§8.2), so the router holds them to the same rule as a push:
        unprompted only under a repository delegation whose branch pattern
        covers them. A repository with no GitHub remote has nothing to delegate
        and keeps the capability's decision mode, as before.
        """
        from raiker.runtime.git_credential import repository_key
        from raiker.tools.git import github_remote_url

        if action.action_type == "git_branch":
            operation = "branch"
            branch = str(action.arguments.get("name", "")).strip() or None
        elif action.action_type == "git_commit":
            operation = "commit"
            branch = None
        else:
            return None
        root = self._repo_root(principal)
        remote_url = github_remote_url(root)
        if not remote_url:
            return None
        if operation == "commit":
            from raiker.tools.git import current_branch

            branch = current_branch(root) or None
        return {"repository": repository_key(remote_url), "operation": operation, "branch": branch}

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

    def _refused(self, action: GovernedAction, error: dict[str, Any], root: Path) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=f"push_failed:{error['type']}",
            summary="Push refused; nothing left this machine.",
            artifacts={"error": error, "repository": repository_label(self._workspace_root, root)},
        )

    def _binding(self, action: GovernedAction) -> dict[str, Any] | None | ExecutionResult:
        """What the owner was shown, when this push runs on their approval (BUG-336).

        A push that runs under a standing decision instead had no approval to be
        shown, so there is nothing to hold it to beyond the snapshot it takes
        itself. A push on an approval that recorded nothing — one raised before
        RAIKER-2106 — is refused rather than run unbound.
        """
        if action.authority_kind != "approval":
            return None
        binding = (
            self._store.load_git_push_binding(action.authority_id)
            if self._store is not None and action.authority_id
            else None
        )
        if binding is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="push_failed:push_binding_missing",
                summary="This approval did not record what it would push; ask for the push again.",
                artifacts={},
            )
        return binding

    def repository_target(self, action: GovernedAction, principal: Principal) -> dict[str, Any]:
        """Which repository and branch this push would reach (GH-50).

        Resolved from the repository as it is now, without the network, so the
        router can ask whether a delegation covers it. Anything that cannot be
        resolved is still a push — it just has no delegation to run under.
        """
        from raiker.runtime.git_credential import repository_key
        from raiker.tools.git import proposed_push_snapshot

        remote = action.arguments.get("remote")
        branch = action.arguments.get("branch")
        snapshot = proposed_push_snapshot(
            self._repo_root(principal),
            str(remote).strip() if remote else None,
            str(branch).strip() if branch else None,
            credential_configured=True,
        )
        if snapshot.get("status") != "success":
            return {"repository": "", "operation": "push", "branch": None}
        return {
            "repository": repository_key(str(snapshot["remote_url"])),
            "operation": "push",
            "branch": str(snapshot["branch"]),
        }

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        if action.action_type not in ("git_push", "git_push_execution"):
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"unknown_git_operation:{action.action_type or 'missing'}",
                summary="Git push failed closed.", artifacts={},
            )
        from raiker.github.delegations import credential_owner
        from raiker.runtime.git_credential import (
            RUNTIME_TOKEN_VAR,
            GitCredentialBroker,
            GitCredentialError,
            repository_key,
        )
        from raiker.tools.git import proposed_push_snapshot, push_target_changes

        try:
            root = self._repo_root(principal)
            remote = action.arguments.get("remote")
            branch = action.arguments.get("branch")
            broker = (
                GitCredentialBroker(self._store, credential_owner(self._store, principal.principal_id))
                if self._store is not None
                else None
            )
            snapshot = proposed_push_snapshot(
                root,
                str(remote).strip() if remote else None,
                str(branch).strip() if branch else None,
                credential_method=broker.selected_method() if broker is not None else None,
            )
            if snapshot["status"] != "success":
                return self._refused(action, snapshot["error"], root)
            binding = self._binding(action)
            if isinstance(binding, ExecutionResult):
                return binding
            # Without an approval to hold it to, the push is held to what it
            # found a moment ago, so nothing committed in between rides along.
            expected = binding or snapshot
            changed = push_target_changes(snapshot, expected)
            if changed:
                return self._refused(action, {"type": "push_target_changed", "changed": changed}, root)
            if broker is None:
                return self._refused(action, {"type": "push_credential_unset"}, root)
            # RAIKER-2022 — the credential is lent for this one command, under a
            # grant the owner made, which has to cover this conversation, this
            # repository and this branch (BUG-335, GH-17). The conversation is
            # the one that proposed the push, carried on the approval; the relay
            # itself runs in the inbox's session.
            try:
                with broker.lend(
                    session_id=action.origin_session_id or action.session_id or None,
                    operation="push",
                    repository=repository_key(str(snapshot["remote_url"])),
                    branch=str(snapshot["branch"]),
                    delegation_id=action.authority_id if action.authority_kind == "delegation" else None,
                ) as environment:
                    result = push_branch(
                        root, str(snapshot["remote"]), str(snapshot["branch"]),
                        credential=environment.get(RUNTIME_TOKEN_VAR), expected=expected,
                        ssh_command=environment.get("GIT_SSH_COMMAND"),
                    )
            except GitCredentialError as exc:
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code=exc.reason, summary=exc.message, artifacts={},
                )
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
        receipt = result.get("receipt") or {}
        confirmed = (
            " Confirmed on the remote."
            if receipt.get("verified")
            else " Not yet confirmed on the remote — check the branch there."
        )
        summary = (
            f"Pushed {result['commit_count']} commit(s) on {result['branch']} to "
            f"{result['remote']} ({result['host']}){created}.{confirmed}"
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
                "receipt": receipt,
            },
        )


class GitFetchExecutor:
    """Real executor for ``git_fetch_execution`` — one governed fetch or clone (ADD-27 GH-23).

    Network egress like a push, so its own capability and the same host rules;
    but it brings content in rather than sending it out, so a public repository
    needs no credential. The owner's credential is lent only when a grant covers
    fetching this repository, and a private repository fetched without one is
    refused with a reason that says so.
    """

    capability = "git_fetch_execution"

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

    def _result(self, action: GovernedAction, outcome: dict[str, Any], summary: str) -> ExecutionResult:
        if outcome["status"] != "success":
            error = outcome["error"]
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"fetch_failed:{error['type']}",
                summary="Nothing was fetched.", artifacts={"error": error},
            )
        artifacts = {
            key: outcome.get(key)
            for key in ("remote", "repository", "path", "host", "transport", "head", "updated_refs")
            if outcome.get(key) is not None
        }
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=summary, artifacts={"summary": summary, **artifacts},
        )

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.github.delegations import DelegationService, credential_owner
        from raiker.runtime.git_credential import (
            RUNTIME_TOKEN_VAR,
            GitCredentialBroker,
            GitCredentialError,
        )
        from raiker.tools.git import (
            clone_repository,
            fetch_remote,
            proposed_clone_snapshot,
            proposed_fetch_snapshot,
        )

        operation = action.action_type
        if operation not in ("git_fetch", "git_clone"):
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"unknown_git_operation:{operation or 'missing'}",
                summary="Git fetch failed closed.", artifacts={},
            )
        try:
            broker = (
                GitCredentialBroker(self._store, credential_owner(self._store, principal.principal_id))
                if self._store is not None
                else None
            )
            method = broker.selected_method() if broker is not None else None
            if operation == "git_clone":
                repository = str(action.arguments.get("repository", ""))
                path = action.arguments.get("path")
                snapshot = proposed_clone_snapshot(
                    self._workspace_root, repository, str(path) if path else None,
                    credential_method=method,
                )
            else:
                remote = action.arguments.get("remote")
                snapshot = proposed_fetch_snapshot(
                    self._repo_root(principal), str(remote) if remote else None,
                    credential_method=method,
                )
            if snapshot["status"] != "success":
                return self._result(action, snapshot, "")
            session = action.origin_session_id or action.session_id or None
            environment: dict[str, str] = {}
            loan = None
            if broker is not None and broker.live_grant() is not None:
                # Lend only under a grant that covers fetching this repository;
                # a grant for anything else is a reason to fetch anonymously,
                # not to borrow it.
                try:
                    broker.covering_grant(
                        session_id=session, operation="fetch",
                        repository=str(snapshot["repository_key"]), branch=None,
                    )
                    loan = broker.lend(
                        session_id=session, operation="fetch",
                        repository=str(snapshot["repository_key"]),
                    )
                except GitCredentialError:
                    loan = None
            if self._store is not None and broker is not None and loan is None and principal.principal_type != "human":
                # GH-50 — or under the owner's delegation to fetch this repository,
                # re-checked now and spending one of its actions.
                owner = credential_owner(self._store, principal.principal_id)
                delegations = DelegationService(self._store, owner)
                covering = delegations.covering(str(snapshot["repository_key"]), "fetch")
                if (
                    covering is not None
                    and not delegations.revalidate(covering)
                    and delegations.spend(
                        covering, operation="fetch", branch=None,
                        action_id=action.action_id, session_id=session,
                    )
                ):
                    loan = broker.lend(
                        session_id=session, operation="fetch",
                        repository=str(snapshot["repository_key"]),
                        delegation_id=str(covering["delegation_id"]),
                    )
            if snapshot["transport"] == "ssh" and loan is None:
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code="git_grant_required",
                    summary="Fetching over SSH needs your SSH key lent for fetching this repository.",
                    artifacts={},
                )
            try:
                if loan is not None:
                    environment = loan.__enter__()
                if operation == "git_clone":
                    outcome = clone_repository(
                        self._workspace_root, str(action.arguments.get("repository", "")),
                        str(action.arguments["path"]) if action.arguments.get("path") else None,
                        credential=environment.get(RUNTIME_TOKEN_VAR),
                        ssh_command=environment.get("GIT_SSH_COMMAND"),
                    )
                    summary = f"Cloned {outcome.get('repository')} into {outcome.get('path')}."
                else:
                    outcome = fetch_remote(
                        self._repo_root(principal),
                        str(action.arguments["remote"]) if action.arguments.get("remote") else None,
                        credential=environment.get(RUNTIME_TOKEN_VAR),
                        ssh_command=environment.get("GIT_SSH_COMMAND"),
                    )
                    summary = (
                        f"Fetched {outcome.get('remote')} ({len(outcome.get('updated_refs') or [])} ref(s) updated)."
                    )
            finally:
                if loan is not None:
                    loan.__exit__(None, None, None)
            if outcome["status"] != "success" and outcome["error"]["type"] == "fetch_authentication_required" and loan is None:
                outcome["error"]["hint"] = "Approve your Git credential for fetching this repository."
            return self._result(action, outcome, summary)
        except GitCredentialError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=exc.reason, summary=exc.message, artifacts={},
            )
        except Exception as exc:  # noqa: BLE001 — every failure is reported, never raised
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"git_fetch_failed:{type(exc).__name__}",
                summary="Git fetch failed closed.", artifacts={},
            )
