from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.integrity import verify_session_events
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


def test_event_writer_appends_and_indexes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    client = ClientMetadata(type="tui", name="raiker-terminal", version="0.0.0")
    first = make_event(
        session_id=session_id,
        turn_id=turn_id,
        event_type="prompt_received",
        actor="test",
        payload={},
        client=client,
    )
    second = make_event(
        session_id=session_id,
        turn_id=turn_id,
        event_type="turn_closed",
        actor="test",
        payload={},
        client=client,
    )
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


def test_concurrent_writer_instances_keep_jsonl_and_hash_chain_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStore(tmp_path)
    session_id = new_id("sess_")
    client = ClientMetadata(type="tui", name="raiker-terminal", version="0.0.0")
    original_last_hash = store.get_last_event_sha256

    def delayed_last_hash(current_session_id: str) -> str | None:
        result = original_last_hash(current_session_id)
        time.sleep(0.002)
        return result

    monkeypatch.setattr(store, "get_last_event_sha256", delayed_last_hash)

    def append_one(index: int) -> None:
        EventLogWriter(store).append(
            make_event(
                session_id=session_id,
                turn_id=new_id("turn_"),
                event_type="prompt_received",
                actor="test",
                payload={"index": index},
                client=client,
            )
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(append_one, range(48)))

    path = EventLogWriter(store).path_for_session(session_id)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 48
    assert len([json.loads(line) for line in lines]) == 48
    integrity = verify_session_events(store, session_id)
    assert integrity["chain_intact"] is True
    assert integrity["failed"] == 0


def test_secret_like_memory_arguments_are_redacted_from_event_log(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
    )
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    broker.execute(
        ToolAction(
            new_id("act_"),
            "memory_write",
            {"text": "password=supersecret123456789", "scope": "project"},
            "high",
            True,
        ),
        session_id=session_id,
        turn_id=turn_id,
    )
    event_text = writer.path_for_session(session_id).read_text(encoding="utf-8")
    assert "supersecret123456789" not in event_text
    assert "[REDACTED_SECRET]" in event_text
