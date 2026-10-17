"""Updating an installed desktop package from the signed channel (DIST-10).

A payload installation is a directory the updater swaps by rename
(:func:`raiker.app.update.apply_signed_update`). A desktop installation is not:
it is an NSIS install on Windows, an application bundle on macOS, an AppImage
or a system package on Linux, and each platform has one correct way to replace
it. What stays the same is every check before that:

1. the channel index is verified against the pinned key, and only a strictly
   newer version for this target is offered (:func:`raiker.app.update.select_update`);
2. the downloaded installer is verified against its own signed schema-1
   manifest — name and SHA-256 — before anything runs or moves
   (:func:`verify_downloaded`);
3. the owner's data is untouched by the replacement: it lives in the per-user
   data directory, never in the installation, and the database refuses to be
   opened by an older build than the one that last migrated it
   (``store_schema_newer``).

Then, per installation kind (:func:`install_kind`):

==============  ==============================================================
``nsis``        Run the verified installer silently for this user
                (``/S --updated --force-run``). It replaces the application
                files, keeps the data, and starts Raiker again. Rolling back is
                installing the previous release's installer.
``mac_app``     Unpack the verified ``.zip`` with ``ditto`` beside the running
                ``Raiker.app``, check its code signature when this install is
                signed, and swap by rename, keeping ``Raiker.app.previous``.
``appimage``    Copy the verified AppImage beside the running one and replace it
                atomically, keeping ``<name>.previous``.
``deb`` /       A system package's files belong to the package manager, which
``rpm`` /       Raiker never bypasses. The update is reported with the release it
``msi``         came from, and the owner installs the new package the way they
                installed this one (``desktop_update_manual``).
==============  ==============================================================
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from raiker.app.update import UpdateError, _signed_manifest, _verified_digest

InstallKind = Literal["nsis", "msi", "mac_app", "appimage", "deb", "rpm"]


@dataclass(frozen=True)
class DesktopInstall:
    kind: InstallKind
    #: What gets replaced: the install directory, the ``.app``, or the AppImage file.
    location: Path

    @property
    def replaces_in_place(self) -> bool:
        return self.kind in {"nsis", "mac_app", "appimage"}


@dataclass(frozen=True)
class DesktopUpdateResult:
    version: str
    kind: InstallKind
    artifact: Path
    #: The previous copy kept for rollback, when the format allows one.
    previous: Path | None
    #: True when the installer was started and finishes on its own (NSIS).
    handed_off: bool


def install_kind(
    *,
    executable: Path | None = None,
    platform: str = sys.platform,
    environ: dict[str, str] | None = None,
) -> DesktopInstall | None:
    """How this desktop package was installed, or ``None`` if it is not one.

    Read from where the frozen host sits — ``<install>/resources/host/`` — and
    from what the platform's installer leaves behind, never from a setting.
    """
    env = os.environ if environ is None else environ
    if executable is None:
        if not getattr(sys, "frozen", False):
            return None
        executable = Path(sys.executable)
    host_dir = executable.resolve().parent
    if host_dir.name != "host":
        return None
    resources = host_dir.parent
    if platform == "win32":
        install = resources.parent
        if (install / "Uninstall Raiker.exe").is_file():
            return DesktopInstall("nsis", install)
        return DesktopInstall("msi", install)
    if platform == "darwin":
        bundle = resources.parent.parent
        return DesktopInstall("mac_app", bundle) if bundle.suffix == ".app" else None
    appimage = env.get("APPIMAGE", "").strip()
    if appimage:
        return DesktopInstall("appimage", Path(appimage))
    install = resources.parent
    if Path("/var/lib/dpkg/info/raiker.list").is_file():
        return DesktopInstall("deb", install)
    return DesktopInstall("rpm", install)


def update_format_for(kind: InstallKind) -> str:
    """The artifact suffix this installation kind takes from the channel."""
    return {
        "nsis": "-setup.exe",
        "msi": ".msi",
        "mac_app": ".zip",
        "appimage": ".AppImage",
        "deb": ".deb",
        "rpm": ".rpm",
    }[kind]


def verify_downloaded(
    *, artifact: Path, manifest: Path, signature: Path, public_key: bytes, version: str
) -> str:
    """The artifact's digest once its signed manifest vouches for it, or a refusal."""
    parsed = _signed_manifest(manifest, signature, public_key)
    if str(parsed["version"]) != version:
        raise UpdateError("release_version_mismatch")
    return _verified_digest(artifact, parsed)


def _run(argv: list[str]) -> None:
    completed = subprocess.run(argv, check=False, capture_output=True, timeout=600)  # noqa: S603
    if completed.returncode != 0:
        raise UpdateError(f"desktop_update_step_failed:{Path(argv[0]).name}")


def _swap(new: Path, current: Path) -> Path:
    """Replace *current* with *new* by rename, keeping the old one beside it."""
    previous = current.with_name(current.name + ".previous")
    if previous.exists():
        if previous.is_dir():
            shutil.rmtree(previous)
        else:
            previous.unlink()
    current.rename(previous)
    try:
        new.rename(current)
    except OSError:
        previous.rename(current)
        raise
    return previous


def apply_desktop_update(
    *,
    install: DesktopInstall,
    artifact: Path,
    version: str,
    signed_install: bool,
    launch: bool = True,
) -> DesktopUpdateResult:
    """Install an artifact :func:`verify_downloaded` has already accepted."""
    if install.kind == "nsis":
        argv = [str(artifact), "/S", "--updated"] + (["--force-run"] if launch else [])
        subprocess.Popen(argv, close_fds=True)  # noqa: S603 - the verified installer
        return DesktopUpdateResult(version, install.kind, artifact, None, handed_off=True)

    if install.kind == "mac_app":
        staging = Path(tempfile.mkdtemp(prefix=".raiker-update-", dir=install.location.parent))
        try:
            # ditto keeps the bundle's symlinks, permissions and signature intact;
            # an archive extractor that refuses symlinks cannot unpack a .app.
            _run(["/usr/bin/ditto", "-x", "-k", str(artifact), str(staging)])
            unpacked = staging / install.location.name
            if not unpacked.is_dir():
                raise UpdateError("desktop_update_bundle_missing")
            if signed_install:
                _run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(unpacked)])
            previous = _swap(unpacked, install.location)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        if launch:
            subprocess.Popen(["/usr/bin/open", "-n", str(install.location)], close_fds=True)  # noqa: S603
        return DesktopUpdateResult(version, install.kind, artifact, previous, handed_off=False)

    if install.kind == "appimage":
        staged = install.location.with_name(f".{install.location.name}.new")
        shutil.copyfile(artifact, staged)
        staged.chmod(0o755)
        previous = install.location.with_name(install.location.name + ".previous")
        shutil.copy2(install.location, previous)
        os.replace(staged, install.location)
        if launch:
            subprocess.Popen([str(install.location)], close_fds=True, start_new_session=True)  # noqa: S603
        return DesktopUpdateResult(version, install.kind, artifact, previous, handed_off=False)

    # deb, rpm, msi: files owned by the system package manager. Raiker does not
    # replace them itself; Settings → Updates says a release is available and
    # where to download its package, and the system installer asks for consent.
    raise UpdateError("desktop_update_manual")


def roll_back_desktop(install: DesktopInstall) -> Path:
    """Put the copy kept by the last in-place update back. Refuses when there is none."""
    if not install.replaces_in_place or install.kind == "nsis":
        raise UpdateError("desktop_rollback_unavailable")
    previous = install.location.with_name(install.location.name + ".previous")
    if not previous.exists():
        raise UpdateError("desktop_rollback_unavailable")
    failed = install.location.with_name(install.location.name + ".failed")
    if failed.exists():
        shutil.rmtree(failed) if failed.is_dir() else failed.unlink()
    install.location.rename(failed)
    previous.rename(install.location)
    return install.location
