from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.security.integrity_sweep import IntegritySweep
from raiker.storage.sqlite import SQLiteStore


def test_integrity_sweep_is_silent_when_green_and_notifies_each_deviation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    sweep = IntegritySweep(store)

    assert sweep.run("principal_owner")["deviations"] == []
    assert store.list_notifications("principal_owner") == []

    store.create_session("sess", str(ws))
    EventLogWriter(store).append(
        make_event(session_id="sess", turn_id=None, event_type="action_proposed", actor="test", payload={})
    )
    event_path = store.paths.events_dir / "sess.jsonl"
    event_path.write_text("tampered\n", encoding="utf-8")
    ApiSessionStore(ws).create_session("principal_owner", absolute_expires_in_seconds=-1)
    now = utc_now()
    store.upsert_principal_capability_gate_state(
        "principal_owner",
        {
            "capability": "subagents",
            "state": "enabled_runtime",
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.example.test")

    result = sweep.run("principal_owner")

    deviations = cast(list[dict[str, object]], result["deviations"])
    assert {item["kind"] for item in deviations} == {
        "event_chain", "session_invalid", "gate_mode_drift", "egress_allowlist_drift",
    }
    assert store.list_notifications("principal_owner")[0]["kind"] == "integrity_deviation"
