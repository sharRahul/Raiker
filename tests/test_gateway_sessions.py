from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.cli.commands import build_prompt_envelope
from raiker.gateway.agent_gateway import AgentGateway
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore


def test_session_create_load(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manager = SessionManager(store, tmp_path)
    created = manager.create_session(title="Test")
    loaded = manager.load_session(created.session_id)
    assert loaded is not None
    assert loaded.session_id == created.session_id


def test_first_prompt_becomes_a_stable_session_title(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manager = SessionManager(store, tmp_path)
    created = manager.create_session()

    manager.track_turn(created.session_id, "turn_1", "  Plan   the   release checklist.  ")
    manager.track_turn(created.session_id, "turn_2", "This must not replace the first title.")

    loaded = store.load_session(created.session_id)
    assert loaded is not None
    assert loaded["title"] == "Plan the release checklist."


def test_gateway_preserves_client_metadata_and_writes_events(
    tmp_path: Path, monkeypatch: Any, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source_config / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("Hello Raiker"))
    assert response.status == "failed"
    assert response.checkpoint_path is not None
    lines = [
        json.loads(line)
        for line in __import__("pathlib")
        .Path(response.events_path)
        .read_text(encoding="utf-8")
        .splitlines()
    ]  # type: ignore[arg-type]
    assert lines[0]["payload"]["client"]["interface_status"] == "equal_primary_when_enabled"


def test_gateway_finalization_events_are_not_runtime_states(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source_config / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("Hello Raiker"))
    lines = [
        json.loads(line)
        for line in __import__("pathlib")
        .Path(response.events_path)
        .read_text(encoding="utf-8")
        .splitlines()
    ]  # type: ignore[arg-type]
    checkpoint_event = next(event for event in lines if event["event_type"] == "checkpoint_created")
    turn_closed_event = next(event for event in lines if event["event_type"] == "turn_closed")
    assert checkpoint_event["actor"] == "checkpoint_service"
    assert turn_closed_event["actor"] == "agent_gateway"
