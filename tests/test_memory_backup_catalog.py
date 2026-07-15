from pathlib import Path

import pytest

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
    assert store.request_backup_erasure(manifest.manifest_id, "owner")
    assert store.record_backup_erased(manifest.manifest_id, "owner")
    row = store.list_backup_manifests()[0]
    assert row["restore_verified_at"] and row["erased_at"]
    with store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_lifecycle_audit WHERE memory_id = ? AND action = 'backup_access'",
            (f"backup:{manifest.manifest_id}",),
        ).fetchone()[0] == 4


def test_backup_legal_hold_blocks_erasure(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manifest = BackupManifest(new_id("bkm_"), "snapshot", "{}", None, None, None, "owner", utc_now(), legal_hold=True)
    store.insert_backup_manifest(manifest)
    assert not store.request_backup_erasure(manifest.manifest_id)


def test_backup_legal_hold_change_is_audited(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    manifest = BackupManifest(new_id("bkm_"), "snapshot", "{}", None, None, None, "owner", utc_now())
    store.insert_backup_manifest(manifest)
    assert store.set_backup_legal_hold(manifest.manifest_id, True, "owner")
    with store.connect() as connection:
        assert connection.execute(
            "SELECT action FROM memory_lifecycle_audit WHERE memory_id = ? ORDER BY created_at DESC LIMIT 1",
            (f"backup:{manifest.manifest_id}",),
        ).fetchone()["action"] == "legal_hold"


def test_memory_lifecycle_audit_rows_are_append_only(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    audit_id = store.record_memory_lifecycle_event("mem_test", "admin_access", "principal_owner")
    with store.connect() as connection:
        with pytest.raises(Exception, match="memory_lifecycle_audit_immutable"):
            connection.execute("UPDATE memory_lifecycle_audit SET actor_id = 'other' WHERE audit_id = ?", (audit_id,))
        with pytest.raises(Exception, match="memory_lifecycle_audit_immutable"):
            connection.execute("DELETE FROM memory_lifecycle_audit WHERE audit_id = ?", (audit_id,))
