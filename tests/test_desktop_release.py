"""DIST-01/DIST-11 — the desktop release as data, kept in step with what builds it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from raiker.app.desktop_build import builder_command, builder_environment, pyinstaller_command
from raiker.app.desktop_release import (
    DESKTOP_TARGETS,
    artifact_names,
    build_desktop_channel,
    desktop_record,
    update_artifact_name,
    write_checksums,
    write_manifests,
)
from raiker.app.installation import detect_installation
from raiker.app.release import ReleaseError, public_key_of
from raiker.app.update import select_update

ROOT = Path(__file__).resolve().parents[1]


def _key() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def test_the_workflow_matrix_is_the_target_list() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/desktop-package.yml").read_text(encoding="utf-8"))
    include = workflow["jobs"]["package"]["strategy"]["matrix"]["include"]
    assert {(row["target"], row["runner"]) for row in include} == {
        (target.target_id, target.target.runner) for target in DESKTOP_TARGETS
    }


def test_every_supported_platform_and_architecture_is_a_target() -> None:
    assert {(t.target.os_name, t.target.arch) for t in DESKTOP_TARGETS} == {
        ("windows", "x86_64"),
        ("macos", "arm64"), ("macos", "x86_64"),
        ("linux", "x86_64"), ("linux", "arm64"),
    }
    for target in DESKTOP_TARGETS:
        assert target.update_format in target.target.installer_formats


def test_artifact_names_match_the_electron_builder_templates() -> None:
    config = yaml.safe_load((ROOT / "desktop/electron-builder.yml").read_text(encoding="utf-8"))

    def expand(template: str, ext: str, target: str, suffix: str) -> str:
        return (
            template.replace("${productName}", "Raiker").replace("${version}", "1.2.3")
            .replace("${env.RAIKER_TARGET}", target).replace("${env.RAIKER_ARTIFACT_SUFFIX}", suffix)
            .replace("${ext}", ext)
        )

    for signed in (True, False):
        suffix = "" if signed else "-unsigned"
        names = artifact_names("1.2.3", "windows-x86_64", signed=signed)
        assert names["-setup.exe"] == expand(config["nsis"]["artifactName"], "exe", "windows-x86_64", suffix)
        assert names[".msi"] == expand(config["msi"]["artifactName"], "msi", "windows-x86_64", suffix)
        for target_id, ext in (("macos-arm64", "dmg"), ("macos-arm64", "zip"),
                               ("linux-x86_64", "AppImage"), ("linux-x86_64", "deb"), ("linux-x86_64", "rpm")):
            assert artifact_names("1.2.3", target_id, signed=signed)[f".{ext}"] == expand(
                config["artifactName"], ext, target_id, suffix
            )


def test_an_unsigned_build_is_named_as_one() -> None:
    for name in artifact_names("1.2.3", "macos-arm64", signed=False).values():
        assert "-unsigned" in name
    for name in artifact_names("1.2.3", "macos-arm64", signed=True).values():
        assert "unsigned" not in name


def test_the_installer_config_is_per_user_and_keeps_owner_data() -> None:
    config = yaml.safe_load((ROOT / "desktop/electron-builder.yml").read_text(encoding="utf-8"))
    assert config["nsis"]["perMachine"] is False
    assert config["nsis"]["allowElevation"] is False
    assert config["nsis"]["deleteAppDataOnUninstall"] is False
    assert config["msi"]["perMachine"] is False
    assert config["mac"]["hardenedRuntime"] is True
    assert set(config["linux"]["target"]) == {"AppImage", "deb", "rpm"}
    include = (ROOT / "desktop" / config["nsis"]["include"]).read_text(encoding="utf-8")
    # An update must never ask about, or touch, the owner's data.
    assert "${IfNot} ${isUpdated}" in include
    # A silent uninstall keeps data; removing it is a choice made in the dialog.
    assert 'StrCpy $0 "keep"' in include
    assert "MB_DEFBUTTON2" in include  # "No" is the default answer


def test_the_desktop_record_is_read_back_as_a_desktop_installation(tmp_path: Path) -> None:
    record = desktop_record(version="1.2.3", target_id="macos-x86_64", channel="stable", signed=False)
    (tmp_path / "installation.json").write_text(json.dumps(record), encoding="utf-8")
    install = detect_installation(tmp_path)
    assert install.packaged is True
    assert install.signed is False
    assert install.distribution == "desktop"
    assert install.target == "macos-x86_64"
    assert install.version == "1.2.3"


def test_manifests_and_the_signed_desktop_channel_are_what_the_updater_accepts(tmp_path: Path) -> None:
    key = _key()
    for target in DESKTOP_TARGETS:
        for name in artifact_names("1.2.3", target.target_id, signed=True).values():
            (tmp_path / name).write_bytes(f"{name} bytes".encode())
        write_manifests(tmp_path, version="1.2.3", target_id=target.target_id, signed=True, private_key=key)
    index, signature = build_desktop_channel(tmp_path, version="1.2.3", channel="stable", private_key=key)
    assert index.name == "desktop-stable.json"
    assert signature is not None
    offered = select_update(
        index=index.read_bytes(), signature=signature.read_bytes(), public_key=public_key_of(key),
        target="linux-arm64", current_version="1.2.2",
    )
    assert offered is not None
    assert offered.artifact == update_artifact_name("1.2.3", "linux-arm64", signed=True)
    assert offered.artifact.endswith(".AppImage")
    # Not newer is not an update.
    assert select_update(
        index=index.read_bytes(), signature=signature.read_bytes(), public_key=public_key_of(key),
        target="linux-arm64", current_version="1.2.3",
    ) is None


def test_a_target_missing_one_of_its_installers_is_refused(tmp_path: Path) -> None:
    names = artifact_names("1.2.3", "windows-x86_64", signed=False)
    (tmp_path / names["-setup.exe"]).write_bytes(b"x")
    with pytest.raises(ReleaseError, match="desktop_artifact_missing"):
        write_manifests(tmp_path, version="1.2.3", target_id="windows-x86_64", signed=False)


def test_checksums_are_in_sha256sum_format(tmp_path: Path) -> None:
    (tmp_path / "a.deb").write_bytes(b"abc")
    path = write_checksums(tmp_path, ["a.deb"], name="SHA256SUMS-linux.txt")
    digest, name = path.read_text(encoding="utf-8").split()
    assert name == "a.deb" and len(digest) == 64


def test_the_builder_is_pinned_and_an_unsigned_build_cannot_pick_up_an_identity() -> None:
    command = builder_command(target_id="macos-arm64", version="1.2.3")
    assert any(part.startswith("electron-builder@") and part.count(".") == 2 for part in command)
    assert "--mac" in command and "--arm64" in command
    assert "-c.extraMetadata.version=1.2.3" in command
    env = builder_environment(
        target_id="macos-arm64", signed=False, environ={"CSC_LINK": "secret", "PATH": "/bin"}
    )
    assert "CSC_LINK" not in env
    assert env["CSC_IDENTITY_AUTO_DISCOVERY"] == "false"
    assert env["RAIKER_ARTIFACT_SUFFIX"] == "-unsigned"
    signed = builder_environment(target_id="macos-arm64", signed=True, environ={"CSC_LINK": "x"})
    assert signed["CSC_LINK"] == "x" and signed["RAIKER_ARTIFACT_SUFFIX"] == ""


def test_the_frozen_host_carries_the_keyring_backends_where_it_uses_them(tmp_path: Path) -> None:
    posix = pyinstaller_command(source_root=tmp_path, web_assets=tmp_path, out_dir=tmp_path, platform_name="linux")
    windows = pyinstaller_command(source_root=tmp_path, web_assets=tmp_path, out_dir=tmp_path, platform_name="win32")
    assert "--copy-metadata" in posix and "keyring" in posix
    assert "keyring" not in windows
    # The in-app Guide is read from docs/guide beside the frozen package.
    assert any(part.endswith("docs/guide") for part in posix)


def test_a_signed_build_checks_its_publishers_channel_unless_the_owner_pinned_one(tmp_path: Path) -> None:
    from raiker.app.installation import bundled_channel_config

    key = public_key_of(_key()).hex()
    channel = {"url": "https://updates.example/desktop-stable.json", "public_key": key, "channel": "stable"}
    signed = desktop_record(version="1.2.3", target_id="linux-x86_64", channel="stable",
                            signed=True, update_channel=channel)
    (tmp_path / "installation.json").write_text(json.dumps(signed), encoding="utf-8")
    found = bundled_channel_config(tmp_path)
    assert found is not None and found.url == channel["url"] and found.public_key.hex() == key

    # An unsigned build never updates, so its record is never a trust root.
    unsigned = desktop_record(version="1.2.3", target_id="linux-x86_64", channel="stable",
                              signed=False, update_channel=channel)
    (tmp_path / "installation.json").write_text(json.dumps(unsigned), encoding="utf-8")
    assert bundled_channel_config(tmp_path) is None

    plain = dict(signed, update_channel=dict(channel, url="http://updates.example/x.json"))
    (tmp_path / "installation.json").write_text(json.dumps(plain), encoding="utf-8")
    assert bundled_channel_config(tmp_path) is None
