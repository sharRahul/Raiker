from __future__ import annotations

import hashlib
import json
import secrets
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class NativeArtifactError(RuntimeError):
    pass


class NativeTrustPosture(StrEnum):
    PUBLISHER_VERIFIED = "publisher_verified"
    PACKAGE_RELATIVE = "package_relative_integrity"
    DEVELOPMENT_UNVERIFIED = "development_unverified"


@dataclass(frozen=True)
class VerifiedNativeArtifact:
    path: Path
    posture: NativeTrustPosture
    manifest_digest: str


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise NativeArtifactError("native_artifact_manifest_missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeArtifactError("native_artifact_manifest_invalid") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise NativeArtifactError("native_artifact_manifest_invalid")
    return value


def resolve_native_artifact(
    package_root: str | Path,
    *,
    platform_tag: str,
    artifact_name: str,
    expected_protocol: int,
    expected_publisher: str,
) -> Path:
    """Resolve an installed helper only after all immutable pins agree."""
    if not platform_tag or any(part in platform_tag for part in ("/", "\\", "..")):
        raise NativeArtifactError("native_artifact_platform_invalid")
    if not artifact_name or Path(artifact_name).name != artifact_name:
        raise NativeArtifactError("native_artifact_name_invalid")
    root = Path(package_root).resolve()
    platform_root = (root / "native" / platform_tag).resolve()
    if root not in platform_root.parents:
        raise NativeArtifactError("native_artifact_platform_invalid")
    manifest = _load_manifest(platform_root / "manifest.json")
    if manifest.get("platform") != platform_tag:
        raise NativeArtifactError("native_artifact_platform_mismatch")
    if manifest.get("protocol_version") != expected_protocol:
        raise NativeArtifactError("native_artifact_protocol_mismatch")
    if manifest.get("publisher") != expected_publisher:
        raise NativeArtifactError("native_artifact_publisher_mismatch")
    artifacts = manifest.get("artifacts")
    record = artifacts.get(artifact_name) if isinstance(artifacts, dict) else None
    if not isinstance(record, dict):
        raise NativeArtifactError("native_artifact_manifest_entry_missing")
    if record.get("publisher") != expected_publisher:
        raise NativeArtifactError("native_artifact_publisher_mismatch")
    artifact = (platform_root / artifact_name).resolve()
    if platform_root not in artifact.parents or not artifact.is_file() or artifact.is_symlink():
        raise NativeArtifactError("native_artifact_missing")
    expected_digest = str(record.get("sha256") or "").casefold()
    if len(expected_digest) != 64:
        raise NativeArtifactError("native_artifact_digest_invalid")
    actual_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if not secrets.compare_digest(actual_digest, expected_digest):
        raise NativeArtifactError("native_artifact_digest_mismatch")
    return artifact


def verify_signed_native_artifact(
    package_root: str | Path,
    *,
    platform_tag: str,
    artifact_name: str,
    expected_protocol: int,
    expected_publisher: str,
    public_key: bytes | None = None,
    trust_key_path: Path | None = None,
    launcher_path: Path | None = None,
) -> VerifiedNativeArtifact:
    """Verify artifact integrity and classify where its trust anchor lives.

    A package-local manifest without an external public key is intentionally
    only package-relative integrity.  Publisher verification on POSIX requires
    both the key and launcher outside the writable package tree, owned by root,
    and not group/other writable.
    """
    artifact = resolve_native_artifact(
        package_root,
        platform_tag=platform_tag,
        artifact_name=artifact_name,
        expected_protocol=expected_protocol,
        expected_publisher=expected_publisher,
    )
    manifest = artifact.parent / "manifest.json"
    manifest_bytes = manifest.read_bytes()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    signature = manifest.with_suffix(".json.sig")
    if public_key is None:
        return VerifiedNativeArtifact(
            artifact, NativeTrustPosture.PACKAGE_RELATIVE, manifest_digest
        )
    if not signature.is_file() or signature.is_symlink():
        raise NativeArtifactError("native_artifact_signature_missing")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature.read_bytes(), manifest_bytes
        )
    except (InvalidSignature, ValueError, OSError) as exc:
        raise NativeArtifactError("native_artifact_signature_invalid") from exc
    if trust_key_path is not None or launcher_path is not None:
        if trust_key_path is None or launcher_path is None:
            raise NativeArtifactError("native_artifact_trust_anchor_incomplete")
        root = Path(package_root).resolve()
        _verify_posix_anchor(trust_key_path, root, "native_artifact_trust_key_unsafe")
        _verify_posix_anchor(launcher_path, root, "native_artifact_launcher_unsafe")
    return VerifiedNativeArtifact(
        artifact, NativeTrustPosture.PUBLISHER_VERIFIED, manifest_digest
    )


def _verify_posix_anchor(path: Path, package_root: Path, reason: str) -> None:
    resolved = path.resolve()
    if (
        not resolved.is_file()
        or resolved.is_symlink()
        or resolved == package_root
        or package_root in resolved.parents
    ):
        raise NativeArtifactError(reason)
    info = resolved.stat()
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise NativeArtifactError(reason)
