from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PluginInstallRecord
from raiker.plugins.policy import plan_plugin_registration
from raiker.plugins.verify import validate_supply_chain, verify_plugin_checksum, verify_plugin_signature
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Path:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _manifest(overrides: dict | None = None) -> dict:
    base = {
        "plugin_id": "test.plugin",
        "name": "Test Plugin",
        "version": "1.0.0",
        "permissions": ["tool:read_file"],
        "trust_level": "local_dev",
    }
    if overrides:
        base.update(overrides)
    return base


# ── Supply-chain verification ──


def test_verify_checksum_matches() -> None:
    m = _manifest({"supply_chain": {"checksum": "abc123"}})
    ok, reason = verify_plugin_checksum(m)
    assert ok is False
    assert "checksum_mismatch" in reason


def test_verify_checksum_correct() -> None:
    import hashlib
    m = _manifest()
    content = json.dumps({k: v for k, v in m.items() if k != "supply_chain"}, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    m["supply_chain"] = {"checksum": expected}
    ok, reason = verify_plugin_checksum(m)
    assert ok is True
    assert reason == "checksum_verified"


def test_verify_no_checksum() -> None:
    m = _manifest()
    ok, reason = verify_plugin_checksum(m)
    assert ok is False
    assert "no_checksum" in reason


def test_verify_signature_present() -> None:
    m = _manifest({"supply_chain": {"signature": "signed-by-authority"}})
    ok, reason = verify_plugin_signature(m)
    assert ok is True
    assert reason == "signature_present"


def test_verify_no_signature() -> None:
    m = _manifest()
    ok, reason = verify_plugin_signature(m)
    assert ok is False
    assert "no_signature" in reason


def test_validate_supply_chain() -> None:
    m = _manifest()
    reasons = validate_supply_chain(m)
    assert any("no_checksum" in r for r in reasons)
    assert any("no_signature" in r for r in reasons)


# ── Plugin registration plan with supply chain ──


def test_plan_with_supply_chain() -> None:
    m = _manifest({"supply_chain": {"checksum": "abc", "signature": "def"}})
    plan = plan_plugin_registration(m)
    assert plan.status == "denied"
    assert any("checksum_mismatch" in r for r in plan.reasons)
    assert not any("signature_present" in r for r in plan.reasons)


def test_plan_with_valid_supply_chain() -> None:
    import hashlib
    m = _manifest({"trust_level": "bundled"})
    content = json.dumps({k: v for k, v in m.items() if k != "supply_chain"}, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    m["supply_chain"] = {"checksum": expected, "signature": "valid-sig"}
    plan = plan_plugin_registration(m)
    assert plan.status == "planned"
    assert plan.reasons == []


def test_plan_denied_for_unknown_trust() -> None:
    m = _manifest({"trust_level": "unknown"})
    plan = plan_plugin_registration(m)
    assert plan.status == "denied"


# ── Plugin install record ──


def test_plugin_install_record_crud(store: SQLiteStore) -> None:
    now = utc_now()
    record = PluginInstallRecord(
        record_id=new_id("plr_"),
        plugin_id="test.plugin",
        version="1.0.0",
        trust_level="local_dev",
        checksum="abc123",
        signature=None,
        source_url="https://example.com/plugin",
        commit_sha="deadbeef",
        permissions_json='["tool:read_file"]',
        status="installed",
        installed_at=now,
        installed_by="test",
    )
    store.insert_plugin_install_record(record)
    loaded = store.load_plugin_install_record(record.record_id)
    assert loaded is not None
    assert loaded["plugin_id"] == "test.plugin"
    assert loaded["checksum"] == "abc123"

    records = store.list_plugin_install_records()
    assert len(records) == 1


def test_plugin_install_record_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    now = utc_now()
    record = PluginInstallRecord(
        record_id=new_id("plr_"),
        plugin_id="persist.test",
        version="2.0.0",
        trust_level="bundled",
        checksum="xyz789",
        signature="sig-data",
        source_url=None,
        commit_sha=None,
        permissions_json='["tool:grep"]',
        status="installed",
        installed_at=now,
        installed_by="test",
    )
    store1.insert_plugin_install_record(record)

    store2 = SQLiteStore(workspace)
    loaded = store2.load_plugin_install_record(record.record_id)
    assert loaded is not None
    assert loaded["signature"] == "sig-data"


def test_plugin_install_record_filter_by_status(store: SQLiteStore) -> None:
    now = utc_now()
    for i in range(3):
        store.insert_plugin_install_record(PluginInstallRecord(
            record_id=new_id("plr_"),
            plugin_id=f"p{i}.test",
            version="1.0",
            trust_level="local_dev",
            checksum=None,
            signature=None,
            source_url=None,
            commit_sha=None,
            permissions_json="[]",
            status="pending" if i % 2 == 0 else "installed",
            installed_at=now,
            installed_by="test",
        ))
    pending = store.list_plugin_install_records(status="pending")
    assert len(pending) >= 1
    assert all(r["status"] == "pending" for r in pending)
