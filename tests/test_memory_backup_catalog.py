from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import BackupManifest
from raiker.storage.sqlite import SQLiteStore


def test_backup_catalog_tracks_restore_and_honest_erasure_state(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manifest = BackupManifest(
        new_id("bkm_"), "snapshot", "{}", None, "sha256", 1, "owner", utc_now(),
        encryption_key_id="wk_1", retention_until="2100-01-01T00:00:00Z",
    )
    store.insert_backup_manifest(manifest)
    assert store.record_backup_restore_verified(manifest.manifest_id)
    assert store.request_backup_erasure(manifest.manifest_id)
    assert store.record_backup_erased(manifest.manifest_id)
    row = store.list_backup_manifests()[0]
    assert row["restore_verified_at"] and row["erased_at"]


def test_backup_legal_hold_blocks_erasure(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manifest = BackupManifest(new_id("bkm_"), "snapshot", "{}", None, None, None, "owner", utc_now(), legal_hold=True)
    store.insert_backup_manifest(manifest)
    assert not store.request_backup_erasure(manifest.manifest_id)
