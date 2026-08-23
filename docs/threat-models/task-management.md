# Threat model — task creation (`task_management_runtime`)

`task_management_runtime` is the capability behind the `create_task` tool. It is
in [`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py), so **approving
a proposed task really creates the row**.

The reason this needs a threat model despite being a "local row" is the second
order effect: a task is **work that runs later**. Each cycle of a task is one
governed turn, so creating a task is asking the runtime to raise turns on the
owner's behalf at a time the owner is not present.

## What the capability does

`raiker/runtime/executors/tier1_tasks.py` → `TaskManagementExecutor` calls the
same `DashboardService.create_task` entry point the **Tasks → Plan work** form
uses, so an agent-proposed task and a hand-typed task are the same row with the
same scheduling and the same stop control. It is created with
`start_immediately=False`.

## Assets

| Asset | Why it matters |
|---|---|
| The task's objective text | It becomes the prompt of every later cycle |
| The schedule / recurrence | It decides how often unattended turns are raised |
| The owner's attention | A task that runs while nobody is watching is the case approvals were built for |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| An agent schedules recurring work the owner never sanctioned | The capability gate, a default-`ask` decision mode, and an approval whose preview names the task; the approval notice states in plain words that approving creates the row and that nothing else runs until the task itself does | `raiker/control/dashboard.py` |
| A created task escalates its own authority | It cannot. Every cycle is an ordinary governed turn: same gates, same decision modes, same approvals. A task inherits no standing permission from having been approved once | `raiker/tasks/manager.py` |
| A task runs unattended and silently self-approves | An unattended cycle that needs a decision **parks** as `task_blocked` with the reason and a link to the decision; where the posture is `dont_ask` it records `denied_no_one_to_ask` rather than proceeding | `raiker/runtime/authority/router.py` |
| A malformed proposal creates a row that cannot run | The executor validates before creating: `title` is required and bounded at 500 characters; `description`, `scheduled_at`, `reminder_at`, `recurrence` and `project_id` must be strings; an absent description falls back to the title so a contract-required `objective` is never empty | `tier1_tasks.py` |
| Task instructions leak into runtime artifacts | Artifacts carry the task id and a receipt (kind, title, href, label) — never the objective text | `tier1_tasks.py` |
| A task is created under another user | `user_id` and `principal_id` come from the acting principal, never from a model argument | `tier1_tasks.py` |
| A runaway task consumes the machine | Tasks are stoppable at a safe boundary from **Tasks**; `raiker-app pause` stops starting new background work while letting approved work finish | `raiker/app/` |

## Residual risk, stated plainly

- **The task title is shown to the owner; the objective is what runs.** Where a
  proposal supplies both, the approval preview names the task. Read the objective
  in Tasks before letting a recurring task run unattended.
- **Cadences are coarse.** `continuous`, `hourly`, `daily` and `weekly` only —
  there is no time-of-day, cron expression or timezone binding, so "daily" is
  relative to the host's own clock and a closed laptop is a missed cadence,
  recorded as missed rather than silently caught up.
- **Nothing owns a set of delegated child tasks.** Tasks nest, but there is no
  parent agent that tracks a set to completion (BUG-220). A proposal that creates
  several tasks creates several independent rows.

## Evidence

- `raiker/runtime/executors/tier1_tasks.py`, `raiker/tasks/manager.py`
- [`../RUNTIME_ORCHESTRATION_SPEC.md`](../RUNTIME_ORCHESTRATION_SPEC.md)
- [`scheduled-routines.md`](scheduled-routines.md) for the scheduling capability
- [`approval-execution-relay.md`](approval-execution-relay.md)
