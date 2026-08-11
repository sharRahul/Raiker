"""BUG-62 — approving a proposed task actually creates it.

`create_task` and `assign_session_project` reached the approval path correctly
(FIXED-98 put them in `approval_required_actions` so they stopped being answered
`unknown_or_denied_tool`), and then stopped there: neither capability was in
`EXECUTABLE_ON_APPROVAL`, so the owner was shown a high-risk decision naming the
task, approved it, and got *"Recorded: approved. The action was NOT executed
(metadata-only)"* with no task anywhere.

These tests cover the wiring that closes it, and its boundaries: the task really
exists afterwards, the sentence the owner reads *before* deciding says so, the
gate is a real off switch, and the conversation a project assignment moves is the
one that proposed it rather than the inbox session that approved it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.approvals.execution import executable_capability
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {raw}"}


def _pending(
    workspace: Path,
    *,
    tool_name: str,
    arguments: dict[str, object],
    approval_id: str = "appr_1",
    action_id: str = "act_1",
    session_id: str = "sess_chat",
) -> str:
    """Insert a pending approval exactly as the broker parks one."""
    store = SQLiteStore(workspace)
    store.create_session(session_id, str(workspace), user_id="owner")
    action = ToolAction(
        action_id=action_id,
        tool_name=tool_name,
        arguments=arguments,
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(
        action, session_id=session_id, turn_id="turn_a", status="approval_required"
    )
    store.insert_approval(approval_id, action)
    return approval_id


def _resolve(
    client: TestClient, headers: dict[str, str], approval_id: str, *, approve: bool = True
) -> Any:
    return client.post(
        f"/api/approvals/{approval_id}/resolve",
        json={"approve": approve, "reason": "test decision"},
        headers=headers,
    )


class TestApprovedTaskIsCreated:
    def test_approving_create_task_puts_the_task_in_tasks(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(
            workspace,
            tool_name="create_task",
            arguments={"title": "Draft the weekly summary", "description": "one line"},
        )

        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["executes_action"] is True
        assert body["status"] == "executed"
        assert body["execution"]["capability"] == "task_management_runtime"
        assert body["execution"]["receipt"] == {
            "kind": "task",
            "title": "Draft the weekly summary",
            "href": "#/tasks",
            "label": "Review in Tasks",
        }

        listed = client.get("/api/tasks", headers=headers)
        assert listed.status_code == 200, listed.text
        created = next(
            task for task in listed.json() if task["title"] == "Draft the weekly summary"
        )
        # BUG-64: approving creation creates only the work object. It does not
        # also schedule a turn the owner never asked to run.
        assert created["scheduled_at"] is None

    def test_owner_can_explicitly_run_an_approved_unscheduled_task(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, tool_name="create_task", arguments={"title": "Run deliberately"})
        assert _resolve(client, headers, "appr_1").status_code == 200
        task = next(
            item
            for item in client.get("/api/tasks", headers=headers).json()
            if item["title"] == "Run deliberately"
        )

        started = client.post(f"/api/tasks/{task['task_id']}/run", headers=headers)

        assert started.status_code == 200, started.text
        assert started.json()["scheduled_at"] is not None
        duplicate = client.post(f"/api/tasks/{task['task_id']}/run", headers=headers)
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["reason_code"] == "task_already_scheduled"

    def test_the_resumed_turn_is_told_the_task_really_exists(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        """The model must be able to tell 'created' from 'recorded'."""
        _pending(workspace, tool_name="create_task", arguments={"title": "Ship the report"})

        body = _resolve(client, headers, "appr_1").json()

        store = SQLiteStore(workspace)
        approval = store.load_approval("appr_1")
        assert approval is not None
        assert approval["status"] == "executed"
        assert body["resume"] is not None

    def test_rejecting_creates_nothing(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, tool_name="create_task", arguments={"title": "Never created"})

        resp = _resolve(client, headers, "appr_1", approve=False)

        assert resp.status_code == 200, resp.text
        assert resp.json()["executes_action"] is False
        titles = [t["title"] for t in client.get("/api/tasks", headers=headers).json()]
        assert "Never created" not in titles

    def test_a_titleless_task_fails_closed(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, tool_name="create_task", arguments={"title": "   "})

        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code != 200
        assert SQLiteStore(workspace).load_approval("appr_1")["status"] != "executed"  # type: ignore[index]


class TestOwnerControl:
    def test_the_owner_is_told_before_deciding_that_approving_creates_it(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(workspace, tool_name="create_task", arguments={"title": "Weekly summary"})

        detail = client.get("/api/approvals/appr_1", headers=headers)

        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["executes_on_approval"] is True
        assert "creates the task" in body["metadata_only_notice"]
        assert "NOT execute" not in body["metadata_only_notice"]

    def test_disabling_the_gate_returns_the_approval_to_record_only(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        """The owner's off switch still wins, and the notice says so first."""
        disabled = client.post(
            "/api/capability-gates/task_management_runtime/disable",
            json={"reason": "owner turned this off"},
            headers=headers,
        )
        assert disabled.status_code == 200, disabled.text
        _pending(workspace, tool_name="create_task", arguments={"title": "Not created"})

        detail = client.get("/api/approvals/appr_1", headers=headers).json()
        assert detail["executes_on_approval"] is False
        assert "NOT execute" in detail["metadata_only_notice"]

        body = _resolve(client, headers, "appr_1").json()
        assert body["executes_action"] is False
        titles = [t["title"] for t in client.get("/api/tasks", headers=headers).json()]
        assert "Not created" not in titles


class TestProjectAssignment:
    def test_approving_moves_the_conversation_that_proposed_it(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        """The moved chat is the approval's own session, never the inbox's."""
        created = client.post(
            "/api/projects", json={"name": "Reporting"}, headers=headers
        )
        assert created.status_code in (200, 201), created.text
        project_id = created.json()["project_id"]
        _pending(
            workspace,
            tool_name="assign_session_project",
            arguments={"project_id": project_id},
            session_id="sess_chat",
        )

        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["executes_action"] is True
        assert body["execution"]["capability"] == "project_assignment_runtime"
        assert body["execution"]["receipt"]["title"] == "Reporting"
        session = SQLiteStore(workspace).load_session("sess_chat")
        assert session is not None
        assert session["project_id"] == project_id

    def test_an_unknown_project_fails_closed(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        _pending(
            workspace,
            tool_name="assign_session_project",
            arguments={"project_id": "proj_does_not_exist"},
        )

        resp = _resolve(client, headers, "appr_1")

        assert resp.status_code != 200
        session = SQLiteStore(workspace).load_session("sess_chat")
        assert session is not None
        assert not session["project_id"]


class TestWiringInvariants:
    def test_both_tools_map_onto_a_relayable_capability(self) -> None:
        assert executable_capability("create_task") == "task_management_runtime"
        assert executable_capability("assign_session_project") == "project_assignment_runtime"

    def test_no_executable_capability_lacks_an_executor(self, workspace: Path) -> None:
        """A capability the relay will route into must have something to route into.

        This is BUG-62's own failure mode generalised: two lists that have to
        agree, with nothing holding them together. `EXECUTABLE_ON_APPROVAL`
        promises the owner that approving performs the action; a member with no
        registered executor would answer `execution_unavailable:no_executor`
        after the owner had already been told it would run.
        """
        from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        missing = sorted(EXECUTABLE_ON_APPROVAL - REAL_EXECUTOR_CAPABILITIES)
        assert missing == [], f"relayable capabilities with no executor: {missing}"

    def test_every_real_capability_can_actually_be_turned_on(self) -> None:
        """A capability with an executor and no activation entry cannot be enabled.

        Found while closing BUG-62: `ACTIVATION_REQUIREMENTS` had no entry for
        the new capabilities *or* for `checkpoint_restore_execution`, so the
        Permissions page answered "Activation is blocked. Satisfy the activation
        requirement first." with no requirement to satisfy — a switch the owner
        can see, cannot use, and is given no reason for.
        """
        from raiker.runtime.authority.activation import ACTIVATION_REQUIREMENTS
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        missing = sorted(REAL_EXECUTOR_CAPABILITIES - set(ACTIVATION_REQUIREMENTS))
        assert missing == [], f"capabilities with an executor and no activation entry: {missing}"

    def test_the_broker_states_what_approving_will_do(self, workspace: Path) -> None:
        from raiker.events.writer import EventLogWriter
        from raiker.policy.config import StaticPolicyConfig
        from raiker.policy.engine import PolicyEngine
        from raiker.tools.broker import ToolBroker

        store = SQLiteStore(workspace)
        broker = ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace), store=store),
            writer=EventLogWriter(store),
            store=store,
            principal_id="principal_owner",
        )
        action = ToolAction(
            action_id="act_e",
            tool_name="create_task",
            arguments={"title": "Weekly summary"},
            risk_level="high",
            requires_approval=True,
        )
        effect = broker._expected_effect(action, False)  # noqa: SLF001
        assert effect == (
            "Creates one task in Tasks. It will wait until you run or schedule it."
        )
