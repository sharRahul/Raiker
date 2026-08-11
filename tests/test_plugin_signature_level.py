"""A plugin signature states what it actually proved (BUG-79)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from raiker.plugins.policy import plan_plugin_registration
from raiker.plugins.verify import (
    LEVEL_PRESENT_ONLY,
    LEVEL_UNSIGNED,
    LEVEL_VERIFIED,
    PLUGIN_ED25519_PUBLIC_KEY_ENV,
    PLUGIN_SIGNING_KEY_ENV,
    ed25519_signature_hex,
    expected_plugin_signature,
    signature_verification,
    signing_posture,
)


def _manifest(**supply_chain: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "example.plugin",
        "name": "Example",
        "version": "1.0.0",
        "trust_level": "local_dev",
        "permissions": ["tool:read_file"],
    }
    content = json.dumps(body, sort_keys=True, separators=(",", ":"))
    body["supply_chain"] = {
        "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        **supply_chain,
    }
    return body


def test_the_default_install_reports_present_only_rather_than_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect was the silence, not the baseline."""
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    verification = signature_verification(_manifest(signature="signature"))

    assert verification.level == LEVEL_PRESENT_ONLY
    assert verification.reason == "signature_present"
    assert "no signing key is configured" in verification.explanation.lower()
    assert PLUGIN_SIGNING_KEY_ENV in verification.remediation
    assert verification.to_dict()["verified"] is False


def test_a_manifest_with_no_signature_is_unsigned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    verification = signature_verification(_manifest())

    assert verification.level == LEVEL_UNSIGNED
    assert verification.reason == "no_signature_in_manifest"


def test_an_owner_key_raises_the_level_to_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, "owner-key")
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)
    manifest = _manifest()
    manifest["supply_chain"]["signature"] = expected_plugin_signature(manifest, "owner-key")

    verification = signature_verification(manifest)

    assert verification.level == LEVEL_VERIFIED
    assert verification.method == "hmac"
    assert verification.remediation == ""


def test_a_wrong_signature_under_an_owner_key_is_not_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, "owner-key")
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    verification = signature_verification(_manifest(signature="signature"))

    assert verification.level == LEVEL_UNSIGNED
    assert verification.reason == "signature_invalid"


def test_a_publisher_key_is_authoritative_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = "11" * 32
    manifest = _manifest()
    manifest["supply_chain"]["ed25519_signature"] = ed25519_signature_hex(manifest, seed)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    public_hex = (
        Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed))
        .public_key()
        .public_bytes_raw()
        .hex()
    )
    monkeypatch.setenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, public_hex)
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)

    verification = signature_verification(manifest)

    assert verification.level == LEVEL_VERIFIED
    assert verification.method == "ed25519"


def test_the_signing_posture_is_stated_rather_than_implied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    posture = signing_posture()

    assert posture["configured"] is False
    assert "presence marker only" in posture["summary"]
    assert PLUGIN_SIGNING_KEY_ENV in posture["remediation"]

    monkeypatch.setenv(PLUGIN_SIGNING_KEY_ENV, "owner-key")
    assert signing_posture()["configured"] is True


def test_the_permission_diff_carries_the_signature_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner reads the level beside the permissions, not somewhere else."""
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    plan = plan_plugin_registration(_manifest(signature="signature"))

    assert plan.signature is not None
    assert plan.to_dict()["signature"]["level"] == LEVEL_PRESENT_ONLY
    # And it is not silently hardened: this manifest still installs as it did.
    assert plan.status != "denied"


def test_a_present_only_default_still_installs(monkeypatch: pytest.MonkeyPatch) -> None:
    """The posture is to tell the owner, not to block work that worked today."""
    monkeypatch.delenv(PLUGIN_SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(PLUGIN_ED25519_PUBLIC_KEY_ENV, raising=False)

    plan = plan_plugin_registration(_manifest(signature="signature"))

    assert "no_signature_in_manifest" not in plan.reasons
    assert plan.status == "planned"
