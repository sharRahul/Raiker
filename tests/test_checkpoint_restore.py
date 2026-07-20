"""Workstream B / Slice B1 — checkpoint pre-image capture.

These tests pin the B1 guarantees: every workspace-file mutation routed through
the broker records a content-addressed pre-image blob plus a metadata-only
manifest entry *before* it overwrites the file, so the mutation becomes
reversible — and capture never leaks file content into the event log, never
reaches outside the workspace, and never breaks the underlying mutation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from raiker.checkpoints.capture import (
    MAX_PRE_IMAGE_BYTES,
    STATUS_ABSENT,
    STATUS_CAPTURED,
    STATUS_OVERSIZE,
    CheckpointCaptureService,
)
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return Principal(**raw)


def _authority(ws: Path, store: SQLiteStore) -> RuntimeAuthority:
    return RuntimeAuthority(
        store,
        EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )


def _write_action(
    *, path: str, text: str, action_type: str = "write_file", extra: dict | None = None
) -> GovernedAction:
    args: dict[str, object] = {"path": path, "text": text}
    if extra:
        args = {"path": path, **extra}
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=args,
        risk_level=RiskLevelValue.LOW,
        session_id="sess_a",
    )


# ── Pre-image is captured BEFORE the mutation overwrites the file ─────────────


def test_capture_records_pre_image_before_overwrite(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    (ws / "note.txt").write_text("OLD CONTENT", encoding="utf-8")
    authority = _authority(ws, store)

    result = authority.route_action(
        _write_action(path="note.txt", text="NEW CONTENT"), _human(store)
    )

    assert result.decision == "allow" and result.message == "executed"
    # The live file holds the new content …
    assert (ws / "note.txt").read_text(encoding="utf-8") == "NEW CONTENT"
    # … but the manifest captured the *old* content, so the write is reversible.
    entries = store.list_checkpoint_capture_entries(session_id="sess_a")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["capture_status"] == STATUS_CAPTURED
    assert entry["existed_before"] == 1
    assert entry["workspace_path"] == "note.txt"
    blob = authority.capture_service.blob_path(entry["pre_image_sha256"])
    assert blob.read_bytes() == b"OLD CONTENT"


def test_capture_blob_is_content_addressed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    (ws / "a.txt").write_text("shared pre-image", encoding="utf-8")
    (ws / "b.txt").write_text("shared pre-image", encoding="utf-8")
    authority = _authority(ws, store)

    authority.route_action(_write_action(path="a.txt", text="A2"), _human(store))
    authority.route_action(_write_action(path="b.txt", text="B2"), _human(store))

    entries = store.list_checkpoint_capture_entries(session_id="sess_a")
    hashes = {e["pre_image_sha256"] for e in entries}
    # Blob name is exactly the sha256 of the pre-image bytes …
    expected = hashlib.sha256(b"shared pre-image").hexdigest()
    assert hashes == {expected}
    # … and identical pre-images deduplicate to a single stored object.
    objects = list((ws / ".raiker" / "checkpoints" / "objects").rglob("*"))
    object_files = [p for p in objects if p.is_file()]
    assert len(object_files) == 1
    assert object_files[0].name == expected


def test_capture_absent_file_records_absent_no_blob(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    authority = _authority(ws, store)

    # Target does not exist yet → the reversible pre-image is "no file".
    authority.route_action(_write_action(path="fresh.txt", text="hello"), _human(store))

    entry = store.list_checkpoint_capture_entries(session_id="sess_a")[0]
    assert entry["capture_status"] == STATUS_ABSENT
    assert entry["existed_before"] == 0
    assert entry["pre_image_sha256"] is None
    assert entry["pre_image_size"] == 0


def test_capture_via_apply_patch(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    (ws / "poem.txt").write_text("roses\n", encoding="utf-8")
    authority = _authority(ws, store)

    authority.route_action(
        _write_action(
            path="poem.txt",
            text="",
            action_type="apply_patch",
            extra={"new_text": "roses are red\n"},
        ),
        _human(store),
    )

    entry = store.list_checkpoint_capture_entries(session_id="sess_a")[0]
    assert entry["capability"] == "patch_apply_execution"
    assert entry["capture_status"] == STATUS_CAPTURED
    blob = authority.capture_service.blob_path(entry["pre_image_sha256"])
    assert blob.read_bytes() == b"roses\n"


# ── Event log is metadata-only (no file content ever) ────────────────────────


def test_capture_event_is_metadata_only(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    (ws / "secret.txt").write_text("TOP SECRET PRE-IMAGE", encoding="utf-8")
    authority = _authority(ws, store)

    authority.route_action(
        _write_action(path="secret.txt", text="redacted"), _human(store)
    )

    viewer = EventViewer(store)
    indexed = viewer.list_events(session_id="sess_a", event_type="checkpoint_captured")
    assert len(indexed) == 1
    payload = viewer.read_event_payload(indexed[0]["event_id"])
    assert payload is not None
    serialized = str(payload)
    # Neither the pre-image nor the new content may appear anywhere in the event.
    assert "TOP SECRET PRE-IMAGE" not in serialized
    assert "redacted" not in serialized
    # Only metadata: content-address, size, status, path.
    body = payload["payload"]
    assert body["capture_status"] == STATUS_CAPTURED
    assert body["workspace_path"] == "secret.txt"
    assert "pre_image_sha256" in body and body["pre_image_sha256"]


# ── Non-file mutations are not captured ──────────────────────────────────────


def test_non_file_mutation_not_captured(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    authority = _authority(ws, store)

    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="memory_write",
        tool_or_service_name="memory_write",
        arguments={"text": "Raiker persists state in SQLite.", "scope": "project"},
        risk_level=RiskLevelValue.LOW,
        session_id="sess_a",
    )
    result = authority.route_action(action, _human(store))

    assert result.message == "executed"
    assert store.list_checkpoint_capture_entries(session_id="sess_a") == []


# ── Capture never breaks the underlying mutation ─────────────────────────────


def test_capture_failure_does_not_break_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    store.create_session("sess_a", "ws")
    (ws / "note.txt").write_text("OLD", encoding="utf-8")
    authority = _authority(ws, store)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("capture storage unavailable")

    # Force the manifest write to fail; the mutation must still succeed.
    monkeypatch.setattr(store, "insert_checkpoint_capture_entry", _boom)

    result = authority.route_action(
        _write_action(path="note.txt", text="NEW"), _human(store)
    )

    assert result.decision == "allow" and result.message == "executed"
    assert (ws / "note.txt").read_text(encoding="utf-8") == "NEW"
    # No manifest row, and a metadata-only failure event was recorded.
    assert store.list_checkpoint_capture_entries(session_id="sess_a") == []
    viewer = EventViewer(store)
    failed = viewer.list_events(
        session_id="sess_a", event_type="checkpoint_capture_failed"
    )
    assert len(failed) == 1


# ── Service-level: oversize + outside-workspace are handled honestly ─────────


def test_snapshot_oversize_records_status_no_blob(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    service = CheckpointCaptureService(store, max_bytes=8)
    (ws / "big.txt").write_text("this is definitely longer than eight bytes", encoding="utf-8")

    pre = service.snapshot_pre_image("file_write_execution", {"path": "big.txt"})
    assert pre is not None
    assert pre.status == STATUS_OVERSIZE
    assert pre.existed is True
    assert pre.data is None

    meta = service.commit(
        pre, session_id="sess_a", turn_id=None, action_id="act_x", principal_id="principal_owner"
    )
    assert meta["capture_status"] == STATUS_OVERSIZE
    assert meta["pre_image_sha256"] is None
    # An oversize pre-image is honestly un-captured: no blob is written.
    objects = list((ws / ".raiker" / "checkpoints" / "objects").rglob("*"))
    assert [p for p in objects if p.is_file()] == []


def test_snapshot_outside_workspace_is_skipped(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    service = CheckpointCaptureService(store)

    assert service.snapshot_pre_image("file_write_execution", {"path": "../escape.txt"}) is None
    assert service.snapshot_pre_image("file_write_execution", {"path": ""}) is None
    # A non-file-mutation capability is never eligible for capture.
    assert service.eligible("memory_write_execution") is False
    assert service.snapshot_pre_image("memory_write_execution", {"text": "x"}) is None


def test_default_size_cap_is_bounded() -> None:
    # A sanity floor/ceiling so the cap can't silently drift to 0 or unbounded.
    assert 1024 * 1024 <= MAX_PRE_IMAGE_BYTES <= 64 * 1024 * 1024
