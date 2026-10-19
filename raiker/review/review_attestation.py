"""BR-D05 — signed review evidence: a review this Raiker took, provably unchanged.

A stored review is a row in the owner's database. Anything that can write that
row could change a finding, drop one, or claim a review of a patch that was
never reviewed. This signs each review when it is taken, with this
installation's Ed25519 issuer key — the key that already signs per-turn machine
identities and subagent delegations — and checks the signature every time the
review is read.

What is signed is a digest of the review itself (every field except the
attestation), bound to the owner, the repository, the patch fingerprint and
what kind of review it is. So the signature says: *this installation took this
review of this exact patch for this owner, and it has not been changed since.*

It is evidence and never authority. A valid signature grants nothing, and an
invalid one blocks nothing — the review is shown with its state named so the
owner can decide what to trust. The private key never leaves the encrypted
store and is never written into the review, a prompt or an event.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from raiker.contracts.ids import utc_now

ATTESTATION_VERSION = 1
ATTESTATION_AUDIENCE = "raiker.patch_review"

AttestationState = Literal["verified", "invalid", "unknown_key", "unsigned"]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def review_digest(review: Mapping[str, Any]) -> str:
    """SHA-256 over the review as stored, without its attestation."""
    body = {key: value for key, value in review.items() if key != "attestation"}
    return hashlib.sha256(_canonical(body)).hexdigest()


def _claims(*, owner_principal_id: str, repo_id: str, kind: str, review: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": ATTESTATION_VERSION,
        "audience": ATTESTATION_AUDIENCE,
        "owner_principal_id": owner_principal_id,
        "repo_id": repo_id,
        "kind": kind,
        "fingerprint": str(review.get("fingerprint") or ""),
        "review_digest": review_digest(review),
    }


def _issuer_key(workspace_root: str | Path, store: Any) -> dict[str, Any]:
    from raiker.runtime.identity.issuer import WorkspaceIdentityIssuer

    return WorkspaceIdentityIssuer(workspace_root, store).issuer_key()


def attest_review(
    workspace_root: str | Path,
    store: Any,
    *,
    owner_principal_id: str,
    repo_id: str,
    kind: Literal["patch", "model"],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    """*review* with an ``attestation`` from this installation's issuer key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from raiker.auth.app_key import app_fernet

    key = _issuer_key(workspace_root, store)
    claims = _claims(owner_principal_id=owner_principal_id, repo_id=repo_id, kind=kind, review=review)
    seed = app_fernet(Path(workspace_root).resolve()).decrypt(bytes(key["private_key_encrypted"]))
    signature = Ed25519PrivateKey.from_private_bytes(seed).sign(_canonical(claims))
    return {
        **dict(review),
        "attestation": {
            "version": ATTESTATION_VERSION,
            "kind": kind,
            "key_id": str(key["key_id"]),
            "review_digest": claims["review_digest"],
            "signature": signature.hex(),
            "signed_at": utc_now(),
        },
    }


def verify_review(
    store: Any, *, owner_principal_id: str, repo_id: str, review: Mapping[str, Any]
) -> AttestationState:
    """Whether *review* is exactly what this installation signed for this owner and repository."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    attestation = review.get("attestation")
    if not isinstance(attestation, Mapping):
        return "unsigned"
    kind = str(attestation.get("kind") or "")
    if kind not in {"patch", "model"} or attestation.get("version") != ATTESTATION_VERSION:
        return "invalid"
    try:
        key = store.get_machine_issuer_key(str(attestation.get("key_id") or ""))
    except Exception:  # noqa: BLE001 — an unreadable key proves nothing
        key = None
    if key is None:
        return "unknown_key"
    claims = _claims(owner_principal_id=owner_principal_id, repo_id=repo_id, kind=kind, review=review)
    if claims["review_digest"] != attestation.get("review_digest"):
        return "invalid"
    try:
        signature = bytes.fromhex(str(attestation.get("signature") or ""))
        Ed25519PublicKey.from_public_bytes(bytes(key["public_key"])).verify(signature, _canonical(claims))
    except (InvalidSignature, ValueError):
        return "invalid"
    return "verified"


def public_attestation(review: Mapping[str, Any] | None, state: AttestationState) -> dict[str, Any] | None:
    """What the owner is shown: the state, key id and time — never the signature bytes."""
    if review is None:
        return None
    attestation = review.get("attestation")
    if not isinstance(attestation, Mapping):
        return {"state": state, "key_id": None, "signed_at": None}
    return {
        "state": state,
        "key_id": str(attestation.get("key_id") or "") or None,
        "signed_at": str(attestation.get("signed_at") or "") or None,
    }


__all__ = ["attest_review", "public_attestation", "review_digest", "verify_review"]
