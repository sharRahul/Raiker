"""Compatibility backlog #23 — a delegating parent could not say where a child runs.

BUG-220 gave a parent ownership of its children's terminal states: it parks as
`waiting_for_children` and settles when the last one lands. What it could not do
is say *how* a child should work. Every task cycle ran with Chat's standing
instructions, so a child whose job is "read this repository, make the change, run
the tests" was given the assistant's working method for it. Cowork's Dispatch
routes each piece of a brief to the surface it belongs on; Raiker already has both
surfaces under one governed turn contract, so this is scheduling rather than a new
execution path.

What has to hold:

* **A task carries a surface**, and it is the same set a composer's own surface is
  validated against — a task cannot name a working method a turn does not have.
* **The cycle runs on it.** The scheduler's prompt says so, which is what selects
  the standing instructions.
* **A Build task needs a project**, because Build's method is a repository it can
  read. Without one it is refused with a stated reason rather than accepted and
  quietly run as Chat.
* **A delegating turn's parent is derived, never supplied.** A cycle runs in its
  task's own thread, so the running task is a fact the broker already trusts;
  taking a `parent_task_id` from a tool call would let one turn attach work to
  somebody else's tree.
* **Nothing else changes.** Same runtime, same tools, same gate, same approvals —
  and the parent still owns the child's terminal state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import PROMPT_SURFACES, ContractValidationError, TaskRecord
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

_OWNER = "principal_owner"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _project(store: SQLiteStore, workspace: Path) -> str:
    result = DashboardService(workspace).create_project("Repo", _OWNER)
    assert result.ok, result.reason_code
    return str(result.data["project_id"])


class TestATaskCarriesItsWorkingMethod:
    def test_the_default_is_chat(self, workspace: Path) -> None:
        task = DashboardService(workspace).create_task(
            title="Read the news", objective="Summarise it",
            user_id=None, principal_id=_OWNER,
        )
        assert task.surface == "chat"

    def test_a_build_task_records_build(self, workspace: Path, store: SQLiteStore) -> None:
        project_id = _project(store, workspace)
        task = DashboardService(workspace).create_task(
            title="Fix the failing test", objective="Make it pass",
            user_id=None, principal_id=_OWNER,
            project_id=project_id, surface="build",
        )
        assert task.surface == "build"
        assert store.load_task(task.task_id).surface == "build"  # type: ignore[union-attr]

    def test_it_is_the_same_set_a_composer_is_validated_against(self) -> None:
        assert {"chat", "build"} == PROMPT_SURFACES
        with pytest.raises(ContractValidationError):
            TaskRecord(
                task_id="task_1", session_id="s", title="t", objective="o",
                status="queued", created_at="x", updated_at="x", surface="dispatch",
            )

    def test_an_unknown_surface_is_refused_with_a_stated_reason(
        self, workspace: Path
    ) -> None:
        with pytest.raises(ValueError) as raised:
            DashboardService(workspace).create_task(
                title="t", objective="o", user_id=None, principal_id=_OWNER,
                surface="dispatch",
            )
        assert "invalid_surface" in str(raised.value)


class TestBuildNeedsARepository:
    def test_a_build_task_with_no_project_is_refused(self, workspace: Path) -> None:
        """Build's method is a repository it can read. Without one it would be
        Chat wearing the wrong standing instructions."""
        with pytest.raises(ValueError) as raised:
            DashboardService(workspace).create_task(
                title="Fix it", objective="Make it pass",
                user_id=None, principal_id=_OWNER, surface="build",
            )
        assert str(raised.value) == "build_task_requires_project"

    def test_a_chat_task_needs_nothing(self, workspace: Path) -> None:
        task = DashboardService(workspace).create_task(
            title="Think about it", objective="And say what you think",
            user_id=None, principal_id=_OWNER,
        )
        assert task.project_id is None
        assert task.surface == "chat"


class TestTheCycleRunsOnIt:
    def test_the_scheduler_sends_the_task_s_surface(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """The prompt's `surface` is what selects the standing instructions, so
        this is the whole difference between a Build task and a Chat one."""
        from raiker.runtime.orchestrator import _system_messages

        chat = _system_messages("chat")
        build = _system_messages("build")
        assert len(build) == len(chat) + 1

        project_id = _project(store, workspace)
        task = DashboardService(workspace).create_task(
            title="Fix the failing test", objective="Make it pass",
            user_id=None, principal_id=_OWNER,
            project_id=project_id, surface="build",
        )
        record = store.load_task(task.task_id)
        assert record is not None
        # What the scheduler puts in the envelope, from the row it claimed.
        assert record.surface == "build"


class TestADelegatingTurnsParentIsDerived:
    def test_a_task_created_inside_a_task_thread_becomes_its_child(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        parent = DashboardService(workspace).create_task(
            title="Ship the fix", objective="End to end",
            user_id=None, principal_id=_OWNER,
        )
        assert parent.thread_session_id
        found = store.load_task_for_thread_session(parent.thread_session_id)
        assert found is not None
        assert found.task_id == parent.task_id

    def test_a_session_that_is_not_a_task_thread_has_no_parent(
        self, store: SQLiteStore, workspace: Path
    ) -> None:
        store.create_session("sess_ordinary_chat", str(workspace), title="Chat")
        assert store.load_task_for_thread_session("sess_ordinary_chat") is None

    def test_the_broker_derives_the_parent_and_inherits_its_project(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.tools.broker import ToolExecutionContext

        project_id = _project(store, workspace)
        parent = DashboardService(workspace).create_task(
            title="Ship the fix", objective="End to end",
            user_id=None, principal_id=_OWNER, project_id=project_id,
        )
        broker = _broker(workspace, store)
        context = ToolExecutionContext(
            session_id=str(parent.thread_session_id),
            turn_id="turn_1",
            acting_principal_id=_OWNER,
            owner_principal_id=_OWNER,
            verified_identity=None,  # type: ignore[arg-type]
        )
        result = broker._create_task(
            {"title": "Run the tests", "surface": "build"}, context
        )

        assert result["status"] == "success", result
        assert result["parent_task_id"] == parent.task_id
        assert result["surface"] == "build"
        child = store.load_task(str(result["task_id"]))
        assert child is not None
        # The repository the brief is about, not one the model named.
        assert child.project_id == project_id

    def test_a_turn_outside_a_task_thread_creates_top_level_work(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.tools.broker import ToolExecutionContext

        store.create_session("sess_ordinary_chat", str(workspace), title="Chat")
        broker = _broker(workspace, store)
        result = broker._create_task(
            {"title": "Remember the milk"},
            ToolExecutionContext(
                session_id="sess_ordinary_chat",
                turn_id="turn_1",
                acting_principal_id=_OWNER,
                owner_principal_id=_OWNER,
                verified_identity=None,  # type: ignore[arg-type]
            ),
        )
        assert result["status"] == "success", result
        assert result["parent_task_id"] is None
        assert result["surface"] == "chat"


class TestTheParentStillOwnsTheChild:
    def test_a_parent_with_an_unfinished_build_child_parks(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """Routing by surface is scheduling, not a second execution path: BUG-220's
        ownership is untouched by it."""
        project_id = _project(store, workspace)
        service = DashboardService(workspace)
        parent = service.create_task(
            title="Ship the fix", objective="End to end",
            user_id=None, principal_id=_OWNER, project_id=project_id,
        )
        service.create_task(
            title="Change and test", objective="Make it pass",
            user_id=None, principal_id=_OWNER,
            project_id=project_id, parent_task_id=parent.task_id, surface="build",
        )
        manager = TaskManager(store, EventLogWriter(store))

        manager.complete_task(parent.task_id, "my own part is done")

        held = store.load_task(parent.task_id)
        assert held is not None
        assert held.status == "waiting_for_children"


def _broker(workspace: Path, store: SQLiteStore) -> Any:
    from raiker.policy.config import StaticPolicyConfig
    from raiker.policy.engine import PolicyEngine
    from raiker.tools.broker import ToolBroker

    return ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=EventLogWriter(store),
        principal_id=_OWNER,
    )
