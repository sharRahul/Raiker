"""Verified, recoverable application updates.

Native installers and platform signing identities live in release infrastructure,
but the update boundary is platform independent: verify a signed manifest and
artifact before touching the installation, retain a recovery point, prepare any
migration off to the side, then replace the installed tree by rename.

BUG-44 adds the half in front of that: the **channel**. An installed Raiker reads
a signed index published by ``.github/workflows/release.yml``, finds the entry for
its own target, and refuses everything else — a bad signature, an index for a
platform it is not, a version that is not newer than the one running. Only then
does it fetch, and what it fetches goes straight into
:func:`apply_signed_update`, which verifies again before it moves a single file.

Two refusals are worth naming because they are easy to leave out. A downgrade is
not an update, so an index naming an older version is *no update available*
rather than an install. And an artifact whose build did not actually run platform
signing is refused by default: an unsigned build is a legitimate thing for a
pipeline to produce, and an unacceptable thing for a host to install by itself.
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


@dataclass(frozen=True)
class ChannelUpdate:
    """One target's entry in a verified channel index."""

    channel: str
    version: str
    target: str
    artifact: str
    sha256: str
    manifest: str
    signature: str
    signed: bool
    released_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "version": self.version,
            "target": self.target,
            "artifact": self.artifact,
            "sha256": self.sha256,
            "manifest": self.manifest,
            "signature": self.signature,
            "signed": self.signed,
            "released_at": self.released_at,
        }


def version_key(version: str) -> tuple[int, int, int]:
    """``"1.2.3"`` as something comparable, and a refusal for anything else.

    Deliberately strict. A release channel is not the place to guess what
    ``1.2.3-rc1+local`` should sort against; a version this cannot parse is a
    version this must not act on.
    """
    parts = version.strip().split(".")
    if len(parts) != 3:
        raise UpdateError("release_version_invalid")
    try:
        numbers = tuple(int(part) for part in parts)
    except ValueError:
        raise UpdateError("release_version_invalid") from None
    if any(number < 0 for number in numbers) or any(
        str(number) != part for number, part in zip(numbers, parts, strict=True)
    ):
        raise UpdateError("release_version_invalid")
    return numbers[0], numbers[1], numbers[2]


def read_channel_index(
    index: bytes, signature: bytes, public_key: bytes
) -> dict[str, Any]:
    """Verify the index signature, then its shape. In that order, always."""
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, index)
    except (InvalidSignature, ValueError) as exc:
        raise UpdateError("channel_signature_invalid") from exc
    try:
        parsed = json.loads(index)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("channel_index_invalid") from exc
    if not isinstance(parsed, dict) or parsed.get("schema") != 1 or parsed.get("kind") != "channel":
        raise UpdateError("channel_index_unsupported")
    required = {"schema", "kind", "channel", "version", "released_at", "artifacts"}
    if set(parsed) != required:
        raise UpdateError("channel_index_invalid")
    artifacts = parsed["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise UpdateError("channel_index_invalid")
    for entry in artifacts.values():
        if not isinstance(entry, dict) or set(entry) != {
            "artifact",
            "sha256",
            "manifest",
            "signature",
            "signed",
        }:
            raise UpdateError("channel_index_invalid")
        if not isinstance(entry["signed"], bool) or not all(
            isinstance(entry[field], str) and entry[field].strip()
            for field in ("artifact", "sha256", "manifest", "signature")
        ):
            raise UpdateError("channel_index_invalid")
        for field in ("artifact", "manifest", "signature"):
            name = str(entry[field])
            if Path(name).name != name or name in {".", ".."}:
                raise UpdateError("channel_artifact_name_invalid")
    version_key(str(parsed["version"]))
    return parsed


def select_update(
    *,
    index: bytes,
    signature: bytes,
    public_key: bytes,
    target: str,
    current_version: str,
    require_signed: bool = True,
) -> ChannelUpdate | None:
    """The update this installation should take, or ``None`` if there is none.

    ``None`` means *nothing to do*: the channel is at or behind the running
    version. Anything wrong — a tampered index, no entry for this target, an
    artifact whose build never ran platform signing — raises, because those are
    not "no update", they are a channel that must not be acted on.
    """
    parsed = read_channel_index(index, signature, public_key)
    entry = parsed["artifacts"].get(target)
    if entry is None:
        raise UpdateError("channel_target_unavailable")
    if require_signed and not entry["signed"]:
        raise UpdateError("channel_artifact_unsigned")
    offered = str(parsed["version"])
    if version_key(offered) <= version_key(current_version):
        return None
    return ChannelUpdate(
        channel=str(parsed["channel"]),
        version=offered,
        target=target,
        artifact=str(entry["artifact"]),
        sha256=str(entry["sha256"]),
        manifest=str(entry["manifest"]),
        signature=str(entry["signature"]),
        signed=bool(entry["signed"]),
        released_at=str(parsed["released_at"]),
    )


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


@dataclass(frozen=True)
class RecoveryPoint:
    """A retained previous installation, and what rolling back to it would mean."""

    version: str
    path: Path
    files: int
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "path": str(self.path),
            "files": self.files,
            "bytes": self.bytes,
        }


def recovery_points(recovery_root: str | Path) -> list[RecoveryPoint]:
    """Every version an owner could roll back to, newest-parsable first.

    A directory whose name is not a version is still listed rather than hidden:
    something put it there, and a recovery directory quietly filtered out of the
    only view of recovery directories is the kind of omission that is discovered
    during an incident.
    """
    root = Path(recovery_root)
    if not root.is_dir():
        return []
    points: list[RecoveryPoint] = []
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        files = [path for path in candidate.rglob("*") if path.is_file()]
        points.append(
            RecoveryPoint(
                version=candidate.name,
                path=candidate,
                files=len(files),
                bytes=sum(path.stat().st_size for path in files),
            )
        )

    def order(point: RecoveryPoint) -> tuple[int, tuple[int, int, int], str]:
        try:
            return (0, version_key(point.version), point.version)
        except UpdateError:
            return (1, (0, 0, 0), point.version)

    return sorted(points, key=order, reverse=True)


def roll_back(*, install_root: str | Path, recovery_point: str | Path) -> Path:
    """Put a retained version back, keeping the failed one until the swap holds.

    The same two-rename shape as installing: the current tree is moved aside
    first and restored if the second rename fails, so a rollback cannot be the
    thing that leaves an owner with no installation at all.
    """
    install = Path(install_root).resolve()
    point = Path(recovery_point).resolve()
    if not point.is_dir():
        raise UpdateError("recovery_point_missing")
    if point == install or install in point.parents:
        raise UpdateError("recovery_point_inside_install")

    parent = install.parent
    staging = parent / f".{install.name}.rollback-{uuid.uuid4().hex}"
    failed = parent / f".{install.name}.failed-{uuid.uuid4().hex}"
    try:
        shutil.copytree(point, staging)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("rollback_preparation_failed") from exc

    moved = False
    try:
        if install.exists():
            os.replace(install, failed)
            moved = True
        os.replace(staging, install)
    except OSError as exc:
        if moved and failed.exists() and not install.exists():
            os.replace(failed, install)
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError("rollback_install_failed") from exc
    else:
        shutil.rmtree(failed, ignore_errors=True)
    return install
