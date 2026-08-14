from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from raiker.execution.native_artifacts import (
    NativeArtifactError,
    resolve_native_artifact,
)


def _package(tmp_path: Path, *, protocol: int = 1) -> tuple[Path, Path]:
    package_root = tmp_path / "package"
    platform_root = package_root / "native" / "win32-x86_64"
    platform_root.mkdir(parents=True)
    artifact = platform_root / "raiker-command-runner.exe"
    artifact.write_bytes(b"signed-runner-fixture")
    manifest = {
        "schema_version": 1,
        "platform": "win32-x86_64",
        "protocol_version": protocol,
        "publisher": "CN=Raiker Test",
        "artifacts": {
            artifact.name: {
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "publisher": "CN=Raiker Test",
            }
        },
    }
    (platform_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return package_root, artifact


def test_packaged_native_artifact_requires_manifest_digest_publisher_and_protocol(
    tmp_path: Path,
) -> None:
    package_root, artifact = _package(tmp_path)
    resolved = resolve_native_artifact(
        package_root,
        platform_tag="win32-x86_64",
        artifact_name="raiker-command-runner.exe",
        expected_protocol=1,
        expected_publisher="CN=Raiker Test",
    )
    assert resolved == artifact.resolve()


def test_tampered_or_wrong_protocol_artifact_fails_closed(tmp_path: Path) -> None:
    package_root, artifact = _package(tmp_path)
    artifact.write_bytes(b"tampered")
    with pytest.raises(NativeArtifactError, match="native_artifact_digest_mismatch"):
        resolve_native_artifact(
            package_root,
            platform_tag="win32-x86_64",
            artifact_name=artifact.name,
            expected_protocol=1,
            expected_publisher="CN=Raiker Test",
        )

    other_root, other = _package(tmp_path / "other", protocol=2)
    with pytest.raises(NativeArtifactError, match="native_artifact_protocol_mismatch"):
        resolve_native_artifact(
            other_root,
            platform_tag="win32-x86_64",
            artifact_name=other.name,
            expected_protocol=1,
            expected_publisher="CN=Raiker Test",
        )


def test_missing_manifest_or_publisher_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(NativeArtifactError, match="native_artifact_manifest_missing"):
        resolve_native_artifact(
            tmp_path,
            platform_tag="win32-x86_64",
            artifact_name="runner.exe",
            expected_protocol=1,
            expected_publisher="CN=Raiker Test",
        )
