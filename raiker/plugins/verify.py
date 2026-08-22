from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any

PLUGIN_SIGNING_KEY_ENV = "RAIKER_PLUGIN_SIGNING_KEY"
PLUGIN_ED25519_PUBLIC_KEY_ENV = "RAIKER_PLUGIN_ED25519_PUBLIC_KEY"

# The three states a manifest signature can actually be in (BUG-79). They are
# named because the default install is `present_only`, and an owner who is never
# told that cannot tell a genuinely signed plugin from one carrying the literal
# string "signature".
LEVEL_VERIFIED = "verified"
LEVEL_PRESENT_ONLY = "present_only"
LEVEL_UNSIGNED = "unsigned"

_LEVEL_LABELS = {
    LEVEL_VERIFIED: "Verified",
    LEVEL_PRESENT_ONLY: "Present only",
    LEVEL_UNSIGNED: "Unsigned",
}

_LEVEL_EXPLANATIONS = {
    LEVEL_VERIFIED: (
        "The manifest signature was checked against a key you configured, so the "
        "author is who the manifest says."
    ),
    LEVEL_PRESENT_ONLY: (
        "The manifest carries a signature but no signing key is configured on this "
        "machine, so nothing was checked against an author. The checksum still "
        "proves the manifest is internally consistent — it catches an accidental "
        "edit, not a hostile one."
    ),
    LEVEL_UNSIGNED: "The manifest carries no signature at all.",
}


@dataclass(frozen=True)
class SignatureVerification:
    """What a manifest's signature actually proved, and why.

    Raiker's default install has no owner signing key, which is a deliberate
    local-development baseline rather than an oversight — but an unstated one was
    the defect. This is the statement: the level, the reason code that produced
    it, the method that ran, and the one step that would raise it.
    """

    level: str
    reason: str
    method: str
    ok: bool

    @property
    def label(self) -> str:
        return _LEVEL_LABELS.get(self.level, self.level)

    @property
    def explanation(self) -> str:
        return _LEVEL_EXPLANATIONS.get(self.level, "")

    @property
    def remediation(self) -> str:
        if self.level == LEVEL_VERIFIED:
            return ""
        return (
            f"Set {PLUGIN_SIGNING_KEY_ENV} to your signing key (or "
            f"{PLUGIN_ED25519_PUBLIC_KEY_ENV} to a publisher's public key) and reinstall "
            "to have signatures verified rather than merely present."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "label": self.label,
            "reason": self.reason,
            "method": self.method,
            "verified": self.ok and self.level == LEVEL_VERIFIED,
            "explanation": self.explanation,
            "remediation": self.remediation,
        }


def signature_verification(manifest: dict[str, Any]) -> SignatureVerification:
    """Classify what this manifest's signature proved — never silently harden.

    A `present_only` plugin still installs exactly as it did before: the posture
    at the top of `docs/plans/TO_BE_FIXED.md` is to tell the owner what they have
    and give them the one-step path to a stronger state, not to block an install
    that works today.
    """
    supply_chain = manifest.get("supply_chain") or {}
    asymmetric_ok, asymmetric_reason = verify_plugin_asymmetric_signature(manifest)
    if plugin_ed25519_public_key():
        # An owner-trusted publisher key is the strongest statement available and
        # is authoritative when configured — including when it fails.
        return SignatureVerification(
            level=LEVEL_VERIFIED if asymmetric_ok else LEVEL_UNSIGNED,
            reason=asymmetric_reason,
            method="ed25519",
            ok=asymmetric_ok,
        )
    signature = supply_chain.get("signature")
    if not signature:
        return SignatureVerification(
            level=LEVEL_UNSIGNED,
            reason="no_signature_in_manifest",
            method="none",
            ok=False,
        )
    ok, reason = verify_plugin_signature(manifest)
    if reason == "signature_present":
        return SignatureVerification(
            level=LEVEL_PRESENT_ONLY, reason=reason, method="none", ok=True
        )
    return SignatureVerification(
        level=LEVEL_VERIFIED if ok else LEVEL_UNSIGNED,
        reason=reason,
        method="hmac",
        ok=ok,
    )


def signing_posture() -> dict[str, Any]:
    """The workspace's own signing posture, independent of any one manifest."""
    hmac_key = bool(plugin_signing_key())
    publisher_key = bool(plugin_ed25519_public_key())
    configured = hmac_key or publisher_key
    return {
        "configured": configured,
        "hmac_key_set": hmac_key,
        "publisher_key_set": publisher_key,
        "summary": (
            "Manifest signatures are verified against a key you configured."
            if configured
            else "No signing key is configured, so a manifest signature is a presence "
            "marker only. Installs are unaffected; verification is not."
        ),
        "remediation": (
            ""
            if configured
            else f"Set {PLUGIN_SIGNING_KEY_ENV} (your own key) or "
            f"{PLUGIN_ED25519_PUBLIC_KEY_ENV} (a publisher's public key) before installing."
        ),
    }


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


def plugin_checksum(manifest: dict[str, Any]) -> str:
    """The checksum an owner would compute for *manifest*.

    The counterpart to :func:`expected_plugin_signature`, and exposed for the
    same reason: tooling that prepares a manifest should not have to
    reimplement the canonicalisation, and a second implementation of it is a
    second thing that can disagree with the verifier.
    """
    return hashlib.sha256(_canonical_content(manifest).encode("utf-8")).hexdigest()


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
