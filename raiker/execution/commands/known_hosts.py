"""Owner-profile-specific OpenSSH host-key pin material."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

from raiker.storage.internal_paths import internal_io_path

_HOST = re.compile(r"[A-Za-z0-9.-]{1,253}")
_KEY_TYPE = re.compile(r"(?:ssh-ed25519|ecdsa-sha2-nistp(?:256|384|521)|rsa-sha2-(?:256|512))")


def host_key_fingerprint(public_key: str) -> str:
    parts = public_key.strip().split()
    if len(parts) != 2 or not _KEY_TYPE.fullmatch(parts[0]):
        raise ValueError("ssh_host_key_invalid")
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except ValueError as exc:
        raise ValueError("ssh_host_key_invalid") from exc
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return f"SHA256:{digest}"


def write_profile_known_hosts(
    workspace_root: Path,
    *,
    owner_principal_id: str,
    profile_id: str,
    host: str,
    port: int,
    public_key: str,
    expected_fingerprint: str,
) -> Path:
    if not _HOST.fullmatch(host) or not 1 <= port <= 65535:
        raise ValueError("ssh_destination_invalid")
    actual = host_key_fingerprint(public_key)
    if actual != expected_fingerprint.strip():
        raise ValueError("ssh_host_key_fingerprint_mismatch")
    material = f"{owner_principal_id}\0{profile_id}".encode()
    name = hashlib.sha256(material).hexdigest() + ".known_hosts"
    path = workspace_root / ".raiker" / "remote" / "known_hosts" / name
    io_path = internal_io_path(path)
    io_path.parent.mkdir(parents=True, exist_ok=True)
    marker = host if port == 22 else f"[{host}]:{port}"
    io_path.write_text(f"{marker} {public_key.strip()}\n", encoding="utf-8")
    return io_path
