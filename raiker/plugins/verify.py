from __future__ import annotations

import hashlib
from typing import Any


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
    return True, "signature_present"


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
