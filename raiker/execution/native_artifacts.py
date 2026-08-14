from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any


class NativeArtifactError(RuntimeError):
    pass


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
