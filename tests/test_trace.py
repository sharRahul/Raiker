from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.trace.builder import build_turn_trace, format_trace


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def writer(store: SQLiteStore) -> EventLogWriter:
    return EventLogWriter(store)


def _seed_turn(
    writer: EventLogWriter,
    session_id: str,
    turn_id: str,
    *,
    include_tool: bool = True,
    include_model: bool = False,
    fail: bool = False,
    deny: bool = False,
) -> None:
    action_id = new_id("act_")
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="prompt_received",
            actor="test",
            payload={"preview": "list my github issues"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "RECEIVED", "to": "NORMALISED"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="prompt_normalised",
            actor="runtime",
            payload={},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "NORMALISED", "to": "CLASSIFIED"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="intent_classified",
            actor="runtime",
            payload={"intent": "query"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "CLASSIFIED", "to": "CONTEXT_READY"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="context_gathered",
            actor="runtime",
            payload={"sources": ["config"]},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "CONTEXT_READY", "to": "PLAN_READY"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="plan_created",
            actor="runtime",
            payload={"steps": ["search_issues"]},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "PLAN_READY", "to": "POLICY_REVIEWED"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="policy_decision",
            actor="runtime",
            payload={"decision": "allow"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "POLICY_REVIEWED", "to": "EXECUTING"},
        )
    )
    if include_tool:
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="tool_started",
                actor="tool_broker",
                payload={"action_id": action_id, "tool_name": "search_issues"},
            )
        )
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="tool_completed",
                actor="tool_broker",
                payload={"action_id": action_id, "tool_name": "search_issues", "status": "success"},
            )
        )
    if include_model:
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="model_request_started",
                actor="runtime",
                payload={"provider": "anthropic", "model": "claude-3-sonnet", "message_count": 3},
            )
        )
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="model_request_completed",
                actor="runtime",
                payload={
                    "provider": "anthropic",
                    "finish_reason": "stop",
                    "usage": {"input_tokens": 120, "output_tokens": 340},
                },
            )
        )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "EXECUTING", "to": "OBSERVING"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="verification_started",
            actor="runtime",
            payload={},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="verification_completed",
            actor="runtime",
            payload={"passed": True},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "OBSERVING", "to": "VERIFYING"},
        )
    )

    if deny:
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="approval_denied",
                actor="runtime",
                payload={"reason": "policy violated"},
            )
        )
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="turn_state_changed",
                actor="runtime",
                payload={"from": "VERIFYING", "to": "DENIED"},
            )
        )
        return  # denied turn ends here

    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "VERIFYING", "to": "RESPONDING"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="response_created",
            actor="runtime",
            payload={"preview": "Found 5 open issues..."},
        )
    )

    if fail:
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="error_recorded",
                actor="runtime",
                payload={"error": "Something broke"},
            )
        )
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type="turn_state_changed",
                actor="runtime",
                payload={"from": "RESPONDING", "to": "FAILED"},
            )
        )
        return  # failed turn ends here

    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "RESPONDING", "to": "CHECKPOINTING"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="checkpoint_created",
            actor="runtime",
            payload={},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_state_changed",
            actor="runtime",
            payload={"from": "CHECKPOINTING", "to": "CLOSED"},
        )
    )
    writer.append(
        make_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="turn_closed",
            actor="runtime",
            payload={},
        )
    )


class TestBuildTurnTrace:
    def test_empty_returns_none(self, store: SQLiteStore) -> None:
        assert build_turn_trace(store, "sess_x", "turn_y") is None

    def test_basic_trace(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid, include_tool=True)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        assert trace.session_id == sid
        assert trace.turn_id == tid
        assert trace.status == "completed"
        assert trace.prompt_preview == "list my github issues"
        assert len(trace.phases) > 0
        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "search_issues"
        assert trace.tool_calls[0].status == "success"

    def test_no_tool_calls(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid, include_tool=False)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        assert len(trace.tool_calls) == 0

    def test_model_calls(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid, include_model=True)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        assert len(trace.model_calls) == 1
        assert trace.model_calls[0].model == "claude-3-sonnet"
        assert trace.model_calls[0].prompt_tokens == 120
        assert trace.model_calls[0].completion_tokens == 340

    def test_failed_trace(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid, fail=True)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        assert trace.status == "failed"
        assert trace.error is not None

    def test_denied_trace(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid, deny=True)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        assert trace.status == "denied"

    def test_different_turn_not_found(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid)
        assert build_turn_trace(store, sid, "turn_wrong") is None


class TestFormatTrace:
    def test_format_returns_string(self, store: SQLiteStore, writer: EventLogWriter) -> None:
        sid = new_id("sess_")
        tid = new_id("turn_")
        _seed_turn(writer, sid, tid)
        trace = build_turn_trace(store, sid, tid)
        assert trace is not None
        output = format_trace(trace)
        assert "Turn:" in output
        assert "Session:" in output
        assert "Status:" in output
        assert "Phases:" in output
        assert tid in output
        assert sid in output

    def test_format_empty_trace(self) -> None:
        from raiker.trace.models import TurnTrace

        trace = TurnTrace(session_id="sess_x", turn_id="turn_y", status="unknown")
        output = format_trace(trace)
        assert "turn_y" in output
        assert "sess_x" in output
