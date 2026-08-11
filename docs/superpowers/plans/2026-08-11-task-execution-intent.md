# Task Execution Intent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make approval create a proposed task without scheduling a run, while preserving immediate execution for an explicit human “create and run” action.

**Architecture:** `DashboardService.create_task` accepts explicit execution intent. Model and approval-relay callers pass `start_immediately=False`; the authenticated human create endpoint defaults to current immediate behavior. A separate atomic “Run now” operation sets the schedule and wakes the resident scheduler.

**Tech Stack:** Python task service/store/scheduler, FastAPI, Svelte Tasks UI, pytest, Vitest.

## Global Constraints

- Approval authorizes creation only; it must never imply execution.
- “Run now” must be owner-scoped, idempotent for already-due tasks, and rejected for terminal or foreign tasks.
- Scheduled tasks with explicit times and recurring tasks retain their existing behavior.

---

### Task 1: Preserve an unscheduled model-created task (BUG-64)

**Files:**
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/tools/broker.py`
- Modify: `raiker/runtime/executors/tier1_tasks.py`
- Modify: `tests/test_bug_62_task_approval_executes.py`
- Modify: `tests/test_task_scheduler.py`

- [ ] Add a failing approval test asserting the approved task exists with `scheduled_at is None`, remains pending after `TaskScheduler.run_due()`, and produces no new model turn.

```python
approved = approve_create_task(client, proposal_id)
task = client.get(f"/api/tasks/{approved['task_id']}", headers=headers).json()
assert task["scheduled_at"] is None
assert asyncio.run(TaskScheduler(workspace).run_due()) == 0
```

- [ ] Run the focused tests and verify the task currently receives `utc_now()`.
- [ ] Add keyword-only `start_immediately: bool = True` to `DashboardService.create_task`; set `scheduled_at=utc_now()` only when the timestamp is absent and the flag is true.
- [ ] Pass `start_immediately=False` from both `ToolBroker._create_task` and `TaskManagementExecutor`. Leave the authenticated human API default unchanged.
- [ ] Update task-created audit payloads to record `execution_intent` as `run_now`, `scheduled`, or `awaiting_user`.
- [ ] Run the focused tests and verify they pass.

### Task 2: Add an explicit, atomic Run now operation

**Files:**
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/tasks/manager.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/routes_dashboard.py`
- Modify: `raiker/api/app.py`
- Modify: `tests/test_api_dashboard.py`
- Modify: `tests/test_scheduler_wakeup.py`

- [ ] Add failing tests for owner success, foreign-owner 404, terminal-task conflict, repeated Run now idempotence, and immediate scheduler wakeup.
- [ ] Run `python -m pytest tests/test_api_dashboard.py tests/test_scheduler_wakeup.py -q` and verify failure.
- [ ] Add a compare-and-update store method that sets `scheduled_at=utc_now()` only for an owner-visible nonterminal task with no earlier schedule.
- [ ] Add `TaskManager.run_now` and `DashboardService.run_task_now`, emitting `task_run_requested` once when state changes.
- [ ] Add `POST /api/tasks/{task_id}/run`, authenticated with the same owner scope as task reads. Signal the existing `SchedulerWakeup` after success.
- [ ] Return the canonical task view and use 404/409 reason codes consistent with adjacent task routes.
- [ ] Run the focused tests and verify they pass.

### Task 3: Add the Tasks UI control

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/TasksView.svelte`
- Modify: `apps/web/src/lib/views/TasksView.test.ts`

- [ ] Add a failing component test asserting an unscheduled pending task shows “Ready when you run it” and a `Run now` button, while scheduled, active, terminal, and foreign-unavailable tasks do not.
- [ ] Add a failing interaction test asserting one click calls the run endpoint once, disables during the request, announces success, and refreshes the row.
- [ ] Run `npm test -- --run src/lib/views/TasksView.test.ts` from `apps/web` and verify failure.
- [ ] Add the typed API method and implement the button using existing task button, focus, toast, and error styles.
- [ ] Keep Stop/Resume controls semantically separate from Run now.
- [ ] Run the focused component test, `npm run check`, and `npm run lint`; verify all pass.
