from __future__ import annotations

import json

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


def test_event_writer_appends_and_indexes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    client = ClientMetadata(type="tui", name="raiker-terminal", version="0.0.0")
    first = make_event(session_id=session_id, turn_id=turn_id, event_type="prompt_received", actor="test", payload={}, client=client)
    second = make_event(session_id=session_id, turn_id=turn_id, event_type="turn_closed", actor="test", payload={}, client=client)
    path1, offset1 = writer.append(first)
    path2, offset2 = writer.append(second)
    assert path1 == path2
    assert offset2 > offset1
    lines = [json.loads(line) for line in path1.read_text(encoding="utf-8").splitlines()]
    assert [line["event_id"] for line in lines] == [first.event_id, second.event_id]
    assert lines[0]["payload"]["client"]["interface_status"] == "equal_primary_when_enabled"
    with store.connect() as connection:
        count = connection.execute("SELECT count(*) FROM events_index").fetchone()[0]
    assert count == 2
