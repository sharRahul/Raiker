"""GAP-BUILD B17 / GAP-CHAT C13 — stop or steer a turn that is already running.

`POST /api/interrupts` could cancel a *task*; a live Chat or Build turn is not a
task the owner scheduled, so the one control an autonomous agent most needs —
"stop, this is going the wrong way" — reached nothing the owner was watching.

These tests pin what closes that:

- a stop is honoured at a **safe boundary**, between the last tool batch and the
  next question to the model, never mid-mutation;
- a stopped turn ends as ``stopped`` and keeps the text it had already produced —
  it is not a failure and not an empty answer;
- a steer enters the running turn as the owner's own user message at the same
  boundary, in the order it was typed, and grants nothing;
- controls are consumed, so one stop cannot end two turns and one instruction
  cannot be read twice;
- a control left over from between turns is cleared rather than applied to work
  the owner had not asked for yet;
- the endpoint stays human-only and owner-scoped.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import EVENT_TYPES, RESPONSE_STATUSES
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.storage.sqlite import SQLiteStore
from tests.test_turn_resume_after_approval import (  # reuse the B2 harness verbatim
    ScriptedRouter,
    _envelope,
    _event_types,
    _orchestrator,
)

_OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "control_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class ControllingRouter(ScriptedRouter):
    """A scripted model that acts as the owner pressing a control mid-turn.

    A control the owner leaves *between* turns is deliberately cleared, so a test
    that plants one before the turn starts would prove nothing. This plants it
    the way it really arrives: while the turn is in flight, from the outside.
    """

    def __init__(self, responses, *, on_call) -> None:  # type: ignore[no-untyped-def]
        super().__init__(responses)
        self._on_call = on_call

    def chat(self, provider, model, messages, tools=None):  # type: ignore[no-untyped-def]
        self._on_call(self.calls)
        return super().chat(provider, model, messages, tools)


def _read_call(name: str = "README.md") -> ToolCallProposal:
    return ToolCallProposal(
        call_id=f"call_{name}", tool_name="read_file", arguments={"path": name}
    )


def _run(orchestrator, envelope):  # type: ignore[no-untyped-def]
    async def go():  # type: ignore[no-untyped-def]
        events = []
        async for event in orchestrator._aturn_events(envelope, stream=False):
            events.append(event)
        return events

    return asyncio.run(go())


class TestStopAtASafeBoundary:
    def test_a_stop_ends_the_turn_before_the_next_model_call(self, workspace: Path) -> None:
        envelope = _envelope("summarise the readme")
        (workspace / "README.md").write_text("hello\n", encoding="utf-8")
        store = SQLiteStore(workspace)

        def owner_presses_stop(call_index: int) -> None:
            # Pressed while the model is answering the first time — so the tool
            # call it proposes still runs, and the *second* question is the one
            # that never gets asked.
            if call_index == 0:
                store.request_turn_stop(
                    envelope.session_id, envelope.user.id,
                    reason="user stopped this turn (composer)",
                )

        router = ControllingRouter([
            ModelResponse(text="Reading the file.", tool_calls=[_read_call()]),
            ModelResponse(text="This second answer must never be produced."),
        ], on_call=owner_presses_stop)
        orchestrator = _orchestrator(workspace, router)

        events = _run(orchestrator, envelope)
        final = events[-1].response
        assert final is not None
        assert final.status == "stopped"
        # The model was asked exactly once: the stop was honoured at the boundary
        # before the second question, not after it.
        assert router.calls == 1
        types = _event_types(orchestrator, envelope.session_id)
        assert "turn_stopped" in types

    def test_a_stopped_turn_keeps_what_it_already_said(self, workspace: Path) -> None:
        envelope = _envelope("write something long")
        store = SQLiteStore(workspace)
        router = ControllingRouter(
            [ModelResponse(text="Half of an answer.")],
            on_call=lambda index: store.request_turn_stop(
                envelope.session_id, envelope.user.id, reason="user requested stop"
            ),
        )
        orchestrator = _orchestrator(workspace, router)
        final = _run(orchestrator, envelope)[-1].response
        assert final is not None
        assert final.status == "stopped"
        assert "Half of an answer." in final.message

    def test_stopped_is_a_declared_response_status(self) -> None:
        assert "stopped" in RESPONSE_STATUSES

    def test_both_control_events_are_declared(self) -> None:
        # FIXED-97's rule: an event the runtime emits but never declares kills the
        # turn that tries to emit it.
        assert {"turn_stopped", "turn_steered"} <= EVENT_TYPES

    def test_a_stop_is_consumed_and_does_not_end_the_next_turn(
        self, workspace: Path
    ) -> None:
        first = _envelope("one")
        store = SQLiteStore(workspace)
        stopped_once = {"done": False}

        def stop_the_first_turn(call_index: int) -> None:
            if not stopped_once["done"]:
                stopped_once["done"] = True
                store.request_turn_stop(first.session_id, first.user.id, reason="stop")

        router = ControllingRouter(
            [ModelResponse(text="First."), ModelResponse(text="Second.")],
            on_call=stop_the_first_turn,
        )
        orchestrator = _orchestrator(workspace, router)
        assert _run(orchestrator, first)[-1].response.status == "stopped"

        second = _envelope("two")
        object.__setattr__(second, "session_id", first.session_id)
        assert _run(orchestrator, second)[-1].response.status == "completed"

    def test_a_control_left_between_turns_is_cleared(self, workspace: Path) -> None:
        """A stop that arrived with no turn running must not stop the next one."""
        router = ScriptedRouter([ModelResponse(text="Answered.")])
        orchestrator = _orchestrator(workspace, router)
        envelope = _envelope("hello")
        SQLiteStore(workspace).queue_turn_steer(
            envelope.session_id, envelope.user.id, text="stale instruction"
        )
        final = _run(orchestrator, envelope)[-1].response
        assert final.status == "completed"
        seen = " ".join(
            message.content
            for messages in router.seen_messages
            for message in messages
        )
        assert "stale instruction" not in seen


class TestSteerAtASafeBoundary:
    def test_the_owners_words_enter_the_running_turn_in_order(
        self, workspace: Path
    ) -> None:
        envelope = _envelope("look at the readme")
        (workspace / "README.md").write_text("hello\n", encoding="utf-8")
        store = SQLiteStore(workspace)

        def owner_types_two_corrections(call_index: int) -> None:
            if call_index == 0:
                store.queue_turn_steer(
                    envelope.session_id, envelope.user.id, text="actually use CHANGELOG.md"
                )
                store.queue_turn_steer(
                    envelope.session_id, envelope.user.id, text="and keep it short"
                )

        router = ControllingRouter([
            ModelResponse(text="Reading.", tool_calls=[_read_call()]),
            ModelResponse(text="Done, with the correction applied."),
        ], on_call=owner_types_two_corrections)
        orchestrator = _orchestrator(workspace, router)
        final = _run(orchestrator, envelope)[-1].response
        assert final.status == "completed"
        # The second model call sees both instructions, as user messages, in the
        # order the owner typed them.
        second_call = router.seen_messages[1]
        user_texts = [m.content for m in second_call if m.role == "user"]
        assert user_texts[-2:] == ["actually use CHANGELOG.md", "and keep it short"]
        types = _event_types(orchestrator, envelope.session_id)
        assert types.count("turn_steered") == 2

    def test_a_steer_is_read_once(self, workspace: Path) -> None:
        envelope = _envelope("go")
        (workspace / "README.md").write_text("hello\n", encoding="utf-8")
        store = SQLiteStore(workspace)
        router = ControllingRouter([
            ModelResponse(text="One.", tool_calls=[_read_call()]),
            ModelResponse(text="Two.", tool_calls=[_read_call("README.md")]),
            ModelResponse(text="Three."),
        ], on_call=lambda index: (
            store.queue_turn_steer(envelope.session_id, envelope.user.id, text="one correction")
            if index == 0 else None
        ))
        orchestrator = _orchestrator(workspace, router)
        _run(orchestrator, envelope)
        injected = sum(
            1
            for messages in router.seen_messages
            for message in messages
            if message.role == "user" and message.content == "one correction"
        )
        # It appears in the second call and, as conversation, in the third — but
        # it was appended exactly once.
        assert _event_types(orchestrator, envelope.session_id).count("turn_steered") == 1
        assert injected >= 1

    def test_the_audit_trail_records_the_size_not_the_words(self, workspace: Path) -> None:
        envelope = _envelope("go")
        (workspace / "README.md").write_text("hello\n", encoding="utf-8")
        secret = "do not put this sentence in the audit log"
        store = SQLiteStore(workspace)
        router = ControllingRouter([
            ModelResponse(text="A.", tool_calls=[_read_call()]),
            ModelResponse(text="B."),
        ], on_call=lambda index: (
            store.queue_turn_steer(envelope.session_id, envelope.user.id, text=secret)
            if index == 0 else None
        ))
        orchestrator = _orchestrator(workspace, router)
        _run(orchestrator, envelope)
        log = orchestrator.writer.path_for_session(envelope.session_id).read_text(encoding="utf-8")
        assert secret not in log
        steered = [
            json.loads(line)
            for line in log.splitlines()
            if json.loads(line)["event_type"] == "turn_steered"
        ]
        assert steered[0]["payload"]["steer_chars"] == len(secret)


class TestTurnControlStore:
    def test_steers_queue_and_a_stop_is_recorded(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        assert store.queue_turn_steer("s1", _OWNER, text="first") == 1
        assert store.queue_turn_steer("s1", _OWNER, text="second") == 2
        store.request_turn_stop("s1", _OWNER, reason="stop now")
        control = store.take_turn_control("s1", _OWNER)
        assert control["stop_requested"] is True
        assert control["stop_reason"] == "stop now"
        assert control["steer_texts"] == ["first", "second"]
        # Consumed: a second read finds nothing.
        assert store.take_turn_control("s1", _OWNER)["steer_texts"] == []

    def test_controls_are_scoped_to_one_owner_and_one_conversation(
        self, workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        store.request_turn_stop("s1", _OWNER, reason="stop")
        assert store.take_turn_control("s1", "principal_other")["stop_requested"] is False
        assert store.take_turn_control("s2", _OWNER)["stop_requested"] is False
        assert store.take_turn_control("s1", _OWNER)["stop_requested"] is True


class TestInterruptEndpoint:
    def _client(self, workspace: Path) -> TestClient:
        return TestClient(create_app(workspace))

    def _login(self, workspace: Path) -> dict[str, str]:
        raw, _ = ApiSessionStore(workspace).create_session(_OWNER)
        return {"Authorization": f"Bearer {raw}"}

    def test_a_stop_and_a_steer_reach_the_live_turn(self, workspace: Path) -> None:
        """The governed endpoint, not just the store, is what the composer calls."""
        client = self._client(workspace)
        headers = self._login(workspace)
        store = SQLiteStore(workspace)
        store.create_session("sess_live", str(workspace))

        steered = client.post(
            "/api/interrupts",
            json={
                "session_id": "sess_live",
                "all": True,
                "action_type": "steer",
                "steer_text": "use the changelog instead",
            },
            headers=headers,
        )
        assert steered.status_code == 200, steered.text
        assert steered.json()["turn_control"] == {"action": "steer", "queued": 1}

        stopped = client.post(
            "/api/interrupts",
            json={"session_id": "sess_live", "all": True, "action_type": "cancel"},
            headers=headers,
        )
        assert stopped.status_code == 200
        assert stopped.json()["turn_control"]["action"] == "stop"

        control = store.take_turn_control("sess_live", _OWNER)
        assert control["stop_requested"] is True
        assert control["steer_texts"] == ["use the changelog instead"]

    def test_naming_one_task_does_not_touch_the_live_turn(self, workspace: Path) -> None:
        """`task_id` means "that task"; it must not also stop what is streaming."""
        client = self._client(workspace)
        store = SQLiteStore(workspace)
        store.create_session("sess_task", str(workspace))
        response = client.post(
            "/api/interrupts",
            json={"session_id": "sess_task", "task_id": "task_missing", "action_type": "cancel"},
            headers=self._login(workspace),
        )
        assert response.status_code == 404
        assert store.take_turn_control("sess_task", _OWNER)["stop_requested"] is False

    def test_unknown_session_is_not_a_control_channel(self, workspace: Path) -> None:
        client = self._client(workspace)
        response = client.post(
            "/api/interrupts",
            json={"session_id": "sess_not_mine", "all": True, "action_type": "cancel"},
            headers=self._login(workspace),
        )
        assert response.status_code == 404
