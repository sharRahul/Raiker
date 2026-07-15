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
    PLUGIN_ED25519_PUBLIC_KEY_ENV,
    PLUGIN_SIGNING_KEY_ENV,
    ed25519_signature_hex,
    expected_plugin_signature,
    plugin_ed25519_public_key,
    verify_plugin_asymmetric_signature,
)
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore


def _generate_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_hex = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    public_hex = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        .hex()
    )
    return private_hex, public_hex


_PRIV_HEX, _PUB_HEX = _generate_keypair()
_OTHER_PRIV_HEX, _OTHER_PUB_HEX = _generate_keypair()


def _canonical(manifest: dict[str, object]) -> str:
    return json.dumps(
        {k: v for k, v in manifest.items() if k != "supply_chain"},
        sort_keys=True,
        separators=(",", ":"),
    )


def _manifest(*, ed25519_signature: str | None = None) -> dict[str, object]:
    manifest: dict[str, object] = {
        "plugin_id": "local.readonly",
        "name": "Local Read Only",
        "version": "1.0.0",
        "trust_level": "local_dev",
        "permissions": ["tool:read_file"],
        "dependencies": [],
    }
    clean = _canonical(manifest)
    supply_chain: dict[str, object] = {
        "checksum": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        # HMAC signature stays a presence marker (no RAIKER_PLUGIN_SIGNING_KEY set).
        "signature": "sig-marker",
    }
    if ed25519_signature is not None:
        supply_chain["ed25519_signature"] = ed25519_signature
    manifest["supply_chain"] = supply_chain
    return manifest


def _signed_manifest(private_hex: str = _PRIV_HEX) -> dict[str, object]:
    manifest = _manifest()
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["ed25519_signature"] = ed25519_signature_hex(manifest, private_hex)
    return manifest


# ── Pure verification ────────────────────────────────────────────────────────


def test_public_key_env_default_empty_and_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)
    assert plugin_ed25519_public_key() == ""
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    assert plugin_ed25519_public_key() == _PUB_HEX


def test_no_public_key_skips_asymmetric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)
    ok, reason = verify_plugin_asymmetric_signature(_manifest(ed25519_signature="garbage"))
    assert ok is True
    assert reason == "asymmetric_not_configured"


def test_valid_signature_verifies_with_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ok, reason = verify_plugin_asymmetric_signature(_signed_manifest())
    assert ok is True
    assert reason == "asymmetric_signature_verified"


def test_missing_signature_fails_closed_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ok, reason = verify_plugin_asymmetric_signature(_manifest())
    assert ok is False
    assert reason == "no_asymmetric_signature_in_manifest"


def test_non_string_signature_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    manifest = _manifest(ed25519_signature="placeholder")
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["ed25519_signature"] = 1234
    ok, reason = verify_plugin_asymmetric_signature(manifest)
    assert ok is False
    assert reason == "no_asymmetric_signature_in_manifest"


def test_signature_from_other_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Signed by a different private key than the trusted public key.
    manifest = _signed_manifest(_OTHER_PRIV_HEX)
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ok, reason = verify_plugin_asymmetric_signature(manifest)
    assert ok is False
    assert reason == "asymmetric_signature_invalid"


def test_tampered_body_invalidates_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _signed_manifest()
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    manifest["version"] = "9.9.9"
    ok, reason = verify_plugin_asymmetric_signature(manifest)
    assert ok is False
    assert reason == "asymmetric_signature_invalid"


def test_malformed_public_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, "not-hex")
    ok, reason = verify_plugin_asymmetric_signature(_signed_manifest())
    assert ok is False
    assert reason == "asymmetric_public_key_invalid"


def test_wrong_length_public_key_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, "abcd")
    ok, reason = verify_plugin_asymmetric_signature(_signed_manifest())
    assert ok is False
    assert reason == "asymmetric_public_key_invalid"


def test_malformed_signature_hex_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ok, reason = verify_plugin_asymmetric_signature(_manifest(ed25519_signature="zz-not-hex"))
    assert ok is False
    assert reason == "asymmetric_signature_invalid"


# ── Enforcement through the install plan ─────────────────────────────────────


def test_plan_denies_missing_signature_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    plan = plan_plugin_registration(_manifest())
    assert plan.status == "denied"
    assert "no_asymmetric_signature_in_manifest" in plan.reasons


def test_plan_accepts_valid_signature_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    plan = plan_plugin_registration(_signed_manifest())
    assert plan.status == "planned"
    assert not any(r.startswith("asymmetric") or "asymmetric" in r for r in plan.reasons)


def test_plan_unaffected_without_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)
    plan = plan_plugin_registration(_manifest())
    assert plan.status == "planned"
    assert not any("asymmetric" in r for r in plan.reasons)


def test_hmac_and_ed25519_enforced_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid Ed25519 signature but an invalid HMAC signature: install still denied.
    manifest = _signed_manifest()
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, "owner-hmac-key")
    plan = plan_plugin_registration(manifest)
    assert plan.status == "denied"
    assert "signature_invalid" in plan.reasons
    assert "asymmetric_signature_verified" not in plan.reasons

    # Fix the HMAC signature too: both schemes now satisfied → planned.
    supply_chain = manifest["supply_chain"]
    assert isinstance(supply_chain, dict)
    supply_chain["signature"] = expected_plugin_signature(manifest, "owner-hmac-key")
    plan = plan_plugin_registration(manifest)
    assert plan.status == "planned"


# ── Enforcement through the governed plugin_install executor ─────────────────


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-asym"
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


def test_install_fails_closed_on_missing_asymmetric_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ws = _ws(tmp_path)
    _enable_install(ws)
    result = _install(ws, _manifest())
    assert result.error == "plugin_install_plan_not_approved:denied"  # type: ignore[attr-defined]
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_install_succeeds_on_valid_ed25519_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, _PUB_HEX)
    ws = _ws(tmp_path)
    _enable_install(ws)
    result = _install(ws, _signed_manifest())
    assert result.decision == "allow"  # type: ignore[attr-defined]
    records = SQLiteStore(ws).list_plugin_install_records(status="installed")
    assert len(records) == 1
    assert records[0]["plugin_id"] == "local.readonly"
