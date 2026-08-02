from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from raiker.app.update import (
    UpdateError,
    apply_signed_update,
    read_channel_index,
    recovery_points,
    roll_back,
    select_update,
)


def _bundle(tmp_path: Path, *, version: str = "2.0.0") -> tuple[Path, Path, Path, bytes]:
    bundle = tmp_path / "raiker-update.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("version.txt", version)
        archive.writestr("assets/app.js", "new web assets")
    manifest = {
        "schema": 1,
        "version": version,
        "artifact": bundle.name,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }
    manifest_path = tmp_path / "release.json"
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_path.write_bytes(manifest_bytes)
    private_key = Ed25519PrivateKey.generate()
    signature_path = tmp_path / "release.json.sig"
    signature_path.write_bytes(private_key.sign(manifest_bytes))
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return bundle, manifest_path, signature_path, public_key


def test_signed_update_verifies_backs_up_and_atomically_replaces(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")
    recovery = tmp_path / "recovery"

    result = apply_signed_update(
        bundle=bundle,
        manifest=manifest,
        signature=signature,
        public_key=public_key,
        install_root=install,
        recovery_root=recovery,
    )

    assert result.version == "2.0.0"
    assert (install / "version.txt").read_text(encoding="utf-8") == "2.0.0"
    assert (recovery / "1.0.0" / "version.txt").read_text(encoding="utf-8") == "1.0.0"


def test_tampered_update_is_rejected_before_installation_changes(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")
    bundle.write_bytes(bundle.read_bytes() + b"tampered")

    with pytest.raises(UpdateError, match="artifact_digest_mismatch"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=tmp_path / "recovery",
        )

    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
    assert not (tmp_path / "recovery").exists()


def test_failed_migration_leaves_previous_version_running(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")

    def fail_migration(_staged: Path) -> None:
        raise RuntimeError("migration failed")

    with pytest.raises(UpdateError, match="update_preparation_failed"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=tmp_path / "recovery",
            migrate=fail_migration,
        )

    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"


def test_untrusted_installed_version_cannot_escape_recovery_root(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("../outside", encoding="utf-8")

    with pytest.raises(UpdateError, match="installed_version_invalid"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=tmp_path / "recovery",
        )

    assert (install / "version.txt").read_text(encoding="utf-8") == "../outside"
    assert not (tmp_path / "outside").exists()


# ── BUG-44: the channel in front of the boundary above ───────────────────


def _channel(
    tmp_path: Path, *, version: str = "2.0.0", target: str = "linux-x86_64", signed: bool = True
) -> tuple[bytes, bytes, bytes]:
    """A signed index offering one artifact for one target."""
    index = {
        "schema": 1,
        "kind": "channel",
        "channel": "stable",
        "version": version,
        "released_at": "2026-08-02T00:00:00Z",
        "artifacts": {
            target: {
                "artifact": f"raiker-{version}-{target}.zip",
                "sha256": "0" * 64,
                "manifest": f"raiker-{version}-{target}.zip.manifest.json",
                "signature": f"raiker-{version}-{target}.zip.manifest.json.sig",
                "signed": signed,
            }
        },
    }
    private_key = Ed25519PrivateKey.generate()
    raw = json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return raw, private_key.sign(raw), public_key


def test_a_newer_signed_release_for_this_target_is_offered(tmp_path: Path) -> None:
    index, signature, public_key = _channel(tmp_path)
    update = select_update(
        index=index,
        signature=signature,
        public_key=public_key,
        target="linux-x86_64",
        current_version="1.0.0",
    )
    assert update is not None
    assert update.version == "2.0.0"
    assert update.artifact == "raiker-2.0.0-linux-x86_64.zip"
    assert update.signed is True


def test_the_same_or_an_older_version_is_no_update_rather_than_a_downgrade(
    tmp_path: Path,
) -> None:
    """A channel that went backwards must not be able to reinstall the past."""
    index, signature, public_key = _channel(tmp_path, version="1.0.0")
    for current in ("1.0.0", "1.4.2"):
        assert (
            select_update(
                index=index,
                signature=signature,
                public_key=public_key,
                target="linux-x86_64",
                current_version=current,
            )
            is None
        )


def test_a_tampered_index_is_refused_before_its_contents_are_read(tmp_path: Path) -> None:
    index, signature, public_key = _channel(tmp_path)
    tampered = index.replace(b'"2.0.0"', b'"9.0.0"')
    with pytest.raises(UpdateError, match="channel_signature_invalid"):
        select_update(
            index=tampered,
            signature=signature,
            public_key=public_key,
            target="linux-x86_64",
            current_version="1.0.0",
        )


def test_an_unsigned_artifact_is_never_installed_automatically(tmp_path: Path) -> None:
    index, signature, public_key = _channel(tmp_path, signed=False)
    with pytest.raises(UpdateError, match="channel_artifact_unsigned"):
        select_update(
            index=index,
            signature=signature,
            public_key=public_key,
            target="linux-x86_64",
            current_version="1.0.0",
        )


def test_an_index_naming_a_path_instead_of_a_filename_is_refused(tmp_path: Path) -> None:
    """The artifact name becomes a URL and a filename; it may be neither a path."""
    index = {
        "schema": 1,
        "kind": "channel",
        "channel": "stable",
        "version": "2.0.0",
        "released_at": "2026-08-02T00:00:00Z",
        "artifacts": {
            "linux-x86_64": {
                "artifact": "../../etc/passwd",
                "sha256": "0" * 64,
                "manifest": "m.json",
                "signature": "m.json.sig",
                "signed": True,
            }
        },
    }
    private_key = Ed25519PrivateKey.generate()
    raw = json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    with pytest.raises(UpdateError, match="channel_artifact_name_invalid"):
        read_channel_index(raw, private_key.sign(raw), public_key)


def test_rollback_restores_a_recovery_point_and_lists_what_is_available(
    tmp_path: Path,
) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")
    (install / "keep.txt").write_text("original", encoding="utf-8")
    recovery = tmp_path / "recovery"

    apply_signed_update(
        bundle=bundle,
        manifest=manifest,
        signature=signature,
        public_key=public_key,
        install_root=install,
        recovery_root=recovery,
    )
    assert (install / "version.txt").read_text(encoding="utf-8") == "2.0.0"
    assert not (install / "keep.txt").exists()

    points = recovery_points(recovery)
    assert [point.version for point in points] == ["1.0.0"]
    assert points[0].files == 2

    roll_back(install_root=install, recovery_point=points[0].path)
    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
    assert (install / "keep.txt").read_text(encoding="utf-8") == "original"
    # The recovery point survives the rollback: it is the only copy of that
    # version, and consuming it would make a second rollback impossible.
    assert points[0].path.is_dir()


def test_a_missing_recovery_point_refuses_instead_of_emptying_the_installation(
    tmp_path: Path,
) -> None:
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")
    with pytest.raises(UpdateError, match="recovery_point_missing"):
        roll_back(install_root=install, recovery_point=tmp_path / "nothing")
    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
