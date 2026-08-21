"""Exact-file Windows Authenticode publisher verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class AuthenticodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthenticodeVerdict:
    publisher: str
    leaf_spki_sha256: str
    timestamp_certificate_validity: tuple[str, str]
    status: str = "publisher_verified"


_SCRIPT = r"""
$s = Get-AuthenticodeSignature -LiteralPath $args[0]
$leaf = $s.SignerCertificate
$time = $s.TimeStamperCertificate
[pscustomobject]@{
  status = [string]$s.Status
  publisher = [string]$leaf.Subject
  leaf_spki = [Convert]::ToBase64String($leaf.PublicKey.EncodedKeyValue.RawData)
  timestamp_subject = [string]$time.Subject
  timestamp_not_before = $time.NotBefore.ToUniversalTime().ToString('o')
  timestamp_not_after = $time.NotAfter.ToUniversalTime().ToString('o')
} | ConvertTo-Json -Compress
""".strip()


def verify_windows_authenticode(
    artifact: Path,
    *,
    expected_publisher: str,
    expected_leaf_spki_sha256: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> AuthenticodeVerdict:
    resolved = artifact.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise AuthenticodeError("authenticode_artifact_invalid")
    try:
        completed = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT, str(resolved)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        value = json.loads(completed.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise AuthenticodeError("authenticode_verification_unavailable") from exc
    if completed.returncode != 0 or value.get("status") != "Valid":
        raise AuthenticodeError("authenticode_chain_or_revocation_invalid")
    if value.get("publisher") != expected_publisher:
        raise AuthenticodeError("authenticode_publisher_mismatch")
    try:
        import base64

        spki = hashlib.sha256(base64.b64decode(value["leaf_spki"], validate=True)).hexdigest()
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticodeError("authenticode_spki_invalid") from exc
    if spki != expected_leaf_spki_sha256.casefold():
        raise AuthenticodeError("authenticode_spki_mismatch")
    if not value.get("timestamp_subject") or not value.get("timestamp_not_before") or not value.get("timestamp_not_after"):
        raise AuthenticodeError("authenticode_timestamp_missing")
    return AuthenticodeVerdict(
        expected_publisher,
        spki,
        (str(value["timestamp_not_before"]), str(value["timestamp_not_after"])),
    )
