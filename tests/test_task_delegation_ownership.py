"""BUG-220 — a delegating task owns its children's terminal states.

``parent_task_id`` recorded the structure and nothing owned it, so a task that
split its work into children reported ``completed`` the moment its own run
ended — while a child sat parked on an approval. That is a false completion: it
tells the owner the work is finished and removes the row from everything that
counts unfinished work.

What is pinned here is the ownership only. Nothing flows the other way: a child
carries its own approvals, because a parent's decision standing in for its
children's is exactly what the per-turn capability envelope exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def manager(store: SQLiteStore) -> TaskManager:
    return TaskManager(store, EventLogWriter(store))


@pytest.fixture
def session_id(store: SQLiteStore) -> str:
    sid = new_id("sess_")
    store.create_session(sid, str(store.paths.workspace_root))
    return sid


def _parent_with_children(
    manager: TaskManager, session_id: str, count: int = 2
) -> tuple[str, list[str]]:
    parent = manager.create_task(
        session_id=session_id, title="Ship the release", objective="Split and delegate."
    )
    children = [
        manager.create_task(
            session_id=session_id,
            title=f"Child {index}",
            objective="Do one part.",
            parent_task_id=parent.task_id,
        ).task_id
        for index in range(count)
    ]
    return parent.task_id, children


def test_a_parent_does_not_report_done_over_an_unfinished_child(
    manager: TaskManager, session_id: str
) -> None:
    parent_id, children = _parent_with_children(manager, session_id)
    manager.complete_task(children[0], "First part done.")

    manager.complete_task(parent_id, "My own run finished.")

    parked = manager.get_task(parent_id)
    assert parked is not None
    assert parked.status == "waiting_for_children"
    # Unfinished work carries no completion stamp, exactly as a run parked on an
    # approval does not.
    assert parked.completed_at is None


def test_the_last_child_landing_completes_the_parent(
    manager: TaskManager, session_id: str
) -> None:
    parent_id, children = _parent_with_children(manager, session_id)
    manager.complete_task(children[0], "First part done.")
    manager.complete_task(parent_id, "My own run finished.")
    assert (task := manager.get_task(parent_id)) is not None and task.status == "waiting_for_children"

    manager.complete_task(children[1], "Second part done.")

    settled = manager.get_task(parent_id)
    assert settled is not None
    assert settled.status == "completed"
    assert settled.summary == "All 2 delegated tasks completed."


def test_a_failed_child_fails_the_parent_that_delegated_to_it(
    manager: TaskManager, session_id: str
) -> None:
    """A brief is not finished because most of it worked.

    Reporting the parent as completed with a failed child would put the failure
    one level down from where the owner is looking.
    """
    parent_id, children = _parent_with_children(manager, session_id)
    manager.complete_task(parent_id, "My own run finished.")
    manager.complete_task(children[0], "First part done.")
    manager.fail_task(children[1], "Could not reach the registry.")

    settled = manager.get_task(parent_id)
    assert settled is not None
    assert settled.status == "failed"
    assert settled.summary == "1 of 2 delegated tasks did not complete."


def test_a_cancelled_child_counts_as_not_completed(
    manager: TaskManager, session_id: str
) -> None:
    parent_id, children = _parent_with_children(manager, session_id, count=1)
    manager.complete_task(parent_id, "My own run finished.")
    manager.cancel_task(children[0], "Owner stopped it.")

    settled = manager.get_task(parent_id)
    assert settled is not None
    assert settled.status == "failed"


def test_a_childless_task_still_completes_immediately(
    manager: TaskManager, session_id: str
) -> None:
    """The common case is not slowed down by the uncommon one."""
    task = manager.create_task(session_id=session_id, title="Solo", objective="No children.")
    manager.complete_task(task.task_id, "Done.")

    finished = manager.get_task(task.task_id)
    assert finished is not None
    assert finished.status == "completed"
    assert finished.completed_at is not None


def test_a_parent_that_already_finished_is_not_reopened_by_a_late_child(
    manager: TaskManager, session_id: str
) -> None:
    """A terminal state that can be walked back is not one a record can rely on."""
    parent_id, children = _parent_with_children(manager, session_id, count=1)
    manager.complete_task(children[0], "Part done.")
    manager.complete_task(parent_id, "All done.")
    assert (task := manager.get_task(parent_id)) is not None and task.status == "completed"

    late = manager.create_task(
        session_id=session_id, title="Late", objective="Arrived after.", parent_task_id=parent_id
    )
    manager.fail_task(late.task_id, "Too late to matter.")

    unchanged = manager.get_task(parent_id)
    assert unchanged is not None
    assert unchanged.status == "completed"


def test_the_hold_is_recorded_as_its_own_event(
    manager: TaskManager, store: SQLiteStore, session_id: str
) -> None:
    parent_id, _children = _parent_with_children(manager, session_id)
    manager.complete_task(parent_id, "My own run finished.")

    kinds = [
        str(row["event_type"])
        for row in store.list_event_index(session_id=session_id, limit=50)
    ]
    assert "task_waiting_for_children" in kinds
    assert "task_completed" not in kinds


def test_a_grandparent_settles_when_the_whole_tree_lands(
    manager: TaskManager, session_id: str
) -> None:
    grandparent = manager.create_task(
        session_id=session_id, title="Programme", objective="Own two levels."
    )
    parent = manager.create_task(
        session_id=session_id, title="Workstream", objective="Own one level.",
        parent_task_id=grandparent.task_id,
    )
    child = manager.create_task(
        session_id=session_id, title="Leaf", objective="Do the work.",
        parent_task_id=parent.task_id,
    )

    manager.complete_task(grandparent.task_id, "Brief written.")
    manager.complete_task(parent.task_id, "Split done.")
    manager.complete_task(child.task_id, "Work done.")

    for task_id in (child.task_id, parent.task_id, grandparent.task_id):
        settled = manager.get_task(task_id)
        assert settled is not None and settled.status == "completed", task_id
