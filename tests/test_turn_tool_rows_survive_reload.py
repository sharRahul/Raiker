"""Backlog #25 — a reopened turn keeps the record of what it did.

Live, a turn's tool rows arrive on the stream and the client assembles them. A
reload has no stream, so a reopened transcript showed the answer and nothing
about how it was reached — half the record, lost to the surface rather than to
the storage, because ``tool_actions`` had it the whole time.

What matters here is not only that the rows come back, but that they come back
through the same ``raiker.tools.presentation`` function the live path uses, over
arguments the broker had already redacted. That is what makes it impossible for
a reloaded row to say more than the live one did.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def service(tmp_path: Path, store: SQLiteStore) -> DashboardService:
    return DashboardService(tmp_path)


def _turn(store: SQLiteStore) -> tuple[str, str]:
    session_id = new_id("sess_")
    store.create_session(session_id, str(store.paths.workspace_root))
    turn_id = new_id("turn_")
    store.insert_turn(
        session_id=session_id,
        turn_id=turn_id,
        prompt_text="what changed in the readme",
        status="completed",
    )
    return session_id, turn_id


def _record(
    store: SQLiteStore,
    session_id: str,
    turn_id: str,
    tool_name: str,
    arguments: dict[str, object],
    status: str,
) -> str:
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=arguments,
        risk_level="low",
        requires_approval=False,
    )
    store.insert_tool_action(action, session_id, turn_id, status)
    return action.action_id


def test_a_reopened_turn_carries_the_rows_it_showed_live(
    service: DashboardService, store: SQLiteStore
) -> None:
    session_id, turn_id = _turn(store)
    _record(store, session_id, turn_id, "read_file", {"path": "README.md"}, "success")

    detail = service.get_session(session_id, user_id=None)
    assert detail is not None
    rows = detail.turns[0].tool_rows
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "read_file"
    assert rows[0]["status"] == "success"
    # The action phrase is what makes the row worth keeping: "Read file" alone
    # does not tell an owner which file the turn read.
    assert "README.md" in str(rows[0]["action"])


def test_rows_keep_the_order_the_calls_were_proposed_in(
    service: DashboardService, store: SQLiteStore
) -> None:
    session_id, turn_id = _turn(store)
    _record(store, session_id, turn_id, "list_directory", {"path": "docs"}, "success")
    _record(store, session_id, turn_id, "read_file", {"path": "docs/README.md"}, "success")

    detail = service.get_session(session_id, user_id=None)
    assert detail is not None
    assert [row["tool_name"] for row in detail.turns[0].tool_rows] == [
        "list_directory",
        "read_file",
    ]


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("success", "success"),
        ("failed", "failed"),
        ("denied", "denied"),
        ("approval_required", "waiting"),
        ("proposed", "running"),
    ],
)
def test_every_stored_status_reads_as_the_state_the_transcript_uses(
    service: DashboardService, store: SQLiteStore, stored: str, shown: str
) -> None:
    session_id, turn_id = _turn(store)
    _record(store, session_id, turn_id, "read_file", {"path": "README.md"}, stored)

    detail = service.get_session(session_id, user_id=None)
    assert detail is not None
    assert detail.turns[0].tool_rows[0]["status"] == shown


def test_a_turn_with_no_tool_calls_carries_no_rows(
    service: DashboardService, store: SQLiteStore
) -> None:
    session_id, _turn_id = _turn(store)

    detail = service.get_session(session_id, user_id=None)
    assert detail is not None
    assert detail.turns[0].tool_rows == ()


def test_rows_are_scoped_to_their_own_turn(
    service: DashboardService, store: SQLiteStore
) -> None:
    """A row from another turn appearing here would be a false record.

    ``tool_actions`` is keyed by session as well as turn, and reading it by
    session would attach every call the conversation ever made to every turn in
    it.
    """
    session_id, first_turn = _turn(store)
    second_turn = new_id("turn_")
    store.insert_turn(
        session_id=session_id,
        turn_id=second_turn,
        prompt_text="and the licence?",
        status="completed",
    )
    _record(store, session_id, first_turn, "read_file", {"path": "README.md"}, "success")
    _record(store, session_id, second_turn, "read_file", {"path": "LICENSE"}, "success")

    detail = service.get_session(session_id, user_id=None)
    assert detail is not None
    by_turn = {turn.turn_id: turn.tool_rows for turn in detail.turns}
    assert len(by_turn[first_turn]) == 1
    assert "README.md" in str(by_turn[first_turn][0]["action"])
    assert len(by_turn[second_turn]) == 1
    assert "LICENSE" in str(by_turn[second_turn][0]["action"])
