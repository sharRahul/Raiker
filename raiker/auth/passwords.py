"""Password hashing for local accounts.

Primary: Argon2id (argon2-cffi) with the spec-mandated parameters
(19 MiB memory, 2 iterations, 1 degree of parallelism). Fallback: scrypt
(n=2**17, r=8, p=1) when argon2-cffi is unavailable. Encoded hashes are
self-describing, so verification re-derives the parameters from the string.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

try:  # pragma: no cover - import guard exercised by environment, not tests
    from argon2 import PasswordHasher
    from argon2 import exceptions as _argon2_exc

    _PH = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
    ARGON2_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import/runtime failure means fall back to scrypt
    ARGON2_AVAILABLE = False

# scrypt cost parameters (spec §5 fallback).
_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def _scrypt_maxmem(n: int, r: int) -> int:
    # scrypt needs ~128 * N * r bytes; OpenSSL's default cap (32 MiB) is too low
    # for N=2**17. Grant the exact requirement plus a 1 MiB margin.
    return 128 * n * r + (1 << 20)
# A pre-computed scrypt hash of a random string, used to spend comparable work
# when an account does not exist (defeats username enumeration by timing).
_DUMMY_SALT = secrets.token_bytes(16)


def _scrypt_hash(password: str, salt: bytes) -> str:
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_scrypt_maxmem(_SCRYPT_N, _SCRYPT_R),
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(derived).decode('ascii')}"
    )


def hash_password(password: str) -> tuple[str, str]:
    """Return (encoded_hash, algo). algo is 'argon2id' or 'scrypt'."""
    if ARGON2_AVAILABLE:
        return _PH.hash(password), "argon2id"
    return _scrypt_hash(password, secrets.token_bytes(16)), "scrypt"


def _verify_scrypt(password: str, encoded: str) -> bool:
    try:
        _tag, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(base64.b64decode(hash_b64)),
            maxmem=_scrypt_maxmem(int(n), int(r)),
        )
        return hmac.compare_digest(derived, base64.b64decode(hash_b64))
    except Exception:  # noqa: BLE001 - malformed hash is a failed verify, never an error
        return False


def verify_password(password: str, encoded: str, algo: str) -> bool:
    if algo == "argon2id" and ARGON2_AVAILABLE:
        try:
            return _PH.verify(encoded, password)
        except _argon2_exc.VerificationError:
            return False
        except Exception:  # noqa: BLE001 - malformed hash is a failed verify
            return False
    if algo == "scrypt" or encoded.startswith("scrypt$"):
        return _verify_scrypt(password, encoded)
    return False


def spend_dummy_verify(password: str) -> None:
    """Run a hash to equalize timing for a nonexistent account."""
    _scrypt_hash(password, _DUMMY_SALT)


def needs_rehash(encoded: str, algo: str) -> bool:
    """True when the stored hash should be upgraded (scrypt -> argon2id)."""
    if ARGON2_AVAILABLE and algo != "argon2id":
        return True
    if algo == "argon2id" and ARGON2_AVAILABLE:
        try:
            return bool(_PH.check_needs_rehash(encoded))
        except Exception:  # noqa: BLE001
            return False
    return False
