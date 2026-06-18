from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.events.query import EventViewer
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def writer(store: SQLiteStore) -> EventLogWriter:
    return EventLogWriter(store)


@pytest.fixture
def viewer(store: SQLiteStore) -> EventViewer:
    return EventViewer(store)


class TestEventViewer:
    def test_list_events_empty(self, viewer: EventViewer) -> None:
        events = viewer.list_events(limit=10)
        assert events == []

    def test_list_events_with_data(
        self, store: SQLiteStore, writer: EventLogWriter, viewer: EventViewer
    ) -> None:
        sid = new_id("sess_")
        event = make_event(
            session_id=sid,
            turn_id=None,
            event_type="prompt_received",
            actor="test",
            payload={"text": "hello"},
        )
        writer.append(event)
        events = viewer.list_events(session_id=sid, limit=10)
        assert len(events) == 1
        assert events[0]["event_type"] == "prompt_received"

    def test_list_events_filter_type(
        self, store: SQLiteStore, writer: EventLogWriter, viewer: EventViewer
    ) -> None:
        sid = new_id("sess_")
        writer.append(
            make_event(session_id=sid, turn_id=None, event_type="prompt_received", actor="test")
        )
        writer.append(
            make_event(session_id=sid, turn_id=None, event_type="turn_closed", actor="test")
        )
        events = viewer.list_events(session_id=sid, event_type="turn_closed", limit=10)
        assert len(events) == 1
        assert events[0]["event_type"] == "turn_closed"

    def test_get_event_index(
        self, store: SQLiteStore, writer: EventLogWriter, viewer: EventViewer
    ) -> None:
        sid = new_id("sess_")
        event = make_event(session_id=sid, turn_id=None, event_type="prompt_received", actor="test")
        writer.append(event)
        index = viewer.get_event_index(event.event_id)
        assert index is not None
        assert index["event_id"] == event.event_id

    def test_get_event_index_missing(self, viewer: EventViewer) -> None:
        assert viewer.get_event_index("evt_nonexistent") is None

    def test_read_event_payload(
        self, store: SQLiteStore, writer: EventLogWriter, viewer: EventViewer
    ) -> None:
        sid = new_id("sess_")
        event = make_event(
            session_id=sid,
            turn_id=None,
            event_type="prompt_received",
            actor="test",
            payload={"text": "hello"},
        )
        writer.append(event)
        payload = viewer.read_event_payload(event.event_id)
        assert payload is not None
        assert payload["event_type"] == "prompt_received"

    def test_read_event_payload_missing(self, viewer: EventViewer) -> None:
        assert viewer.read_event_payload("evt_nonexistent") is None
