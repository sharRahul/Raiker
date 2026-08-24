# Threat model — project assignment (`project_assignment_runtime`)

`project_assignment_runtime` is the capability behind the `assign_session_project`
tool. It is in [`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py), so
**approving really moves the conversation**.

It is the lowest-consequence capability in the relay set, and it is documented
here for the same reason as the others: the step-up asks for an acknowledgement,
and an acknowledgement with nothing behind it is weaker than one with a page.

## What the capability does

`raiker/runtime/executors/tier1_tasks.py` → `ProjectAssignmentExecutor` calls
`DashboardService.set_session_project`, moving **the conversation the approval
came from** into a named project. A project is an organizing scope: the move
grants nothing, changes no gate, and is reversed in **Projects**.

## Assets

| Asset | Why it matters |
|---|---|
| Project instructions | They are always-on context for every session in the project |
| Project attachments | They are shared across the project's sessions |
| The conversation's own scope | Moving it changes which standing context it inherits |

The consequence worth naming: a project carries owner-authored instructions and
shared attachments, so moving a conversation into one **changes the context every
later turn in that conversation is given**. That is why it is an approval rather
than a silent write.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A model names someone else's conversation | The session is **never a model argument**. It is read from `action.origin_session_id`, which the relay carries across from the approval row, so the conversation moved is the one the owner saw named in the decision | `tier1_tasks.py` |
| A move is used to pull privileged standing context into an agent-controlled chat | The move is an approval the owner reads, and the notice states that a project is an organizing scope that grants nothing and changes no gate | `raiker/control/dashboard.py` |
| A cross-account move | `set_session_project` is human-only and account-scoped, and the principal here is the approving human | `raiker/control/dashboard.py` |
| A move to a project that does not exist | `set_session_project` returns a reason code and the executor fails closed without moving anything | `tier1_tasks.py` |
| The project id drifts after approval | Arguments-hash check in the relay | `tier1_approval.py` |

## Residual risk, stated plainly

- **The move is not itself checkpointed.** It is reversed by moving the
  conversation back in **Projects**, not by a rewind.
- **Project instructions are not re-approved on the move.** Instructions the
  owner wrote for the project apply to the moved conversation from its next turn.
  They are owner records rather than repository files
  ([why](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#37-project-instructions-are-owner-records-not-repository-files)),
  so nothing untrusted enters this way — but the context does change.

## Evidence

- `raiker/runtime/executors/tier1_tasks.py`, `raiker/control/dashboard.py`
- [`approval-execution-relay.md`](approval-execution-relay.md)
