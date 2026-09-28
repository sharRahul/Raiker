"""GEP-02 — the stop switch stops everything in progress, not only the task list.

The owner's decision, 2026-09-27: Stop is for *all* the current chat, response,
Build workflow, routine or task being performed, whether or not it leaves the
machine. The switch used to count and cancel tasks only, so the turn an owner
was watching — which is not a task — was the one thing it could not reach.

These tests pin:

- a running turn is listed while it runs and unlisted however it ends;
- ``GET /api/work-in-flight`` counts that turn, and ``POST /api/stop-all``
  stops it through the same turn control the conversation's Stop button writes,
  so it ends ``stopped`` at a safe boundary rather than being force-killed;
- the same call cancels every active task, in every conversation, not only one;
- it stays human-only and owner-scoped;
- a turn that had already finished is not stopped retroactively, and a stop
  written for it cannot end the *next* turn.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import TaskRecord, UserMetadata
from raiker.models.contracts import ModelResponse
from raiker.runtime.live_turns import live_turn, live_turns
from raiker.storage.sqlite import SQLiteStore
from tests.test_turn_resume_after_approval import _envelope, _event_types, _orchestrator
from tests.test_turn_stop_and_steer import ControllingRouter, _read_call, _run

_OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "stop_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session(_OWNER)
    return {"Authorization": f"Bearer {raw}"}


class TestTheRegistry:
    def test_a_turn_is_listed_only_while_it_runs(self, workspace: Path) -> None:
        with live_turn(workspace, "sess_a", "turn_a", _OWNER) as turn:
            assert live_turns(workspace) == [turn]
        assert live_turns(workspace) == []

    def test_a_turn_that_raises_is_still_unlisted(self, workspace: Path) -> None:
        with pytest.raises(RuntimeError), live_turn(workspace, "sess_a", "turn_a", _OWNER):
            raise RuntimeError("boom")
        assert live_turns(workspace) == []

    def test_another_instance_does_not_see_this_ones_turns(
        self, workspace: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "other_ws"
        other.mkdir()
        with live_turn(workspace, "sess_a", "turn_a", _OWNER):
            assert live_turns(other) == []

    def test_the_agent_loop_lists_itself_and_leaves(self, workspace: Path) -> None:
        envelope = _envelope("hello")
        seen: list[list[str]] = []
        router = ControllingRouter(
            [ModelResponse(text="Hi.")],
            on_call=lambda _i: seen.append([t.session_id for t in live_turns(workspace)]),
        )
        orchestrator = _orchestrator(workspace, router)
        final = _run(orchestrator, envelope)[-1].response
        assert final is not None and final.status == "completed"
        assert seen == [[envelope.session_id]]
        assert live_turns(workspace) == []


class TestStopAll:
    def test_stop_all_reaches_the_turn_being_written(self, workspace: Path) -> None:
        """No task is running — the turn alone is what the switch must see."""
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        # In production the envelope names the signed-in principal
        # (`owner_user_metadata`); the harness default is a placeholder user.
        envelope = replace(_envelope("summarise the readme"), user=UserMetadata(id=_OWNER))
        (workspace / "README.md").write_text("hello\n", encoding="utf-8")
        counted: list[dict[str, object]] = []
        stopped: list[dict[str, object]] = []

        def owner_presses_the_switch(call_index: int) -> None:
            if call_index != 0:
                return
            counted.append(client.get("/api/work-in-flight", headers=headers).json())
            response = client.post("/api/stop-all", headers=headers)
            assert response.status_code == 200, response.text
            stopped.append(response.json())

        router = ControllingRouter(
            [
                ModelResponse(text="Reading the file.", tool_calls=[_read_call()]),
                ModelResponse(text="This second answer must never be produced."),
            ],
            on_call=owner_presses_the_switch,
        )
        orchestrator = _orchestrator(workspace, router)
        final = _run(orchestrator, envelope)[-1].response

        assert counted[0]["turns"] == 1
        assert counted[0]["turn_sessions"] == [envelope.session_id]
        assert stopped[0]["turns"] == [
            {"session_id": envelope.session_id, "turn_id": envelope.turn_id}
        ]
        assert final is not None
        assert final.status == "stopped"
        assert router.calls == 1
        assert "turn_stopped" in _event_types(orchestrator, envelope.session_id)

    def test_stop_all_cancels_tasks_in_every_conversation(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        store = SQLiteStore(workspace)
        user_id = store.principal_user_id(_OWNER)
        for index, state in enumerate(("running", "queued", "completed")):
            session_id = f"sess_{index}"
            store.create_session(session_id, str(workspace), user_id=user_id)
            store.insert_task(
                TaskRecord(
                    task_id=f"task_{index}",
                    session_id=session_id,
                    title=f"task {index}",
                    objective="stand in for a routine",
                    status=state,
                    created_at="2026-09-27T00:00:00Z",
                    updated_at="2026-09-27T00:00:00Z",
                )
            )

        counted = client.get("/api/work-in-flight", headers=headers).json()
        assert counted["tasks"] == 2

        result = client.post("/api/stop-all", headers=headers).json()
        assert sorted(item["task_id"] for item in result["tasks"]) == ["task_0", "task_1"]
        assert result["turns"] == []
        assert result["failed"] == []

    def test_nothing_running_is_answered_with_nothing(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        counted = client.get("/api/work-in-flight", headers=headers).json()
        assert counted == {"tasks": 0, "turns": 0, "commands": 0, "turn_sessions": []}
        result = client.post("/api/stop-all", headers=headers).json()
        assert result["tasks"] == result["turns"] == result["commands"] == []

    def test_a_finished_turn_is_not_stopped_and_its_next_turn_runs(
        self, workspace: Path
    ) -> None:
        """Only live turns are written a stop, so no stop is left waiting."""
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        first = _envelope("one")
        _run(_orchestrator(workspace, ControllingRouter(
            [ModelResponse(text="Done.")], on_call=lambda _i: None
        )), first)

        client.post("/api/stop-all", headers=headers)

        second = replace(first, turn_id="turn_next", request_id="req_next")
        final = _run(_orchestrator(workspace, ControllingRouter(
            [ModelResponse(text="Second answer.")], on_call=lambda _i: None
        )), second)[-1].response
        assert final is not None and final.status == "completed"

    def test_another_owners_turn_is_not_reached(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        with live_turn(workspace, "sess_someone_else", "turn_x", "principal_stranger"):
            counted = client.get("/api/work-in-flight", headers=headers).json()
            result = client.post("/api/stop-all", headers=headers).json()
        assert counted["turns"] == 0
        assert result["turns"] == []

    def test_it_needs_a_signed_in_owner(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        assert client.post("/api/stop-all").status_code in {401, 403}
        assert client.get("/api/work-in-flight").status_code in {401, 403}


class TestATurnIsOnePieceOfWork:
    """Found live 2026-09-28: one stopped answer was reported as two things.

    Every Chat turn runs under an internal governance task (``parent_turn_id``
    set) that the task list hides because it *is* the turn. The first stop-all
    cancelled it as a task and stopped the turn as a turn, and said "1 answer
    being written and 1 task".
    """

    def test_a_turns_own_task_is_counted_and_reported_as_the_turn(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        headers = _headers(workspace)
        store = SQLiteStore(workspace)
        store.create_session("sess_turn", str(workspace), user_id=store.principal_user_id(_OWNER))
        store.insert_turn("sess_turn", "turn_live", "write something long")
        store.insert_task(
            TaskRecord(
                task_id="task_turn",
                session_id="sess_turn",
                title="Chat turn",
                objective="Governed chat turn",
                status="running",
                created_at="2026-09-28T00:00:00Z",
                updated_at="2026-09-28T00:00:00Z",
                parent_turn_id="turn_live",
            )
        )
        with live_turn(workspace, "sess_turn", "turn_live", _OWNER):
            counted = client.get("/api/work-in-flight", headers=headers).json()
            result = client.post("/api/stop-all", headers=headers).json()

        assert counted["tasks"] == 0
        assert counted["turns"] == 1
        assert result["tasks"] == []
        assert result["turns"] == [{"session_id": "sess_turn", "turn_id": "turn_live"}]
        # And the governance task was stopped with it — the stream reads it.
        task = store.load_task("task_turn")
        assert task is not None and task.status == "cancelled"
