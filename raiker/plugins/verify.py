from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

PLUGIN_SIGNING_KEY_ENV = "RAIKER_PLUGIN_SIGNING_KEY"
PLUGIN_ED25519_PUBLIC_KEY_ENV = "RAIKER_PLUGIN_ED25519_PUBLIC_KEY"


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


def plugin_ed25519_public_key() -> str:
    """Owner-trusted Ed25519 PUBLIC key (hex) used to verify supply-chain signatures.

    Read from ``RAIKER_PLUGIN_ED25519_PUBLIC_KEY``. When unset (default),
    asymmetric verification is skipped and the checksum/HMAC behaviour is
    unchanged. When set, the manifest ``supply_chain.ed25519_signature`` must be a
    valid Ed25519 signature (hex) over the canonical manifest body, verified
    against this public key, or the install fails closed.

    Unlike the symmetric HMAC key, this is a *public* key: the owner never holds
    the author's private key, so a trusted third party (plugin publisher) can sign
    manifests off-machine and Raiker only needs the publisher's public key to
    verify authenticity — an asymmetric supply-chain trust model.
    """
    return os.environ.get(PLUGIN_ED25519_PUBLIC_KEY_ENV, "")


def ed25519_signature_hex(manifest: dict[str, Any], private_key_hex: str) -> str:
    """Hex Ed25519 signature an author computes over *manifest* with their seed.

    ``private_key_hex`` is the 32-byte Ed25519 private seed encoded as hex. Signs
    the same canonical content the checksum and HMAC signature cover (manifest
    minus its ``supply_chain`` block). Exposed so authors/tooling can produce a
    manifest signature without reimplementing the canonicalisation; the private
    key stays with the author and is never read by Raiker's verify path.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    content = _canonical_content(manifest)
    return private_key.sign(content.encode("utf-8")).hex()


def verify_plugin_asymmetric_signature(manifest: dict[str, Any]) -> tuple[bool, str]:
    """Verify the manifest's Ed25519 signature against the owner-trusted public key.

    Fail-closed contract: when ``RAIKER_PLUGIN_ED25519_PUBLIC_KEY`` is unset the
    check is skipped (``asymmetric_not_configured``) so existing manifests are
    unaffected. When it is set, a missing/non-string ``ed25519_signature``, a
    malformed public key or signature, an unavailable crypto backend, or a
    signature that does not verify all fail closed with a distinct reason and no
    install record is written.
    """
    public_key_hex = plugin_ed25519_public_key()
    if not public_key_hex:
        return True, "asymmetric_not_configured"
    supply_chain = manifest.get("supply_chain") or {}
    signature = supply_chain.get("ed25519_signature")
    if not signature or not isinstance(signature, str):
        return False, "no_asymmetric_signature_in_manifest"
    try:
        public_key_bytes = bytes.fromhex(public_key_hex)
    except ValueError:
        return False, "asymmetric_public_key_invalid"
    if len(public_key_bytes) != 32:
        return False, "asymmetric_public_key_invalid"
    try:
        signature_bytes = bytes.fromhex(signature)
    except ValueError:
        return False, "asymmetric_signature_invalid"
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except BaseException:
        # Crypto backend unavailable in this environment: fail closed, never open.
        return False, "asymmetric_backend_unavailable"
    content = _canonical_content(manifest)
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            signature_bytes, content.encode("utf-8")
        )
    except InvalidSignature:
        return False, "asymmetric_signature_invalid"
    except Exception:
        return False, "asymmetric_backend_unavailable"
    return True, "asymmetric_signature_verified"


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
    asym_ok, asym_reason = verify_plugin_asymmetric_signature(manifest)
    if not asym_ok:
        reasons.append(asym_reason)
    return reasons
