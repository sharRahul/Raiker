from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.plugins.policy import plan_plugin_registration
from raiker.plugins.verify import (
    PLUGIN_SIGNING_KEY_ENV,
    expected_plugin_signature,
    plugin_signing_key,
    verify_plugin_signature,
)
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_KEY = "owner-signing-key-123"


def _canonical(manifest: dict[str, object]) -> str:
    return json.dumps(
        {k: v for k, v in manifest.items() if k != "supply_chain"},
        sort_keys=True,
        separators=(",", ":"),
    )


def _manifest(*, signature: str | None = None) -> dict[str, object]:
    manifest: dict[str, object] = {
        "plugin_id": "local.readonly",
        "name": "Local Read Only",
        "version": "1.0.0",
        "trust_level": "local_dev",
        "permissions": ["tool:read_file"],
        "dependencies": [],
    }
    clean = _canonical(manifest)
    manifest["supply_chain"] = {
        "checksum": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        "signature": signature if signature is not None else "sig-marker",
    }
    return manifest


def _signed_manifest() -> dict[str, object]:
    manifest = _manifest(signature="placeholder")
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["signature"] = expected_plugin_signature(manifest, _KEY)
    return manifest


# ── Pure verification ────────────────────────────────────────────────────────


def test_signing_key_env_default_empty_and_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    assert plugin_signing_key() == ""
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    assert plugin_signing_key() == _KEY


def test_no_key_keeps_presence_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    ok, reason = verify_plugin_signature(_manifest(signature="anything"))
    assert ok is True
    assert reason == "signature_present"


def test_missing_signature_always_fails() -> None:
    manifest = _manifest()
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["signature"] = None
    ok, reason = verify_plugin_signature(manifest)
    assert ok is False
    assert reason == "no_signature_in_manifest"


def test_valid_hmac_signature_verifies_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    ok, reason = verify_plugin_signature(_signed_manifest())
    assert ok is True
    assert reason == "signature_verified"


def test_wrong_signature_fails_closed_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    ok, reason = verify_plugin_signature(_manifest(signature="sig-marker"))
    assert ok is False
    assert reason == "signature_invalid"


def test_signature_from_other_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest(signature="placeholder")
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["signature"] = expected_plugin_signature(manifest, "a-different-key")
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    ok, reason = verify_plugin_signature(manifest)
    assert ok is False
    assert reason == "signature_invalid"


def test_tampered_body_invalidates_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _signed_manifest()
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    # Tamper with a signed field; the HMAC no longer matches.
    manifest["version"] = "9.9.9"
    ok, reason = verify_plugin_signature(manifest)
    assert ok is False
    assert reason == "signature_invalid"


# ── Enforcement through the install plan ─────────────────────────────────────


def test_plan_denies_bad_signature_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    plan = plan_plugin_registration(_manifest(signature="sig-marker"))
    assert plan.status == "denied"
    assert "signature_invalid" in plan.reasons


def test_plan_accepts_valid_signature_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    plan = plan_plugin_registration(_signed_manifest())
    assert plan.status == "planned"
    assert not any(r.startswith("signature") for r in plan.reasons)


# ── Enforcement through the governed plugin_install executor ─────────────────


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-sig"
    ws.mkdir()
    return ws


def _enable_install(ws: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            ("plugin_install", "principal_owner", utc_now(), "docs/threat-models/plugins.md"),
        )
    result = svc.set_capability_state(
        "plugin_install", "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert result.ok is True, result.reason_code


def _install(ws: Path, manifest: dict[str, object]) -> object:
    (ws / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
    assert raw is not None
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="plugin_install",
        tool_or_service_name="plugin_install",
        arguments={"manifest_path": "manifest.json"},
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_install",
    )
    return authority.route_action(action, Principal(**raw))


def test_install_fails_closed_on_bad_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    ws = _ws(tmp_path)
    _enable_install(ws)
    result = _install(ws, _manifest(signature="sig-marker"))
    assert result.error == "plugin_install_plan_not_approved:denied"  # type: ignore[attr-defined]
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_install_succeeds_on_valid_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, _KEY)
    ws = _ws(tmp_path)
    _enable_install(ws)
    result = _install(ws, _signed_manifest())
    assert result.decision == "allow"  # type: ignore[attr-defined]
    records = SQLiteStore(ws).list_plugin_install_records(status="installed")
    assert len(records) == 1
    assert records[0]["plugin_id"] == "local.readonly"
