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
    tmp_path: Path,
    *,
    version: str = "2.0.0",
    target: str = "linux-x86_64",
    signed: bool = True,
    extra: dict[str, object] | None = None,
    entry_extra: dict[str, object] | None = None,
) -> tuple[bytes, bytes, bytes]:
    """A signed index offering one artifact for one target."""
    index: dict[str, object] = {
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
                **(entry_extra or {}),
            }
        },
        **(extra or {}),
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


# ── DEC-17 step 7: room first, health after ──────────────────────────────────


def _installed(tmp_path: Path) -> Path:
    install = tmp_path / "installed"
    install.mkdir()
    (install / "version.txt").write_text("1.0.0", encoding="utf-8")
    (install / "keep.txt").write_text("original", encoding="utf-8")
    return install


def test_an_update_the_disk_cannot_hold_is_refused_before_the_first_write(
    tmp_path: Path,
) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = _installed(tmp_path)

    with pytest.raises(UpdateError, match="update_insufficient_space"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=tmp_path / "recovery",
            free_space=lambda _path: 1024,
        )

    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
    assert not (tmp_path / "recovery").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".installed.")]


def test_the_space_check_counts_the_staged_tree_and_the_recovery_copy(
    tmp_path: Path,
) -> None:
    from raiker.app.update import UPDATE_SPACE_HEADROOM_BYTES

    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = _installed(tmp_path)
    asked: list[Path] = []
    staged = len("2.0.0") + len("new web assets")
    retained = len("1.0.0") + len("original")

    def exactly_enough(path: Path) -> int:
        asked.append(path)
        return staged + retained + UPDATE_SPACE_HEADROOM_BYTES

    apply_signed_update(
        bundle=bundle,
        manifest=manifest,
        signature=signature,
        public_key=public_key,
        install_root=install,
        recovery_root=tmp_path / "recovery",
        free_space=exactly_enough,
    )
    # One volume here, so one question covering both.
    assert len(asked) == 1
    assert (install / "version.txt").read_text(encoding="utf-8") == "2.0.0"


def test_an_entry_that_unpacks_larger_than_it_declared_is_refused(tmp_path: Path) -> None:
    from raiker.app.update import _safe_extract

    bundle = tmp_path / "lying.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("version.txt", "2.0.0")
    raw = bytearray(bundle.read_bytes())
    # Rewrite the central directory's uncompressed size for the one entry to 1.
    central = raw.rfind(b"PK\x01\x02")
    raw[central + 24 : central + 28] = (1).to_bytes(4, "little")
    bundle.write_bytes(bytes(raw))

    # zipfile stops at the declared size and fails the entry's CRC, so the
    # space check's arithmetic holds against an archive that lies about it.
    with pytest.raises(UpdateError, match="artifact_archive_invalid"):
        _safe_extract(bundle, tmp_path / "staged")
    staged = tmp_path / "staged" / "version.txt"
    assert not staged.exists() or staged.stat().st_size <= 1


def test_a_swapped_tree_that_fails_its_health_check_is_rolled_back(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = _installed(tmp_path)
    recovery = tmp_path / "recovery"

    with pytest.raises(UpdateError, match="update_health_check_failed"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=recovery,
            health_check=lambda _install, _version: False,
        )

    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
    assert (install / "keep.txt").read_text(encoding="utf-8") == "original"
    # No recovery copy is left to refuse the next attempt, and no sibling trees.
    assert not (recovery / "1.0.0").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".installed.")]

    # The same update, with a check that passes, now installs.
    apply_signed_update(
        bundle=bundle,
        manifest=manifest,
        signature=signature,
        public_key=public_key,
        install_root=install,
        recovery_root=recovery,
    )
    assert (install / "version.txt").read_text(encoding="utf-8") == "2.0.0"


def test_a_check_that_raises_counts_as_failed(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = _installed(tmp_path)

    def broken(_install: Path, _version: str) -> bool:
        raise RuntimeError("could not tell")

    with pytest.raises(UpdateError, match="update_health_check_failed"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=tmp_path / "recovery",
            health_check=broken,
        )
    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"


def test_the_default_check_reads_the_version_the_manifest_named(tmp_path: Path) -> None:
    from raiker.app.update import installed_tree_healthy

    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "version.txt").write_text("2.0.0\n", encoding="utf-8")
    assert installed_tree_healthy(tree, "2.0.0")
    assert not installed_tree_healthy(tree, "2.0.1")
    (tree / "installation.json").write_text(json.dumps({"version": "1.9.0"}), encoding="utf-8")
    assert not installed_tree_healthy(tree, "2.0.0")
    (tree / "installation.json").write_text(json.dumps({"version": "2.0.0"}), encoding="utf-8")
    assert installed_tree_healthy(tree, "2.0.0")
    (tree / "installation.json").write_text("{not json", encoding="utf-8")
    assert not installed_tree_healthy(tree, "2.0.0")


def test_a_failed_migration_leaves_no_recovery_copy_to_block_a_retry(tmp_path: Path) -> None:
    bundle, manifest, signature, public_key = _bundle(tmp_path)
    install = _installed(tmp_path)
    recovery = tmp_path / "recovery"

    def fail(_staged: Path) -> None:
        raise RuntimeError("migration failed")

    with pytest.raises(UpdateError, match="update_preparation_failed"):
        apply_signed_update(
            bundle=bundle,
            manifest=manifest,
            signature=signature,
            public_key=public_key,
            install_root=install,
            recovery_root=recovery,
            migrate=fail,
        )
    assert not (recovery / "1.0.0").exists()


# ── DEC-21 Updates: the index says how large the download is and what it changes ─


def test_an_index_may_state_the_download_size_and_the_release_notes(tmp_path: Path) -> None:
    index, signature, public_key = _channel(
        tmp_path, extra={"notes": "Fixes stale routines."}, entry_extra={"size": 4096}
    )
    update = select_update(
        index=index, signature=signature, public_key=public_key,
        target="linux-x86_64", current_version="1.0.0",
    )
    assert update is not None
    assert update.size == 4096
    assert update.notes == "Fixes stale routines."


def test_an_index_without_them_reads_as_unstated(tmp_path: Path) -> None:
    index, signature, public_key = _channel(tmp_path)
    update = select_update(
        index=index, signature=signature, public_key=public_key,
        target="linux-x86_64", current_version="1.0.0",
    )
    assert update is not None
    assert update.size is None and update.notes is None


@pytest.mark.parametrize(
    ("extra", "entry_extra"),
    [
        ({"notes": "x" * 4001}, None),
        ({"notes": 7}, None),
        (None, {"size": 0}),
        (None, {"size": True}),
        (None, {"size": "4096"}),
        ({"homepage": "https://example"}, None),
        (None, {"mirror": "https://example"}),
    ],
)
def test_a_malformed_size_or_note_or_an_unknown_field_is_refused(
    tmp_path: Path, extra: dict[str, object] | None, entry_extra: dict[str, object] | None
) -> None:
    index, signature, public_key = _channel(tmp_path, extra=extra, entry_extra=entry_extra)
    with pytest.raises(UpdateError, match="channel_index_invalid"):
        read_channel_index(index, signature, public_key)


def test_a_download_reads_no_more_than_the_size_the_index_signed(tmp_path: Path) -> None:
    from raiker.app.installation import ChannelConfig, UpdateStatus, detect_installation
    from raiker.app.update import ChannelUpdate
    from raiker.app.updater import MAX_ARTIFACT_BYTES, download_and_apply

    asked: dict[str, int] = {}

    class Stop(Exception):
        pass

    def fetch(url: str, limit: int) -> bytes:
        asked[url.rsplit("/", 1)[-1]] = limit
        raise Stop

    offered = ChannelUpdate(
        channel="stable", version="2.0.0", target="linux-x86_64",
        artifact="raiker-2.0.0.zip", sha256="0" * 64,
        manifest="raiker-2.0.0.zip.manifest.json",
        signature="raiker-2.0.0.zip.manifest.json.sig",
        signed=True, released_at="2026-08-02T00:00:00Z", size=4096,
    )
    status = UpdateStatus(
        state="available", message="", installation=detect_installation(),
        channel=None, available=offered, recovery=[], checked_at=None,
    )
    config = ChannelConfig(url="https://releases.example/stable.json", public_key=b"k" * 32, channel="stable")
    with pytest.raises(Stop):
        download_and_apply(tmp_path, status=status, config=config, install_root=tmp_path / "i", fetch=fetch)
    assert asked["raiker-2.0.0.zip"] == 4096

    oversized = ChannelUpdate(**{**offered.__dict__, "size": MAX_ARTIFACT_BYTES + 1})
    with pytest.raises(UpdateError, match="artifact_too_large"):
        download_and_apply(
            tmp_path,
            status=UpdateStatus(**{**status.__dict__, "available": oversized}),
            config=config, install_root=tmp_path / "i", fetch=fetch,
        )


def _bundle_with_generation(tmp_path: Path, generation: int) -> tuple[Path, Path, Path, bytes]:
    bundle = tmp_path / "raiker-update.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("version.txt", "2.0.0")
        archive.writestr(
            "installation.json", json.dumps({"version": "2.0.0", "schema_generation": generation})
        )
    manifest = {
        "schema": 1,
        "version": "2.0.0",
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
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return bundle, manifest_path, signature_path, public_key


def test_a_release_that_cannot_open_this_workspace_is_refused_before_anything_moves(
    tmp_path: Path,
) -> None:
    """DEC-17 step 7 — compatibility is checked on the staged build, before the swap."""
    bundle, manifest, signature, public_key = _bundle_with_generation(tmp_path, 150)
    install = _installed(tmp_path)
    recovery = tmp_path / "recovery"
    with pytest.raises(UpdateError, match="update_schema_incompatible"):
        apply_signed_update(
            bundle=bundle, manifest=manifest, signature=signature, public_key=public_key,
            install_root=install, recovery_root=recovery, workspace_generation=199,
        )
    assert (install / "version.txt").read_text(encoding="utf-8") == "1.0.0"
    assert not (recovery / "1.0.0").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".installed.")]


@pytest.mark.parametrize(("offered", "workspace"), [(199, 199), (210, 199), (150, None)])
def test_a_release_that_opens_it_or_an_unknown_reading_is_not_refused(
    tmp_path: Path, offered: int, workspace: int | None
) -> None:
    bundle, manifest, signature, public_key = _bundle_with_generation(tmp_path, offered)
    install = _installed(tmp_path)
    apply_signed_update(
        bundle=bundle, manifest=manifest, signature=signature, public_key=public_key,
        install_root=install, recovery_root=tmp_path / "recovery", workspace_generation=workspace,
    )
    assert (install / "version.txt").read_text(encoding="utf-8") == "2.0.0"
