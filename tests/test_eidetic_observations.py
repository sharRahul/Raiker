from pathlib import Path

from raiker.memory.eidetic import propose_gist, record_observation
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
