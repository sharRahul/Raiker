"""DIST-10 — a desktop package is updated by its own installer, after the same checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from raiker.app import desktop_update
from raiker.app.desktop_update import (
    DesktopInstall,
    apply_desktop_update,
    install_kind,
    roll_back_desktop,
    verify_downloaded,
)
from raiker.app.release import public_key_of, sign
from raiker.app.update import UpdateError


def _host(root: Path, *parts: str) -> Path:
    host = root.joinpath(*parts, "host")
    host.mkdir(parents=True)
    executable = host / "Raiker"
    executable.write_text("", encoding="utf-8")
    return executable


def test_the_installation_kind_is_read_from_where_the_host_sits(tmp_path: Path) -> None:
    windows = _host(tmp_path / "win", "Raiker", "resources")
    (tmp_path / "win" / "Raiker" / "Uninstall Raiker.exe").write_text("", encoding="utf-8")
    assert install_kind(executable=windows, platform="win32", environ={}) == DesktopInstall(
        "nsis", (tmp_path / "win" / "Raiker").resolve()
    )
    msi = _host(tmp_path / "msi", "Raiker", "resources")
    assert install_kind(executable=msi, platform="win32", environ={}).kind == "msi"  # type: ignore[union-attr]
    mac = _host(tmp_path / "mac", "Raiker.app", "Contents", "Resources")
    found = install_kind(executable=mac, platform="darwin", environ={})
    assert found is not None and found.kind == "mac_app" and found.location.name == "Raiker.app"
    linux = _host(tmp_path / "appimage", "squashfs-root", "resources")
    found = install_kind(executable=linux, platform="linux", environ={"APPIMAGE": "/home/o/Raiker.AppImage"})
    assert found == DesktopInstall("appimage", Path("/home/o/Raiker.AppImage"))
    # A payload or source install is not a desktop package.
    loose = tmp_path / "loose" / "Raiker"
    loose.parent.mkdir()
    loose.write_text("", encoding="utf-8")
    assert install_kind(executable=loose, platform="linux", environ={}) is None


def _signed(tmp_path: Path, payload: bytes, *, version: str = "1.2.3") -> tuple[Path, Path, Path, bytes]:
    key = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    artifact = tmp_path / "Raiker-1.2.3-linux-x86_64.AppImage"
    artifact.write_bytes(payload)
    manifest = {"schema": 1, "version": version, "artifact": artifact.name,
                "sha256": hashlib.sha256(payload).hexdigest()}
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_path = tmp_path / f"{artifact.name}.manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    signature = tmp_path / f"{artifact.name}.manifest.json.sig"
    signature.write_bytes(sign(manifest_bytes, key))
    return artifact, manifest_path, signature, public_key_of(key)


def test_a_downloaded_installer_must_match_its_signed_manifest(tmp_path: Path) -> None:
    artifact, manifest, signature, public = _signed(tmp_path, b"new release")
    assert verify_downloaded(artifact=artifact, manifest=manifest, signature=signature,
                             public_key=public, version="1.2.3")
    artifact.write_bytes(b"tampered")
    with pytest.raises(UpdateError, match="artifact_digest_mismatch"):
        verify_downloaded(artifact=artifact, manifest=manifest, signature=signature,
                          public_key=public, version="1.2.3")


def test_an_untrusted_signature_is_refused(tmp_path: Path) -> None:
    artifact, manifest, signature, _ = _signed(tmp_path, b"new release")
    other = public_key_of(Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    with pytest.raises(UpdateError, match="release_signature_invalid"):
        verify_downloaded(artifact=artifact, manifest=manifest, signature=signature,
                          public_key=other, version="1.2.3")


def test_a_manifest_for_another_version_is_refused(tmp_path: Path) -> None:
    artifact, manifest, signature, public = _signed(tmp_path, b"x", version="9.9.9")
    with pytest.raises(UpdateError, match="release_version_mismatch"):
        verify_downloaded(artifact=artifact, manifest=manifest, signature=signature,
                          public_key=public, version="1.2.3")


def test_an_appimage_is_replaced_atomically_and_can_be_rolled_back(tmp_path: Path) -> None:
    current = tmp_path / "Raiker.AppImage"
    current.write_bytes(b"old")
    new = tmp_path / "download.AppImage"
    new.write_bytes(b"new")
    install = DesktopInstall("appimage", current)
    result = apply_desktop_update(install=install, artifact=new, version="1.2.3",
                                  signed_install=False, launch=False)
    assert current.read_bytes() == b"new"
    assert current.stat().st_mode & 0o111
    assert result.previous is not None and result.previous.read_bytes() == b"old"
    roll_back_desktop(install)
    assert current.read_bytes() == b"old"


def test_a_system_package_is_never_replaced_by_raiker_itself(tmp_path: Path) -> None:
    for kind in ("deb", "rpm", "msi"):
        with pytest.raises(UpdateError, match="desktop_update_manual"):
            apply_desktop_update(install=DesktopInstall(kind, tmp_path), artifact=tmp_path / "x",  # type: ignore[arg-type]
                                 version="1.2.3", signed_install=True, launch=False)


def test_nsis_runs_the_verified_installer_silently_for_this_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(desktop_update.subprocess, "Popen", lambda argv, **_k: started.append(argv))
    artifact = tmp_path / "Raiker-1.2.3-windows-x86_64-setup.exe"
    result = apply_desktop_update(install=DesktopInstall("nsis", tmp_path), artifact=artifact,
                                  version="1.2.3", signed_install=True)
    assert started == [[str(artifact), "/S", "--updated", "--force-run"]]
    assert result.handed_off is True
