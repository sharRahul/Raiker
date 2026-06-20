from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import BackupManifest, BudgetRecord, HostedRoutine, RetentionPolicy
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Path:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


# ── RAIKER-5401: Hosted Routines ──


def test_hosted_routine_crud(store: SQLiteStore) -> None:
    now = utc_now()
    r = HostedRoutine(
        routine_id=new_id("htr_"),
        name="daily-cleanup",
        routine_type="scheduled",
        schedule="0 0 * * *",
        endpoint=None,
        enabled=False,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_hosted_routine(r)
    list_r = store.list_hosted_routines()
    assert len(list_r) == 1
    assert list_r[0]["name"] == "daily-cleanup"
    assert store.delete_hosted_routine(r.routine_id) is True
    assert len(store.list_hosted_routines()) == 0


def test_hosted_routine_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    now = utc_now()
    r = HostedRoutine(new_id("htr_"), "test", "webhook", None, "https://hook.example.com", True, "admin", now, now)
    store1.insert_hosted_routine(r)
    store2 = SQLiteStore(workspace)
    list_r = store2.list_hosted_routines()
    assert len(list_r) == 1


# ── RAIKER-5501: Budget Records ──


def test_budget_crud(store: SQLiteStore) -> None:
    now = utc_now()
    b = BudgetRecord(
        budget_id=new_id("bud_"),
        name="cloud-gpu-budget",
        max_cost=100.0,
        current_cost=25.0,
        currency="USD",
        scope="cloud",
        enabled=True,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_budget_record(b)
    loaded = store.load_budget_record(b.budget_id)
    assert loaded is not None
    assert loaded["name"] == "cloud-gpu-budget"
    assert loaded["current_cost"] == 25.0
    assert store.update_budget_cost(b.budget_id, 10.0) is True
    loaded2 = store.load_budget_record(b.budget_id)
    assert loaded2["current_cost"] == 35.0


def test_budget_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_budget_record(BudgetRecord(new_id("bud_"), "test", 50, 0, "USD", "project", True, "admin", utc_now(), utc_now()))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_budget_records()) == 1


# ── RAIKER-5601: Retention Policies ──


def test_retention_policy_crud(store: SQLiteStore) -> None:
    now = utc_now()
    p = RetentionPolicy(
        policy_id=new_id("ret_"),
        target_type="events",
        retention_days=90,
        legal_hold=False,
        enabled=True,
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_retention_policy(p)
    policies = store.list_retention_policies()
    assert len(policies) >= 1
    assert policies[0]["retention_days"] == 90


def test_retention_policy_legal_hold(store: SQLiteStore) -> None:
    now = utc_now()
    p = RetentionPolicy(new_id("ret_"), "audit_exports", 365, True, True, "admin", now, now)
    store.insert_retention_policy(p)
    loaded = store.list_retention_policies(enabled_only=True)
    assert any(r["legal_hold"] for r in loaded if r["policy_id"] == p.policy_id)


def test_retention_policy_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_retention_policy(RetentionPolicy(new_id("ret_"), "sessions", 30, False, True, "admin", utc_now(), utc_now()))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_retention_policies()) == 1


# ── RAIKER-5601: Backup Manifests ──


def test_backup_manifest_crud(store: SQLiteStore) -> None:
    now = utc_now()
    m = BackupManifest(
        manifest_id=new_id("bkm_"),
        backup_type="full",
        scope_json='{"tables": ["events_index", "sessions"]}',
        path="/tmp/backup.jsonl",
        checksum="abc123",
        size_bytes=1024,
        created_by="admin",
        created_at=now,
    )
    store.insert_backup_manifest(m)
    manifests = store.list_backup_manifests()
    assert len(manifests) == 1
    assert manifests[0]["backup_type"] == "full"


def test_backup_manifest_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_backup_manifest(BackupManifest(new_id("bkm_"), "incremental", "{}", None, None, None, "admin", utc_now()))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_backup_manifests()) == 1
