from pathlib import Path

import pytest

from raiker.memory.eidetic import (
    cleanup_expired_observations,
    expiry_preview,
    propose_gist,
    record_observation,
)
from raiker.storage.sqlite import SQLiteStore


def test_observation_records_checksum_and_retention(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    item = record_observation(store=store, source_event_id="evt_1", session_id="sess_1", summary="tool output", content="exact output")
    assert len(item.content_sha256) == 64
    with store.connect() as connection:
        row = connection.execute("SELECT retention FROM eidetic_observations WHERE observation_id = ?", (item.observation_id,)).fetchone()
    assert row is not None and row["retention"] == "short_term_30_days"


def test_gist_is_reviewable_not_automatically_durable(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    observation = record_observation(store=store, source_event_id="evt_1", session_id="sess_1", summary="tool output", content="exact output")
    gist = propose_gist(store=store, observation_id=observation.observation_id, summary="tool succeeded", confidence=0.8)
    assert gist.status == "pending_review"


def test_expiry_preview_never_deletes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    item = record_observation(store=store, source_event_id="evt_1", session_id="sess_1", summary="tool output", content="exact output", retention="turn_only")
    assert item.observation_id in expiry_preview(store=store, now="2100-01-01T00:00:00Z")


def test_owner_confirmed_expiry_cleanup_only_deletes_previewed_observations(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    due = record_observation(store=store, source_event_id="evt_1", session_id="sess_1", summary="old", content="old", retention="turn_only")
    kept = record_observation(store=store, source_event_id="evt_2", session_id="sess_1", summary="held", content="held", retention="legal_hold")
    with pytest.raises(PermissionError, match="confirmation"):
        cleanup_expired_observations(store=store, now="2100-01-01T00:00:00Z", confirmed_ids={kept.observation_id})
    assert cleanup_expired_observations(store=store, now="2100-01-01T00:00:00Z", confirmed_ids={due.observation_id}) == [due.observation_id]
    with store.connect() as connection:
        assert connection.execute("SELECT 1 FROM eidetic_observations WHERE observation_id = ?", (due.observation_id,)).fetchone() is None
        assert connection.execute("SELECT 1 FROM eidetic_observations WHERE observation_id = ?", (kept.observation_id,)).fetchone() is not None
