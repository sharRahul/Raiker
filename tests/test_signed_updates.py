from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from raiker.app.update import UpdateError, apply_signed_update


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
