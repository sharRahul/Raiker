from pathlib import Path

from raiker.memory.eidetic import record_observation
from raiker.storage.sqlite import SQLiteStore


def test_observation_records_checksum_and_retention(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    item = record_observation(store=store, source_event_id="evt_1", session_id="sess_1", summary="tool output", content="exact output")
    assert len(item.content_sha256) == 64
    with store.connect() as connection:
        row = connection.execute("SELECT retention FROM eidetic_observations WHERE observation_id = ?", (item.observation_id,)).fetchone()
    assert row is not None and row["retention"] == "short_term_30_days"
