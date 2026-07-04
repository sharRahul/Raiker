from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

PLUGIN_SIGNING_KEY_ENV = "RAIKER_PLUGIN_SIGNING_KEY"


def plugin_signing_key() -> str:
    """Owner-held symmetric key used to verify plugin manifest signatures.

    Read from ``RAIKER_PLUGIN_SIGNING_KEY``. When unset (default), signatures
    are treated as presence markers only (local-dev baseline, unchanged). When
    set, the manifest ``signature`` must be a valid HMAC-SHA256 over the
    canonical manifest content or the install fails closed.
    """
    return os.environ.get(PLUGIN_SIGNING_KEY_ENV, "")


def expected_plugin_signature(manifest: dict[str, Any], key: str) -> str:
    """Deterministic HMAC-SHA256 signature an owner would compute for *manifest*.

    Signs the same canonical content the checksum covers (manifest minus its
    ``supply_chain`` block), so the signature authenticates the exact reviewed
    manifest body. Exposed so owners/tooling can produce a signature without
    reimplementing the canonicalisation.
    """
    content = _canonical_content(manifest)
    return hmac.new(key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_plugin_checksum(manifest: dict[str, Any]) -> tuple[bool, str]:
    supply_chain = manifest.get("supply_chain") or {}
    checksum = supply_chain.get("checksum")
    if not checksum:
        return False, "no_checksum_in_manifest"
    content = _canonical_content(manifest)
    computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if computed == checksum:
        return True, "checksum_verified"
    return False, f"checksum_mismatch:expected={checksum}:computed={computed}"


def verify_plugin_signature(manifest: dict[str, Any]) -> tuple[bool, str]:
    supply_chain = manifest.get("supply_chain") or {}
    signature = supply_chain.get("signature")
    if not signature:
        return False, "no_signature_in_manifest"
    key = plugin_signing_key()
    if not key:
        # No owner signing key configured: presence marker only (local dev).
        return True, "signature_present"
    if not isinstance(signature, str):
        return False, "signature_invalid"
    expected = expected_plugin_signature(manifest, key)
    if hmac.compare_digest(signature, expected):
        return True, "signature_verified"
    return False, "signature_invalid"


def _canonical_content(manifest: dict[str, Any]) -> str:
    import json
    clean = {k: v for k, v in manifest.items() if k != "supply_chain"}
    return json.dumps(clean, sort_keys=True, separators=(",", ":"))


def validate_supply_chain(manifest: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    checksum_ok, checksum_reason = verify_plugin_checksum(manifest)
    if not checksum_ok:
        reasons.append(checksum_reason)
    sig_ok, sig_reason = verify_plugin_signature(manifest)
    if not sig_ok:
        reasons.append(sig_reason)
    return reasons
