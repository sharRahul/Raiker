"""Repository delegations and the risk of each Git and GitHub operation (ADD-27 GH-50…GH-53).

A **delegation** is the owner's explicit, stored authority for repository work
without a per-step approval: one repository, a set of operations, a branch
pattern, an expiry and an optional budget, tied to the credential selected when
it was made. It is the only thing that lets a standing decision mode or a
standing grant cover a push or a GitHub write (specification §12): without one
the router asks.

What this module never allows:

* an agent creating or widening a delegation — creation is a human decision,
  and narrowing for a child is the only thing an agent may do (GH-53);
* a delegation for an operation the matrix marks *not delegable* — merging,
  deleting a branch, workflows, protected branches, repository settings
  (§8.2, GH-51);
* a delegation outliving its credential, account, installation or repository
  identity — :meth:`DelegationService.revalidate` is asked before every
  consequential step and names what changed (GH-52).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.github.http import GitHubHttp
    from raiker.runtime.authority.models import Principal
    from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class OperationRisk:
    """One row of the specification's §8.2 matrix."""

    operation: str
    label: str
    risk: str  # low / medium / high / critical / none
    default: str  # allowed / ask / ask_every_time / not_offered
    delegable: bool
    capability: str | None


#: §8.2 — the twelve operations, their risk, and whether a standing delegation
#: may cover them. The capability is the switch that governs the operation in
#: Raiker today; ``None`` means Raiker offers no way to do it.
OPERATION_RISKS: tuple[OperationRisk, ...] = (
    OperationRisk("read", "Read a repository (local)", "low", "allowed", True, None),
    OperationRisk("fetch", "Fetch or clone", "high", "ask", True, "git_fetch_execution"),
    OperationRisk("branch", "Create a local branch", "medium", "ask", True, "git_write_execution"),
    OperationRisk("commit", "Create or amend a commit", "medium", "ask", True, "git_write_execution"),
    OperationRisk("push", "Push a branch", "high", "ask", True, "git_push_execution"),
    OperationRisk("pull_request", "Open or update a pull request", "high", "ask", True, "connector_github_runtime"),
    OperationRisk("merge", "Merge a pull request", "critical", "ask_every_time", False, None),
    OperationRisk("protected_branch", "Modify a protected branch", "critical", "not_offered", False, None),
    OperationRisk("workflows", "Change workflows", "critical", "not_offered", False, None),
    OperationRisk("delete_branch", "Delete a branch", "high", "ask_every_time", False, None),
    OperationRisk("repository_permissions", "Change repository permissions", "none", "not_offered", False, None),
    OperationRisk("delete_repository", "Delete a repository", "none", "not_offered", False, None),
)
RISK_BY_OPERATION: dict[str, OperationRisk] = {row.operation: row for row in OPERATION_RISKS}
DELEGABLE_OPERATIONS: frozenset[str] = frozenset(row.operation for row in OPERATION_RISKS if row.delegable)
#: Operations that land on a branch and so need the delegation's branch pattern.
BRANCH_OPERATIONS: frozenset[str] = frozenset({"branch", "commit", "push"})
#: Branches a pattern may never reach: a delegation is for work branches, and
#: the default branch is what a reviewer merges into.
PROTECTED_BRANCH_NAMES: tuple[str, ...] = ("main", "master", "trunk", "develop", "release", "production")
MAX_DELEGATION_HOURS = 24 * 30
_REPOSITORY_RE = re.compile(r"^github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_PATTERN_RE = re.compile(r"^[A-Za-z0-9_.\-/*?]{1,200}$")


class DelegationError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


def credential_owner(store: SQLiteStore, principal_id: str) -> str:
    """The account whose credentials and delegations an actor works under.

    An agent acting for the owner borrows the owner's connection; it has none
    of its own.
    """
    try:
        scope = store.account_scope(principal_id)
        if scope:
            return scope
        principal = store.get_principal(principal_id)
        user_id = (principal or {}).get("delegated_by_user_id")
        if principal is None or str(principal.get("principal_type")) == "human" or not user_id:
            return principal_id
        # A turn's agent carries its owner's user id. On a machine whose owner
        # has no password account the human principal for that user is the
        # owner — when there is exactly one.
        with store.connect() as connection:
            humans = connection.execute(
                """SELECT principal_id FROM principals
                   WHERE principal_type = 'human' AND delegated_by_user_id = ? AND is_active = 1
                   LIMIT 2""",
                (user_id,),
            ).fetchall()
        return str(humans[0][0]) if len(humans) == 1 else principal_id
    except Exception:  # noqa: BLE001 — an unknown actor is scoped to itself
        return principal_id


def delegation_state(row: dict[str, Any], *, now: str | None = None) -> str:
    """``active``, ``revoked``, ``expired`` or ``exhausted``."""
    if row.get("revoked_at"):
        return "revoked"
    if str(row.get("expires_at") or "") <= (now or utc_now()):
        return "expired"
    limit = row.get("max_actions")
    if limit is not None and int(row.get("actions_used") or 0) >= int(limit):
        return "exhausted"
    return "active"


def _expiry(hours: float) -> str:
    moment = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=hours)
    return moment.isoformat().replace("+00:00", "Z")


def _pattern_reaches_protected(pattern: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for name in PROTECTED_BRANCH_NAMES)


def _is_literal(pattern: str) -> bool:
    return not any(char in pattern for char in "*?[")


def _full_name(repository: str) -> str:
    return repository.split("/", 1)[1] if repository.startswith("github.com/") else repository


class DelegationService:
    """The owner's delegations: create, narrow, cover, spend, revalidate, revoke."""

    def __init__(self, store: SQLiteStore, principal_id: str) -> None:
        self._store = store
        self._principal_id = principal_id

    # ── records ─────────────────────────────────────────────────────────
    def _record(self, event_type: str, payload: dict[str, Any], session_id: str | None = None) -> None:
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        try:
            EventLogWriter(self._store).append(
                make_event(
                    session_id=session_id or "git_credential", turn_id=None, event_type=event_type,
                    actor="repository_delegations", payload={"principal_id": self._principal_id, **payload},
                )
            )
        except Exception:  # noqa: BLE001 — the decision stands whether or not it is recorded
            return

    def delegations(self, *, include_ended: bool = False) -> list[dict[str, Any]]:
        rows = self._store.list_repository_delegations(self._principal_id, include_ended=include_ended)
        return [{**row, "state": delegation_state(row)} for row in rows]

    def get(self, delegation_id: str) -> dict[str, Any]:
        row = self._store.load_repository_delegation(delegation_id)
        if row is None or row.get("principal_id") != self._principal_id:
            raise DelegationError("delegation_unknown", "No such delegation.")
        return {**row, "state": delegation_state(row)}

    # ── creation ────────────────────────────────────────────────────────
    def _validate_shape(
        self, repository: str, operations: list[str], branch_pattern: str | None, hours: float
    ) -> tuple[list[str], str | None]:
        if not _REPOSITORY_RE.match(repository or ""):
            raise DelegationError("delegation_repository_invalid", "Name one repository as github.com/owner/name.")
        wanted = sorted({str(op).strip() for op in operations if str(op).strip()})
        if not wanted:
            raise DelegationError("delegation_operations_required", "Choose at least one operation.")
        for operation in wanted:
            if operation not in RISK_BY_OPERATION:
                raise DelegationError(f"delegation_operation_unknown:{operation}")
            if operation not in DELEGABLE_OPERATIONS:
                raise DelegationError(
                    f"delegation_operation_not_delegable:{operation}",
                    f"{RISK_BY_OPERATION[operation].label} is never delegated; it is asked every time or not offered.",
                )
        pattern = (branch_pattern or "").strip() or None
        if BRANCH_OPERATIONS & set(wanted):
            if pattern is None:
                raise DelegationError(
                    "delegation_branch_pattern_required", "Name the branches this work may touch, e.g. raiker/*."
                )
            if not _BRANCH_PATTERN_RE.match(pattern) or pattern[0] in "*?/":
                # It starts with a name — `raiker/*`, `fix-` — or it is every branch.
                raise DelegationError("delegation_branch_pattern_too_broad", "Name a branch prefix, not every branch.")
            if _pattern_reaches_protected(pattern):
                raise DelegationError(
                    "delegation_branch_pattern_too_broad",
                    "A delegation never reaches the default branch; use a work-branch prefix.",
                )
        if not (0 < hours <= MAX_DELEGATION_HOURS):
            raise DelegationError(
                "delegation_expiry_invalid", f"A delegation lasts between an hour and {MAX_DELEGATION_HOURS // 24} days."
            )
        return wanted, pattern

    def create(
        self,
        *,
        created_by: Principal,
        repository: str,
        operations: list[str],
        branch_pattern: str | None = None,
        expires_in_hours: float = 24.0,
        max_actions: int | None = None,
        task_id: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """The owner delegates repository work. Only a human may."""
        from raiker.runtime.authority.models import PrincipalType

        if created_by.principal_type != PrincipalType.HUMAN:
            raise DelegationError("delegation_requires_human", "Only you can delegate repository work.")
        wanted, pattern = self._validate_shape(repository, operations, branch_pattern, expires_in_hours)
        if max_actions is not None and int(max_actions) <= 0:
            raise DelegationError("delegation_budget_invalid", "A budget is a positive number of actions.")
        from raiker.runtime.git_credential import GitCredentialBroker

        selected = GitCredentialBroker(self._store, self._principal_id).methods.selected()
        if selected is None:
            raise DelegationError("delegation_credential_required", "Connect GitHub before delegating work to it.")
        known = self._store.github_repository_by_name(self._principal_id, _full_name(repository))
        if known is not None and known.get("status") != "available":
            raise DelegationError("repository_access_removed", "Raiker no longer has access to that repository.")
        row = self._store.create_repository_delegation(
            principal_id=self._principal_id, repository=repository,
            repository_id=str(known["repository_id"]) if known else None,
            operations=wanted, branch_pattern=pattern,
            allow_pull_request="pull_request" in wanted,
            expires_at=_expiry(expires_in_hours), created_by=created_by.principal_id,
            max_actions=int(max_actions) if max_actions is not None else None,
            credential_id=str(selected["credential_id"]), task_id=task_id, note=(note or None),
        )
        self._record("repository_delegation_created", self._summary(row))
        return {**row, "state": delegation_state(row)}

    def narrow(
        self,
        parent_id: str,
        *,
        created_by: Principal,
        operations: list[str] | None = None,
        branch_pattern: str | None = None,
        expires_in_hours: float | None = None,
        max_actions: int | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """A child's share of a parent delegation — never more (GH-53).

        Anyone working under the parent may hand a child less of it. Every field
        is checked against the parent: operations a subset, the branch pattern
        the parent's own or one branch it already reaches, expiry no later,
        budget no larger than what the parent has left.
        """
        parent = self.get(parent_id)
        if parent["state"] != "active":
            raise DelegationError(f"delegation_{parent['state']}", "The delegation this would narrow has ended.")
        wanted = sorted(set(operations if operations is not None else parent["operations"]))
        extra = sorted(set(wanted) - set(parent["operations"]))
        if extra:
            raise DelegationError("delegation_exceeds_parent:operations", f"Not delegated: {', '.join(extra)}.")
        parent_pattern = parent.get("branch_pattern")
        pattern = (branch_pattern or "").strip() or parent_pattern
        if pattern != parent_pattern and (
            parent_pattern is None or not _is_literal(str(pattern)) or not fnmatch.fnmatchcase(str(pattern), parent_pattern)
        ):
            raise DelegationError("delegation_exceeds_parent:branch_pattern", "A child may only work on the parent's branches.")
        expires_at = str(parent["expires_at"])
        if expires_in_hours is not None:
            candidate = _expiry(expires_in_hours)
            if candidate > expires_at:
                raise DelegationError("delegation_exceeds_parent:expires_at", "A child cannot outlast its parent.")
            expires_at = candidate
        remaining = (
            int(parent["max_actions"]) - int(parent.get("actions_used") or 0)
            if parent.get("max_actions") is not None
            else None
        )
        if max_actions is not None and remaining is not None and int(max_actions) > remaining:
            raise DelegationError("delegation_exceeds_parent:max_actions", "A child cannot spend more than is left.")
        budget = int(max_actions) if max_actions is not None else remaining
        row = self._store.create_repository_delegation(
            principal_id=self._principal_id, repository=str(parent["repository"]),
            repository_id=parent.get("repository_id"), operations=wanted, branch_pattern=pattern,
            allow_pull_request="pull_request" in wanted, expires_at=expires_at,
            created_by=created_by.principal_id, max_actions=budget,
            credential_id=parent.get("credential_id"), parent_delegation_id=parent_id,
            task_id=task_id or parent.get("task_id"),
        )
        self._record("repository_delegation_created", {**self._summary(row), "parent_delegation_id": parent_id})
        return {**row, "state": delegation_state(row)}

    # ── use ─────────────────────────────────────────────────────────────
    def covering(
        self, repository: str, operation: str, branch: str | None = None, *, delegation_id: str | None = None
    ) -> dict[str, Any] | None:
        """The active delegation that covers this exact use, if any."""
        if operation not in DELEGABLE_OPERATIONS:
            return None
        rows = [self.get(delegation_id)] if delegation_id else self.delegations()
        for row in rows:
            if row["state"] != "active":
                continue
            if str(row["repository"]).lower() != repository.lower():
                continue
            if operation not in row["operations"]:
                continue
            pattern = row.get("branch_pattern")
            if operation in BRANCH_OPERATIONS:
                if not branch or not pattern or not fnmatch.fnmatchcase(branch, str(pattern)):
                    continue
            elif operation == "pull_request" and pattern and (not branch or not fnmatch.fnmatchcase(branch, str(pattern))):
                # A pull request proposes a branch; it has to be one of the delegated ones.
                continue
            return row
        return None

    def spend(
        self, row: dict[str, Any], *, operation: str, branch: str | None, action_id: str, session_id: str | None
    ) -> bool:
        """Spend one action; record what the delegation allowed and what ran."""
        parent_id = row.get("parent_delegation_id")
        if parent_id:
            # A child's action is the parent's action too: one budget, shared,
            # and nothing left of a parent that has ended.
            parent = self._store.load_repository_delegation(str(parent_id))
            if parent is None or delegation_state(parent) != "active":
                return False
        if not self._store.count_repository_delegation_action(str(row["delegation_id"])):
            return False
        if parent_id and not self._store.count_repository_delegation_action(str(parent_id)):
            return False
        self._record(
            "repository_delegation_used",
            {
                "delegation_id": row["delegation_id"], "repository": row["repository"],
                "allowed_operations": row["operations"], "branch_pattern": row.get("branch_pattern"),
                "operation": operation, "branch": branch, "action_id": action_id,
            },
            session_id=session_id,
        )
        return True

    # ── revalidation (GH-52) ────────────────────────────────────────────
    def revalidate(self, row: dict[str, Any], *, http: GitHubHttp | None = None) -> list[str]:
        """Everything that no longer holds for *row*; empty when all of it does.

        Checked: the delegation itself; the credential it was made with — still
        there, still selected, still the same account; the installation the
        repository is reached through; and the repository's identity by id.
        With *http*, GitHub is asked for the repository by name as well, so a
        transfer or a removed grant is seen even before discovery runs again.
        """
        problems: list[str] = []
        state = delegation_state(row)
        if state != "active":
            problems.append(f"delegation_{state}")
        credential_id = row.get("credential_id")
        credential = self._store.load_git_credential(str(credential_id)) if credential_id else None
        if credential_id and (credential is None or credential.get("principal_id") != self._principal_id):
            problems.append("credential_removed")
        elif credential is not None:
            if credential.get("status") not in ("active", "unverified"):
                problems.append(f"credential_{credential.get('status')}")
            from raiker.runtime.git_credential import GitCredentialBroker

            selected = GitCredentialBroker(self._store, self._principal_id).methods.selected()
            if selected is None or selected.get("credential_id") != credential_id:
                problems.append("credential_not_selected")
        full_name = _full_name(str(row["repository"]))
        known = self._store.github_repository_by_name(self._principal_id, full_name)
        repository_id = row.get("repository_id")
        if known is not None:
            if known.get("status") != "available":
                problems.append("repository_access_removed")
            elif repository_id and str(known.get("repository_id")) != str(repository_id):
                problems.append("repository_identity_changed")
            installation_id = known.get("installation_id")
            if installation_id:
                installation = self._store.load_github_installation(str(installation_id))
                if installation is None or installation.get("status") != "active":
                    status = (installation or {}).get("status") or "removed"
                    problems.append(f"installation_{status}")
        elif repository_id:
            problems.append("repository_access_removed")
        if http is not None and credential is not None and not problems:
            problems.extend(self._remote_identity(row, credential, http))
        return problems

    def _remote_identity(self, row: dict[str, Any], credential: dict[str, Any], http: GitHubHttp) -> list[str]:
        from raiker.github.credentials import METHOD_SSH, CredentialMethodError
        from raiker.github.http import GitHubHttpError
        from raiker.runtime.git_credential import GitCredentialBroker

        if credential.get("method") == METHOD_SSH:
            return []
        methods = GitCredentialBroker(self._store, self._principal_id).methods
        try:
            token = methods.secret(credential, verify=True, repository=str(row["repository"]), operation="fetch")
            response = http.get_json(f"https://api.github.com/repos/{_full_name(str(row['repository']))}", token=token)
        except (CredentialMethodError, GitHubHttpError) as exc:
            return [getattr(exc, "reason", "credential_unavailable")]
        if response.status in (403, 404):
            return ["repository_access_removed"]
        if response.status != 200 or not isinstance(response.data, dict):
            return [f"github_unavailable:{response.status}"]
        found = str(response.data.get("id") or "")
        if row.get("repository_id") and found != str(row["repository_id"]):
            return ["repository_identity_changed"]
        return []

    # ── revocation ──────────────────────────────────────────────────────
    def revoke(self, delegation_id: str, *, revoked_by: Principal) -> list[str]:
        from raiker.runtime.authority.models import PrincipalType
        from raiker.storage.deletion_journal import DELEGATION_REVOKE, record_deletion

        if revoked_by.principal_type != PrincipalType.HUMAN:
            raise DelegationError("delegation_requires_human", "Only you can revoke a delegation.")
        revoked = self._store.revoke_repository_delegation(delegation_id, self._principal_id)
        if not revoked:
            raise DelegationError("delegation_unknown", "No such delegation, or it already ended.")
        for revoked_id in revoked:
            # Journaled so a restore from an older backup cannot bring it back.
            record_deletion(self._store.paths.workspace_root, DELEGATION_REVOKE, revoked_id, self._principal_id)
        self._record("repository_delegation_revoked", {"delegation_id": delegation_id, "revoked": revoked})
        return revoked

    @staticmethod
    def _summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "delegation_id": row["delegation_id"], "repository": row["repository"],
            "repository_id": row.get("repository_id"), "operations": row.get("operations"),
            "branch_pattern": row.get("branch_pattern"), "expires_at": row.get("expires_at"),
            "max_actions": row.get("max_actions"), "credential_id": row.get("credential_id"),
            "created_by": row.get("created_by"),
        }


def risk_table() -> list[dict[str, Any]]:
    """§8.2 as a surface renders it."""
    return [
        {
            "operation": row.operation, "label": row.label, "risk": row.risk,
            "default": row.default, "delegable": row.delegable, "capability": row.capability,
        }
        for row in OPERATION_RISKS
    ]
