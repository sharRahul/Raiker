"""The desktop release: what an owner downloads, installs and updates.

DIST-01 (docs/adr/ADR-0003-desktop-distribution.md). The release pipeline in
:mod:`raiker.app.release` builds a reproducible *payload* — the service, the web
assets and that platform's wheels. Installing that payload needs a Python on the
owner's machine, so it is not what an ordinary owner should be handed. The
desktop package is: the Electron window (``desktop/``) with the host frozen
inside it by PyInstaller, so the machine needs nothing else.

This module is that package as data, the same way ``release.py`` is the payload
as data:

* :data:`DESKTOP_TARGETS` — every platform and architecture, its native runner,
  the installers electron-builder produces there, and the one the signed updater
  replaces an installation with;
* :func:`artifact_names` — the published filenames, which say the product,
  version, OS and architecture. Whether a build was signed is recorded inside
  it (``signing.applied`` in ``installation.json``) and in its manifest, not in
  its filename, so a signed and an unsigned build of one target share a name;
* :data:`RELEASE_ASSETS` / :func:`release_asset_names` — the one installer per
  platform a draft GitHub release carries;
* :func:`desktop_record` — the ``installation.json`` written beside the frozen
  host, so the running product reports what it is;
* :func:`write_manifests` / :func:`build_desktop_channel` — the schema-1
  manifests and the signed ``desktop-<channel>.json`` index, in exactly the
  format :mod:`raiker.app.update` already verifies.

The two indexes are separate on purpose. A payload installation and a desktop
installation of the same target replace themselves with different files, and an
index that mixed them would let one be offered the other's artifact.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.app.release import (
    _APPLE,
    _AUTHENTICODE,
    _LINUX,
    ReleaseArtifact,
    ReleaseError,
    ReleaseTarget,
    _canonical,
    _validate_version,
    build_channel_index,
    installation_record,
    sign,
)

#: What ``installation.json`` says when it describes a desktop package.
DISTRIBUTION = "desktop"
#: The signed index a desktop installation reads, beside the payload's own.
CHANNEL_PREFIX = "desktop-"


@dataclass(frozen=True)
class DesktopTarget:
    """One platform the desktop package is built for, on its own runner."""

    target: ReleaseTarget
    #: electron-builder's platform and architecture switches for this target.
    builder_args: tuple[str, ...]
    #: The format the signed updater replaces an installation with.
    update_format: str

    @property
    def target_id(self) -> str:
        return self.target.target_id

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.target.to_dict(),
            "builder_args": list(self.builder_args),
            "update_format": self.update_format,
        }


def _target(
    target_id: str,
    os_name: str,
    arch: str,
    runner: str,
    formats: tuple[str, ...],
    builder_args: tuple[str, ...],
    update_format: str,
) -> DesktopTarget:
    signing = {"macos": _APPLE, "windows": _AUTHENTICODE, "linux": _LINUX}[os_name]
    return DesktopTarget(
        ReleaseTarget(target_id, os_name, arch, runner, formats, signing),
        builder_args,
        update_format,
    )


#: Every desktop platform, built and smoke-tested on that platform's own runner:
#: a package built elsewhere is not evidence about the machine it targets.
#:
#: Windows on Arm has no native target: `cryptography` publishes no win_arm64
#: wheel, so the frozen host cannot be built there. Windows 11 on Arm runs the
#: x86-64 package under its built-in emulation, and `desktop-package.yml`
#: installs and tests exactly that on an Arm runner.
DESKTOP_TARGETS: tuple[DesktopTarget, ...] = (
    _target("windows-x86_64", "windows", "x86_64", "windows-2022",
            ("-setup.exe", ".msi"), ("--win", "--x64"), "-setup.exe"),
    _target("macos-arm64", "macos", "arm64", "macos-14",
            (".dmg", ".zip"), ("--mac", "--arm64"), ".zip"),
    _target("linux-x86_64", "linux", "x86_64", "ubuntu-22.04",
            (".AppImage", ".deb", ".rpm"), ("--linux", "--x64"), ".AppImage"),
    _target("linux-arm64", "linux", "arm64", "ubuntu-22.04-arm",
            (".AppImage", ".deb", ".rpm"), ("--linux", "--arm64"), ".AppImage"),
)
DESKTOP_TARGETS_BY_ID: dict[str, DesktopTarget] = {t.target_id: t for t in DESKTOP_TARGETS}


def desktop_target(target_id: str) -> DesktopTarget:
    try:
        return DESKTOP_TARGETS_BY_ID[target_id]
    except KeyError:
        raise ReleaseError("release_target_unknown") from None


def current_desktop_target() -> DesktopTarget | None:
    """The desktop target this machine builds, or ``None`` if it is not one."""
    systems = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    machines = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}
    os_name = systems.get(platform.system())
    arch = machines.get(platform.machine().lower())
    for target in DESKTOP_TARGETS:
        if target.target.os_name == os_name and target.target.arch == arch:
            return target
    return None


def suffix(*, signed: bool) -> str:  # noqa: ARG001 — kept for the build environment's contract
    """The filename suffix for a build: none, signed or not.

    Signing state lives in the installed record and the signed manifest. The
    owner's decision (2026-10-19) was that a release's files are named for the
    platform alone, so the suffix is empty for both.
    """
    return ""


def artifact_names(version: str, target_id: str, *, signed: bool) -> dict[str, str]:
    """Each installer's published filename, keyed by its format.

    These are the names ``desktop/electron-builder.yml`` produces when the build
    script sets ``RAIKER_TARGET`` and ``RAIKER_ARTIFACT_SUFFIX``; the two are
    kept together by ``tests/test_desktop_release.py``.
    """
    target = desktop_target(target_id)
    tail = suffix(signed=signed)
    names: dict[str, str] = {}
    for fmt in target.target.installer_formats:
        if fmt == "-setup.exe":
            names[fmt] = f"Raiker-{version}-{target_id}-setup{tail}.exe"
        else:
            names[fmt] = f"Raiker-{version}-{target_id}{tail}{fmt}"
    return names


#: The single installer each platform's download is, in the order a release
#: lists them. Windows on Arm has no native host (see :data:`DESKTOP_TARGETS`):
#: its download is the x86-64 setup program, installed, smoke-tested and
#: uninstalled on a Windows on Arm runner and published under its own name.
RELEASE_ASSETS: tuple[tuple[str, str, str], ...] = (
    # (platform shown to the owner, target the file comes from, its format)
    ("windows-x86_64", "windows-x86_64", "-setup.exe"),
    ("windows-arm64", "windows-x86_64", "-setup.exe"),
    ("macos-arm64", "macos-arm64", ".dmg"),
    ("linux-x86_64", "linux-x86_64", ".AppImage"),
    ("linux-arm64", "linux-arm64", ".AppImage"),
)


def release_asset_names(version: str) -> dict[str, tuple[str, str]]:
    """``{published name: (built name, platform)}`` for every release asset.

    One file per platform. The built name is what the platform's runner
    produced; the published name says the platform the owner downloads it for.
    """
    _validate_version(version)
    assets: dict[str, tuple[str, str]] = {}
    for platform_id, source_target, fmt in RELEASE_ASSETS:
        built = artifact_names(version, source_target, signed=True)[fmt]
        if fmt == "-setup.exe":
            published = f"Raiker-{version}-{platform_id}-setup.exe"
        else:
            published = f"Raiker-{version}-{platform_id}{fmt}"
        assets[published] = (built, platform_id)
    return assets


def update_artifact_name(version: str, target_id: str, *, signed: bool) -> str:
    target = desktop_target(target_id)
    return artifact_names(version, target_id, signed=signed)[target.update_format]


def desktop_record(
    *,
    version: str,
    target_id: str,
    channel: str,
    signed: bool,
    commit: str | None = None,
    update_channel: dict[str, str] | None = None,
) -> dict[str, Any]:
    """``installation.json`` for a desktop package.

    The payload record, with ``distribution`` saying which updater index this
    installation reads and ``signing.applied`` exactly as true as the build was.

    ``update_channel`` is the publisher's signed desktop channel — its URL and
    the release public key — so an owner can check for updates from Settings
    without pinning one in a terminal. It is read only when the owner has not
    pinned a channel of their own, and nothing is fetched until they press
    *Check for updates*.
    """
    record = installation_record(
        version=version,
        target=desktop_target(target_id).target,
        channel=channel,
        signed=signed,
        commit=commit,
    )
    record["distribution"] = DISTRIBUTION
    if update_channel:
        record["update_channel"] = dict(update_channel)
    return record


def write_record(host_dir: Path, record: dict[str, Any]) -> Path:
    """Place the record beside the frozen host, where the product looks first."""
    path = host_dir / "installation.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifests(
    directory: Path,
    *,
    version: str,
    target_id: str,
    signed: bool,
    channel: str = "stable",
    private_key: bytes | None = None,
) -> list[ReleaseArtifact]:
    """A schema-1 manifest (and, with a key, its signature) for each installer.

    The manifest is the four fields :func:`raiker.app.update._signed_manifest`
    accepts, so the desktop updater verifies a downloaded installer with the code
    that already verifies a payload. A missing installer is a refusal: a target
    that built only some of its formats is not a release.
    """
    _validate_version(version)
    artifacts: list[ReleaseArtifact] = []
    for name in artifact_names(version, target_id, signed=signed).values():
        path = directory / name
        if not path.is_file():
            raise ReleaseError(f"desktop_artifact_missing:{name}")
        digest = sha256_file(path)
        manifest = {"schema": 1, "version": version, "artifact": name, "sha256": digest}
        manifest_path = directory / f"{name}.manifest.json"
        manifest_bytes = _canonical(manifest)
        manifest_path.write_bytes(manifest_bytes)
        signature_path: Path | None = None
        if private_key is not None:
            signature_path = directory / f"{name}.manifest.json.sig"
            signature_path.write_bytes(sign(manifest_bytes, private_key))
        artifacts.append(
            ReleaseArtifact(
                path=path,
                sha256=digest,
                version=version,
                target_id=target_id,
                channel=channel,
                signed=signed,
                manifest_path=manifest_path,
                signature_path=signature_path,
            )
        )
    return artifacts


def write_checksums(directory: Path, names: list[str], *, name: str = "SHA256SUMS") -> Path:
    """Checksums in the format ``sha256sum --check`` reads."""
    lines = [f"{sha256_file(directory / item)}  {item}" for item in sorted(names)]
    path = directory / name
    # LF on every platform: `sha256sum --check` reads a CRLF line's name with
    # the carriage return on it and reports the file missing (found on Windows).
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def update_artifacts(directory: Path, version: str) -> list[ReleaseArtifact]:
    """The one updater artifact per target found in *directory*, with its manifest."""
    found: list[ReleaseArtifact] = []
    for target in DESKTOP_TARGETS:
        name = update_artifact_name(version, target.target_id, signed=True)
        path = directory / name
        if path.is_file():
            manifest_path = directory / f"{name}.manifest.json"
            signature_path = directory / f"{name}.manifest.json.sig"
            if not manifest_path.is_file() or not signature_path.is_file():
                raise ReleaseError("release_manifest_missing")
            found.append(
                ReleaseArtifact(
                    path=path,
                    sha256=sha256_file(path),
                    version=version,
                    target_id=target.target_id,
                    channel="",
                    # A manifest signature is required just above, so an
                    # artifact listed here is one the signed channel can carry.
                    signed=True,
                    manifest_path=manifest_path,
                    signature_path=signature_path,
                )
            )
    return found


def build_desktop_channel(
    directory: Path,
    *,
    version: str,
    channel: str,
    private_key: bytes | None,
    notes: str | None = None,
) -> tuple[Path, Path | None]:
    """``desktop-<channel>.json`` and its signature, over every target found.

    Written through :func:`raiker.app.release.build_channel_index` so the two
    indexes share one schema, one signing rule, and one reader.
    """
    artifacts = update_artifacts(directory, version)
    staging = directory / ".desktop-channel"
    staging.mkdir(exist_ok=True)
    index, signature = build_channel_index(
        out_dir=staging,
        version=version,
        channel=channel,
        artifacts=artifacts,
        private_key=private_key,
        notes=notes,
    )
    final_index = directory / f"{CHANNEL_PREFIX}{channel}.json"
    index.replace(final_index)
    final_signature: Path | None = None
    if signature is not None:
        final_signature = directory / f"{CHANNEL_PREFIX}{channel}.json.sig"
        signature.replace(final_signature)
    staging.rmdir()
    return final_index, final_signature
