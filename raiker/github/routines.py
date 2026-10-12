"""The issue-to-pull-request routine template (ADD-27 GH-55).

A template, not a runner: it names the steps an approved issue-to-PR routine
takes and the authority each one needs, and — given the routine's stored
delegation reference, if any — says which steps would run unprompted and which
would ask. Two rules hold whatever the routine is told:

* **Read-only by default.** Without a delegation every write step asks.
* **A scheduled run creates no authority.** The routine carries a delegation
  *reference* the owner made; it is re-validated before the plan is made, and
  the template has no way to create, widen or extend one.

Running the plan end to end needs a routine runner that can drive write-capable
agent turns; today's scheduled routines run read-only subagents only
(``raiker/runtime/executors/scheduled.py``). That gap is recorded, not papered
over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raiker.github.delegations import DelegationError, DelegationService

if TYPE_CHECKING:
    from raiker.github.http import GitHubHttp
    from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class RoutineStep:
    step: str
    label: str
    operation: str  # the §8.2 operation it needs; "read" needs nothing
    writes: bool


ISSUE_TO_PR_STEPS: tuple[RoutineStep, ...] = (
    RoutineStep("read_issue", "Read the issue (as untrusted data)", "read", False),
    RoutineStep("fetch", "Fetch the repository", "fetch", False),
    RoutineStep("branch", "Create a work branch", "branch", True),
    RoutineStep("commit", "Commit the change on it", "commit", True),
    RoutineStep("push", "Push the work branch", "push", True),
    RoutineStep("pull_request", "Open a pull request", "pull_request", True),
    RoutineStep("report", "Report what was done, with the receipts", "read", False),
)
#: Never part of the routine, whatever a delegation says.
NEVER_IN_ROUTINE: frozenset[str] = frozenset({"merge", "delete_branch", "workflows", "protected_branch"})


def plan_issue_to_pr(
    store: SQLiteStore,
    principal_id: str,
    *,
    repository: str,
    work_branch: str,
    delegation_id: str | None = None,
    http: GitHubHttp | None = None,
) -> dict[str, Any]:
    """Which steps would run unprompted, and which would ask the owner."""
    service = DelegationService(store, principal_id)
    delegation: dict[str, Any] | None = None
    problems: list[str] = []
    if delegation_id:
        try:
            delegation = service.get(delegation_id)
        except DelegationError as exc:
            problems.append(exc.reason)
        else:
            if str(delegation["repository"]).lower() != repository.lower():
                problems.append("delegation_other_repository")
            problems.extend(service.revalidate(delegation, http=http))
    usable = delegation if delegation is not None and not problems else None
    steps = []
    for step in ISSUE_TO_PR_STEPS:
        if step.operation == "read":
            decision = "runs"
        elif usable is not None and service.covering(
            repository, step.operation, work_branch, delegation_id=str(usable["delegation_id"])
        ):
            decision = "runs_under_delegation"
        else:
            decision = "asks"
        steps.append({"step": step.step, "label": step.label, "operation": step.operation, "decision": decision})
    return {
        "repository": repository,
        "work_branch": work_branch,
        "delegation_id": delegation_id,
        "delegation_problems": problems,
        "steps": steps,
        "never": sorted(NEVER_IN_ROUTINE),
        "blocked_needs_owner": bool(delegation_id) and bool(problems),
    }
