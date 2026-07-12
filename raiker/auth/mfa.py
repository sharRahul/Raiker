"""Time-based one-time password (TOTP) multi-factor authentication.

TOTP is fully local: no network, no external provider. The TOTP seed is encrypted
at rest with the internal app key (``app_key``), never the connector vault key, so
MFA works whether or not a connector vault has been configured. SMS and email
factors are intentionally out of scope.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

import pyotp

from raiker.auth.app_key import app_fernet

_ISSUER = "Raiker"


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, username: str, issuer: str = _ISSUER) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    try:
        return bool(pyotp.TOTP(secret).verify(code, valid_window=valid_window))
    except Exception:  # noqa: BLE001 - malformed code is a failed verify
        return False


def encrypt_secret(workspace_root: str | Path, secret: str) -> bytes:
    return app_fernet(workspace_root).encrypt(secret.encode("utf-8"))


def decrypt_secret(workspace_root: str | Path, blob: bytes) -> str:
    return app_fernet(workspace_root).decrypt(bytes(blob)).decode("utf-8")


def generate_backup_codes(n: int = 10) -> list[str]:
    return [secrets.token_hex(4) for _ in range(n)]


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def hash_backup_codes(codes: list[str]) -> str:
    return json.dumps([_hash_code(c) for c in codes])


def consume_backup_code(hashed_json: str, code: str) -> tuple[bool, str]:
    """Return (accepted, updated_hashed_json). A matched code is removed."""
    try:
        hashes = list(json.loads(hashed_json))
    except (ValueError, TypeError):
        return False, hashed_json
    target = _hash_code(code)
    if target not in hashes:
        return False, hashed_json
    hashes.remove(target)
    return True, json.dumps(hashes)
