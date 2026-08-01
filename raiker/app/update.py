"""Verified, recoverable application updates.

Native installers and platform signing identities live in release infrastructure,
but the update boundary is platform independent: verify a signed manifest and
artifact before touching the installation, retain a recovery point, prepare any
migration off to the side, then replace the installed tree by rename.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class UpdateError(RuntimeError):
    """A stable refusal from the signed-update boundary."""


@dataclass(frozen=True)
class UpdateResult:
    version: str
    installed_at: Path
    recovery_point: Path
    artifact_sha256: str


def _signed_manifest(
    manifest_path: Path, signature_path: Path, public_key: bytes
) -> dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature_path.read_bytes(), manifest_bytes
        )
    except (InvalidSignature, ValueError) as exc:
        raise UpdateError("release_signature_invalid") from exc
    try:
        parsed = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("release_manifest_invalid") from exc
    if not isinstance(parsed, dict) or parsed.get("schema") != 1:
        raise UpdateError("release_manifest_unsupported")
    required = {"schema", "version", "artifact", "sha256"}
    if set(parsed) != required or not all(
        isinstance(parsed.get(field), str) and parsed[field].strip()
        for field in ("version", "artifact", "sha256")
    ):
        raise UpdateError("release_manifest_invalid")
    return parsed


def _verified_digest(bundle: Path, manifest: dict[str, Any]) -> str:
    if str(manifest["artifact"]) != bundle.name:
        raise UpdateError("artifact_name_mismatch")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if digest != str(manifest["sha256"]).lower():
        raise UpdateError("artifact_digest_mismatch")
    return digest


def _safe_extract(bundle: Path, staging: Path) -> None:
    staging.mkdir(parents=True)
    root = staging.resolve()
    try:
        with zipfile.ZipFile(bundle) as archive:
            for info in archive.infolist():
                relative = PurePosixPath(info.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise UpdateError("artifact_path_escape")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise UpdateError("artifact_symlink_not_allowed")
                destination = (staging / Path(*relative.parts)).resolve()
                if destination != root and root not in destination.parents:
                    raise UpdateError("artifact_path_escape")
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except zipfile.BadZipFile as exc:
        raise UpdateError("artifact_archive_invalid") from exc


def _installed_version(install_root: Path) -> str:
    version_file = install_root / "version.txt"
    if not version_file.is_file():
        return "unknown"
    value = version_file.read_text(encoding="utf-8").strip()
    return value or "unknown"


def apply_signed_update(
    *,
    bundle: str | Path,
    manifest: str | Path,
    signature: str | Path,
    public_key: bytes,
    install_root: str | Path,
    recovery_root: str | Path,
    migrate: Callable[[Path], None] | None = None,
) -> UpdateResult:
    """Verify and install one update while preserving the previous version.

    ``migrate`` receives only the staged tree. A failure cannot mutate the live
    installation. The final change is two sibling-directory renames; if the
    second rename fails, the first is immediately rolled back.
    """
    bundle_path = Path(bundle).resolve()
    install = Path(install_root).resolve()
    recoveries = Path(recovery_root).resolve()
    release = _signed_manifest(Path(manifest), Path(signature), public_key)
    digest = _verified_digest(bundle_path, release)
    version = str(release["version"])

    parent = install.parent
    staging = parent / f".{install.name}.staged-{uuid.uuid4().hex}"
    previous = parent / f".{install.name}.previous-{uuid.uuid4().hex}"
    if recoveries == install or install in recoveries.parents:
        raise UpdateError("recovery_root_inside_install")
    installed_version = _installed_version(install)
    if (
        installed_version in {".", ".."}
        or "/" in installed_version
        or "\\" in installed_version
        or Path(installed_version).name != installed_version
    ):
        raise UpdateError("installed_version_invalid")
    recovery = recoveries / installed_version
    if recovery.exists():
        raise UpdateError("recovery_point_already_exists")

    try:
        _safe_extract(bundle_path, staging)
        if install.exists():
            recovery.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(install, recovery)
        if migrate is not None:
            migrate(staging)
    except UpdateError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("update_preparation_failed") from exc

    moved_previous = False
    try:
        if install.exists():
            os.replace(install, previous)
            moved_previous = True
        os.replace(staging, install)
    except OSError as exc:
        if moved_previous and previous.exists() and not install.exists():
            os.replace(previous, install)
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("atomic_install_failed") from exc
    else:
        shutil.rmtree(previous, ignore_errors=True)

    return UpdateResult(
        version=version,
        installed_at=install,
        recovery_point=recovery,
        artifact_sha256=digest,
    )
