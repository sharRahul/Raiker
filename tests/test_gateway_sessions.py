from __future__ import annotations

import json

from raiker.cli.commands import build_prompt_envelope
from raiker.gateway.agent_gateway import AgentGateway
from raiker.sessions.manager import SessionManager
from raiker.storage.sqlite import SQLiteStore


def test_session_create_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    manager = SessionManager(store, tmp_path)
    created = manager.create_session(title="Test")
    loaded = manager.load_session(created.session_id)
    assert loaded is not None
    assert loaded.session_id == created.session_id


def test_gateway_preserves_client_metadata_and_writes_events(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source_config / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("Hello Raiker"))
    assert response.status == "completed"
    assert response.checkpoint_path is not None
    lines = [
        json.loads(line)
        for line in __import__("pathlib")
        .Path(response.events_path)
        .read_text(encoding="utf-8")
        .splitlines()
    ]  # type: ignore[arg-type]
    assert lines[0]["payload"]["client"]["interface_status"] == "equal_primary_when_enabled"
