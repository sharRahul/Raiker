from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import AgentEvent, ExportManifest
from raiker.events.export import build_export_manifest, generate_export, redact_event_payload
from raiker.events.integrity import compute_session_root_hash, verify_session_events
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def writer(store: SQLiteStore) -> EventLogWriter:
    return EventLogWriter(store)


def _write_events(writer: EventLogWriter, count: int = 5, session: str | None = None) -> list[AgentEvent]:
    sess = session or new_id("sess_")
    events = []
    for i in range(count):
        evt = make_event(
            session_id=sess,
            turn_id=None,
            event_type="tool_completed",
            actor="test",
            payload={"index": i, "data": f"event_{i}"},
        )
        writer.append(evt)
        events.append(evt)
    return events


# ── ExportManifest contract ──


def test_export_manifest_contract() -> None:
    manifest = ExportManifest(
        export_id=new_id("aex_"),
        manifest_hash="abc123",
        scope_json='{"event_count": 0}',
        redacted=True,
        event_count=0,
        first_event_id=None,
        last_event_id=None,
        first_timestamp=None,
        last_timestamp=None,
        export_path=None,
        exported_by="test",
        created_at=utc_now(),
    )
    assert manifest.export_id.startswith("aex_")
    assert manifest.redacted is True
    assert manifest.event_count == 0


# ── Redaction ──


def test_redact_event_payload() -> None:
    payload = {
        "text": "Hello world",
        "api_key": "sk-1234567890abcdef",
        "nested": {
            "password": "supersecret",
            "normal": "visible",
        },
        "token": "ghp_xxxxx",
    }
    redacted = redact_event_payload(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["text"] == "Hello world"
    assert redacted["nested"]["password"] == "***REDACTED***"
    assert redacted["nested"]["normal"] == "visible"
    assert redacted["token"] == "***REDACTED***"


def test_redact_preserves_non_secret() -> None:
    payload = {"data": "public info", "count": 42}
    redacted = redact_event_payload(payload)
    assert redacted["data"] == "public info"
    assert redacted["count"] == 42


# ── Build export manifest ──


def test_build_export_manifest_no_events(store: SQLiteStore) -> None:
    manifest = build_export_manifest(store, session_id=new_id("sess_"))
    assert manifest is None


def test_build_export_manifest_with_events(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=3)
    sess_id = events[0].session_id
    manifest = build_export_manifest(store, session_id=sess_id)
    assert manifest is not None
    assert manifest.event_count == 3
    assert manifest.first_event_id == events[0].event_id
    assert manifest.last_event_id == events[-1].event_id
    assert manifest.manifest_hash is not None


# ── Generate export ──


def test_generate_export_empty(store: SQLiteStore) -> None:
    manifest = generate_export(store, session_id=new_id("sess_"))
    assert manifest.event_count == 0
    assert manifest.manifest_hash == "empty"


def test_generate_export_with_events(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=5)
    sess_id = events[0].session_id
    manifest = generate_export(store, session_id=sess_id)
    assert manifest.event_count == 5
    assert manifest.export_path is not None
    assert Path(manifest.export_path).exists()
    with open(manifest.export_path) as f:
        lines = f.readlines()
    assert len(lines) == 5


def test_generate_export_redacted(store: SQLiteStore, writer: EventLogWriter) -> None:
    sess_id = new_id("sess_")
    sensitive = make_event(
        session_id=sess_id,
        turn_id=None,
        event_type="action_proposed",
        actor="test",
        payload={"api_key": "sk-1234", "data": "normal"},
    )
    writer.append(sensitive)
    manifest = generate_export(store, session_id=sess_id, redact=True)
    assert manifest.export_path is not None
    with open(manifest.export_path) as f:
        line = f.readline()
        loaded = json.loads(line)
    assert loaded["payload"]["api_key"] == "***REDACTED***"
    assert loaded["payload"]["data"] == "normal"


# ── Hash chain ──


def test_event_hash_chain(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=3)
    sess_id = events[0].session_id
    rows = store.list_session_events_for_integrity(sess_id)
    assert len(rows) == 3
    for i, row in enumerate(rows):
        if i == 0:
            assert row.get("prev_event_sha256") is None
        else:
            assert row.get("prev_event_sha256") is not None


def test_integrity_verification_passes(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=5)
    sess_id = events[0].session_id
    result = verify_session_events(store, sess_id)
    assert result["total_events"] == 5
    assert result["passed"] == 5
    assert result["failed"] == 0
    assert result["chain_intact"] is True


def test_integrity_detects_tampered_hash(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=3)
    sess_id = events[0].session_id
    # Verify with store re-created to get fresh connection
    store2 = SQLiteStore(store.paths.workspace_root)
    rows = store2.list_session_events_for_integrity(sess_id)
    assert len(rows) >= 2
    second_event = rows[1]
    tampered_id = second_event["event_id"]
    with store2.connect() as conn:
        conn.execute(
            "UPDATE events_index SET payload_sha256 = 'tampered' WHERE event_id = ?",
            (tampered_id,),
        )
    result = verify_session_events(store2, sess_id)
    assert result["failed"] >= 1
    failed_ids = [d["event_id"] for d in result["details"] if d.get("hash_matches") is False]
    assert tampered_id in failed_ids


def test_compute_session_root_hash(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=3)
    sess_id = events[0].session_id
    root_hash = compute_session_root_hash(store, sess_id)
    assert root_hash is not None
    assert isinstance(root_hash, str)
    assert len(root_hash) == 64  # SHA-256 hex


# ── Export persistence ──


def test_export_persisted(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=2)
    sess_id = events[0].session_id
    manifest = generate_export(store, session_id=sess_id)
    loaded = store.load_audit_export(manifest.export_id)
    assert loaded is not None
    assert loaded["event_count"] == 2
    assert loaded["manifest_hash"] == manifest.manifest_hash


def test_export_list(store: SQLiteStore, writer: EventLogWriter) -> None:
    events = _write_events(writer, count=2)
    manifest = generate_export(store, session_id=events[0].session_id)
    exports = store.list_audit_exports()
    assert len(exports) >= 1
    assert any(e["export_id"] == manifest.export_id for e in exports)
