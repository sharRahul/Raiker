# Chat Tasks and Project Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Raiker create tasks/reminders and assign the active chat to a project through governed natural-language chat actions.

**Architecture:** Add two narrow action intents and tool executors that delegate to `DashboardService`; the broker supplies trusted active-session/principal context while model arguments remain untrusted. A small conversation state layer collects missing task details and resolves project ambiguity. The normal transcript receives only human-readable completion receipts.

**Tech Stack:** Python/FastAPI/SQLite/existing tool broker, Svelte 5/TypeScript/Vitest.

## Global Constraints

- Existing `DashboardService.create_task` and `set_session_project` remain the only mutation path.
- The model never provides an arbitrary session id; project assignment targets the active chat session.
- Ask for missing or ambiguous details; never silently select among duplicate projects.
- Existing global approval/decision policy controls action execution; successful chat receipts contain no governance payload.
- An approved task/project action resumes the exact validated action once with stored trusted context; approval never reconstructs model arguments.

## Implementation status (2026-07-26)

The governed tool registry now validates `create_task` and
`assign_session_project`; the broker passes the active session and acting
principal as trusted execution context, so neither can be supplied by a model.
The handlers delegate to the existing `DashboardService` mutation methods.

The planner/clarification state, duplicate-project choice flow, persistent
exactly-once approval resumption, API coverage, and transcript receipts are
still open. Until those steps are complete, the feature must not be presented as
natural-language task/project automation or as an approved action that resumes.

---

### Task 1: Structured intents and clarification state

**Files:**
- Create: `raiker/runtime/chat_actions.py`
- Test: `tests/test_chat_actions.py`

**Interfaces:**
- Produces `TaskDraft`, `ProjectMatch`, and `ChatActionPlanner.plan(text, session_id, projects)`.
- Consumed by the tool executor in Task 2.

- [ ] **Step 1: Write failing planner tests**

```python
def test_task_without_reminder_time_requests_one_follow_up() -> None:
    action = ChatActionPlanner().plan("remind me tomorrow", "sess_1", [])
    assert action.kind == "clarify_task_time"
    assert action.question == "What time tomorrow should I remind you?"

def test_project_match_requires_a_choice_when_names_are_ambiguous() -> None:
    action = ChatActionPlanner().plan("move this chat to launch", "sess_1", [Project("p1", "Launch"), Project("p2", "Launch notes")])
    assert action.kind == "choose_project"
    assert [match.project_id for match in action.matches] == ["p1", "p2"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest --basetemp .pytest_tmp tests/test_chat_actions.py -v`

- [ ] **Step 3: Implement the minimal state model**

```python
@dataclass(frozen=True)
class TaskDraft:
    title: str
    description: str
    scheduled_at: str | None
    reminder_at: str | None
    recurrence: str | None

class ChatActionPlanner:
    def plan(self, text: str, session_id: str, projects: Sequence[ProjectMatch]) -> PlannedChatAction: ...
```

Parse only explicit date/time information with a bounded deterministic parser.
Use case-insensitive exact project name matches before bounded contains matches;
return `choose_project` for more than one match and `project_not_found` for none.

- [ ] **Step 4: Run the planner tests**

Run: `python -m pytest --basetemp .pytest_tmp tests/test_chat_actions.py -v`

- [ ] **Step 5: Commit**

```bash
git add raiker/runtime/chat_actions.py tests/test_chat_actions.py
git commit -m "feat(chat): plan task and project actions"
```

### Task 2: Governed executors and receipts

**Files:**
- Modify: `raiker/models/tool_call_validation.py`
- Modify: `raiker/tools/broker.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/approvals/inbox.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_chat_actions.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- `create_task` accepts `{title, description, scheduled_at?, reminder_at?, recurrence?, project_id?}`.
- `assign_session_project` accepts `{project_id}` and obtains `session_id` solely from trusted broker execution context.
- Completion returns `ChatActionReceipt(kind, title, destination, href)`.
- `resume_local_chat_action(approval_id)` executes the stored action once after approval.

- [ ] **Step 1: Write failing service-delegation tests**

```python
def test_task_action_delegates_to_dashboard_and_returns_a_tasks_receipt(service, owner) -> None:
    receipt = ChatActionExecutor(service, active_session_id="sess_1", principal_id=owner).create_task({"title": "Send report"})
    assert receipt.href == "#/tasks"
    assert "Send report" in receipt.message

def test_project_action_uses_the_broker_session_not_model_arguments(service, owner) -> None:
    receipt = ChatActionExecutor(service, active_session_id="sess_1", principal_id=owner).assign_session_project({"project_id": "p1"})
    assert receipt.session_id == "sess_1"

def test_approved_task_action_resumes_once_from_the_stored_action(client, owner_token) -> None:
    approval = request_task_action(client, owner_token)
    assert resolve_approval(client, approval, owner_token).json()["status"] == "executed"
    assert resolve_approval(client, approval, owner_token).status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest --basetemp .pytest_tmp tests/test_chat_actions.py -v`

- [ ] **Step 3: Register and implement tools**

Add validated tool specifications and extend `ToolBroker.execute` so executor
handlers receive a trusted `ToolExecutionContext(session_id, principal_id)`.
Handlers instantiate the existing dashboard service with that principal, call
its existing methods, and translate only successful results into receipts.
Reuse the normal tool approval/decision path; do not add an HTTP shortcut or
direct SQLite write. Persist an action-resume record for only `create_task` and
`assign_session_project`; approval resolution atomically claims it before calling
the same executor, making retries idempotent.

- [ ] **Step 4: Run backend tests**

Run: `python -m pytest --basetemp .pytest_tmp tests/test_chat_actions.py tests/test_api_dashboard.py -v`

- [ ] **Step 5: Commit**

```bash
git add raiker/models/tool_call_validation.py raiker/tools/broker.py raiker/gateway/agent_gateway.py raiker/control/dashboard.py tests/test_chat_actions.py tests/test_api_dashboard.py
git commit -m "feat(chat): execute governed task and project actions"
```

### Task 3: Conversational chat receipts

**Files:**
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/ChatView.svelte`
- Modify: `apps/web/src/lib/views/ChatView.test.ts`

**Interfaces:**
- Consumes a final response action receipt `{kind, message, href, label}` from Task 2.
- Renders a normal Raiker bubble plus a standard in-app link.

- [ ] **Step 1: Write failing transcript tests**

```ts
expect(screen.getByText(/created task: send report/i)).toBeInTheDocument();
expect(screen.getByRole("link", { name: /review in tasks/i })).toHaveAttribute("href", "#/tasks");
expect(screen.queryByText(/governing this turn|completed/i)).not.toBeInTheDocument();
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm.cmd test -- ChatView`

- [ ] **Step 3: Render only completed action receipts**

Extend the final-response type with optional receipt metadata. Render a compact
link in the Raiker response group only when a receipt exists; clarification and
error replies remain normal message text. Dispatch the existing `raiker:chats-changed`
and `raiker:projects-changed` events after successful mutations.

- [ ] **Step 4: Run web verification**

Run: `npm.cmd test -- ChatView; npm.cmd run check; npm.cmd run build`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/ChatView.svelte apps/web/src/lib/views/ChatView.test.ts
git commit -m "feat(chat): show task and project action receipts"
```
