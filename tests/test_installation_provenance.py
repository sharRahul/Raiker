"""BUG-44 — what Raiker says about its own build, and when it asks a channel.

The interesting cases are all the ones where evidence is absent or damaged. A
source checkout, a record that will not parse, a record from a schema this code
does not know, a target that is not a target: every one of them must report an
*unsigned, unpackaged* installation. Nothing may read the absence of evidence as
a signature.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from raiker.app.installation import (
    artifact_url,
    detect_installation,
    read_channel_config,
    read_last_check,
    record_check,
    update_status,
    write_channel_config,
)
from raiker.app.release import build_channel_index, installation_record, public_key_of, target_for
from raiker.app.update import UpdateError
from raiker.app.updater import MAX_METADATA_BYTES, check_for_update


@pytest.fixture
def signing_key() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes_raw()


def _installed(root: Path, **overrides: object) -> Path:
    record = installation_record(
        version="1.2.3",
        target=target_for("linux-x86_64"),
        channel="stable",
        signed=True,
        commit="abc1234",
        built_at="2026-08-02T00:00:00Z",
    )
    record.update(overrides)
    root.mkdir(parents=True, exist_ok=True)
    (root / "installation.json").write_text(json.dumps(record), encoding="utf-8")
    return root


def test_a_source_checkout_says_it_is_a_source_checkout(tmp_path: Path) -> None:
    install = detect_installation(tmp_path / "nothing")
    assert install.packaged is False
    assert install.signed is False
    assert install.version == "0.0.0"
    assert "source checkout" in install.note


def test_a_signed_release_reports_its_build(tmp_path: Path) -> None:
    install = detect_installation(_installed(tmp_path / "app"))
    assert install.packaged is True
    assert install.signed is True
    assert (install.version, install.target, install.channel) == ("1.2.3", "linux-x86_64", "stable")
    assert install.commit == "abc1234"
    assert install.note == ""


def test_an_unsigned_build_is_packaged_but_never_reported_as_signed(tmp_path: Path) -> None:
    root = _installed(
        tmp_path / "app",
        signing={"tool": "codesign", "required_secrets": [], "applied": False},
    )
    install = detect_installation(root)
    assert install.packaged is True
    assert install.signed is False
    assert "without platform signing" in install.note


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        json.dumps({"version": "1.2.3"}),
        json.dumps({"schema": 99, "version": "1.2.3", "target": "linux-x86_64",
                    "channel": "stable", "signing": {"applied": True}}),
        json.dumps({"schema": 1, "version": "1.2.3", "target": "atari-st",
                    "channel": "stable", "signing": {"applied": True}}),
    ],
)
def test_a_record_that_cannot_be_trusted_reports_an_unsigned_source_install(
    tmp_path: Path, content: str
) -> None:
    root = tmp_path / "app"
    root.mkdir()
    (root / "installation.json").write_text(content, encoding="utf-8")
    install = detect_installation(root)
    assert install.packaged is False
    assert install.signed is False


def test_status_refuses_locally_before_it_would_ever_ask_a_channel(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert update_status(workspace, installation=detect_installation(tmp_path / "none")).state == (
        "source_checkout"
    )
    unsigned = detect_installation(
        _installed(
            tmp_path / "unsigned",
            signing={"tool": "codesign", "required_secrets": [], "applied": False},
        )
    )
    assert update_status(workspace, installation=unsigned).state == "unsigned_build"
    signed = detect_installation(_installed(tmp_path / "signed"))
    assert update_status(workspace, installation=signed).state == "no_channel"


def test_pinning_a_channel_requires_https_and_a_real_key(tmp_path: Path, signing_key: bytes) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    public = public_key_of(signing_key).hex()
    with pytest.raises(UpdateError, match="channel_url_invalid"):
        write_channel_config(workspace, url="http://releases.example/stable.json", public_key=public)
    with pytest.raises(UpdateError, match="channel_public_key_invalid"):
        write_channel_config(workspace, url="https://releases.example/stable.json", public_key="zz")
    config = write_channel_config(
        workspace, url="https://releases.example/stable.json", public_key=public
    )
    assert read_channel_config(workspace) == config


def test_an_artifact_name_can_never_leave_the_channel_directory(
    tmp_path: Path, signing_key: bytes
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    config = write_channel_config(
        workspace,
        url="https://releases.example/downloads/stable.json",
        public_key=public_key_of(signing_key).hex(),
    )
    assert artifact_url(config, "raiker-2.0.0-linux-x86_64.zip") == (
        "https://releases.example/downloads/raiker-2.0.0-linux-x86_64.zip"
    )
    for name in ("../secret.zip", "/etc/passwd", "https://elsewhere.example/x.zip"):
        with pytest.raises(UpdateError, match="channel_artifact_name_invalid"):
            artifact_url(config, name)


def _published(directory: Path, version: str, signing_key: bytes) -> tuple[bytes, bytes]:
    from raiker.app.release import ReleaseArtifact, sign

    artifacts = []
    for target in ("linux-x86_64", "macos-arm64"):
        name = f"raiker-{version}-{target}.zip"
        bundle = directory / name
        bundle.write_bytes(b"artifact")
        manifest = directory / f"{name}.manifest.json"
        manifest.write_bytes(b"{}")
        signature = directory / f"{name}.manifest.json.sig"
        signature.write_bytes(sign(b"{}", signing_key))
        artifacts.append(
            ReleaseArtifact(
                path=bundle,
                sha256="0" * 64,
                version=version,
                target_id=target,
                channel="stable",
                signed=True,
                manifest_path=manifest,
                signature_path=signature,
            )
        )
    index_path, signature_path = build_channel_index(
        out_dir=directory,
        version=version,
        channel="stable",
        artifacts=artifacts,
        private_key=signing_key,
    )
    assert signature_path is not None
    return index_path.read_bytes(), signature_path.read_bytes()


def test_a_check_against_a_published_channel_offers_the_newer_release(
    tmp_path: Path, signing_key: bytes
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_channel_config(
        workspace,
        url="https://releases.example/stable.json",
        public_key=public_key_of(signing_key).hex(),
    )
    published = tmp_path / "published"
    published.mkdir()
    index, signature = _published(published, "2.0.0", signing_key)
    responses = {
        "https://releases.example/stable.json": index,
        "https://releases.example/stable.json.sig": signature,
    }

    status = check_for_update(
        workspace,
        installation=detect_installation(_installed(tmp_path / "app")),
        fetch=lambda url, limit: responses[url],
    )
    assert status.state == "available"
    assert status.available is not None and status.available.version == "2.0.0"
    assert status.checked_at is not None

    record_check(workspace, status)
    assert read_last_check(workspace) == {
        "state": "available",
        "message": status.message,
        "available_version": "2.0.0",
        "checked_at": status.checked_at,
    }


def test_a_channel_that_cannot_be_read_changes_nothing_and_says_so(
    tmp_path: Path, signing_key: bytes
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_channel_config(
        workspace,
        url="https://releases.example/stable.json",
        public_key=public_key_of(signing_key).hex(),
    )

    def refuse(url: str, limit: int) -> bytes:
        raise OSError("no route to host")

    status = check_for_update(
        workspace,
        installation=detect_installation(_installed(tmp_path / "app")),
        fetch=refuse,
    )
    assert status.state == "unreachable"
    assert status.available is None
    assert "nothing about this installation changed" in status.message


def test_a_source_checkout_never_makes_a_request(tmp_path: Path, signing_key: bytes) -> None:
    """Pressing "check" on a development host must not be a way to cause egress."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_channel_config(
        workspace,
        url="https://releases.example/stable.json",
        public_key=public_key_of(signing_key).hex(),
    )
    calls: list[str] = []

    def record(url: str, limit: int) -> bytes:
        calls.append(url)
        return b""

    status = check_for_update(
        workspace, installation=detect_installation(tmp_path / "none"), fetch=record
    )
    assert status.state == "source_checkout"
    assert calls == []


def test_an_oversized_channel_response_is_refused(tmp_path: Path, signing_key: bytes) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    write_channel_config(
        workspace,
        url="https://releases.example/stable.json",
        public_key=public_key_of(signing_key).hex(),
    )

    def flood(url: str, limit: int) -> bytes:
        assert limit == MAX_METADATA_BYTES
        raise UpdateError("channel_response_too_large")

    status = check_for_update(
        workspace, installation=detect_installation(_installed(tmp_path / "app")), fetch=flood
    )
    assert status.state == "unreachable"


# ── the CLI an owner actually types ──────────────────────────────────────


def test_raiker_app_update_reports_the_build_without_asking_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The default is a report. A check is something you ask for."""
    from apps.api.launcher import main

    assert main(["update", "--workspace", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "source checkout" in out
    assert "unsigned build" in out


def test_raiker_app_update_pins_a_channel_and_refuses_a_half_pin(
    tmp_path: Path, signing_key: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main

    assert (
        main(
            [
                "update",
                "--workspace",
                str(tmp_path),
                "--channel-url",
                "https://releases.example/stable.json",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "update",
                "--workspace",
                str(tmp_path),
                "--channel-url",
                "https://releases.example/stable.json",
                "--channel-key",
                public_key_of(signing_key).hex(),
            ]
        )
        == 0
    )
    assert "Update channel pinned" in capsys.readouterr().out
    config = read_channel_config(tmp_path)
    assert config is not None and config.channel == "stable"


def test_raiker_app_update_rollback_names_what_is_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from apps.api.launcher import main
    from raiker.app.installation import recovery_root

    point = recovery_root(tmp_path) / "1.0.0"
    point.mkdir(parents=True)
    (point / "version.txt").write_text("1.0.0", encoding="utf-8")
    assert main(["update", "--workspace", str(tmp_path), "--rollback", "9.9.9"]) == 2
    err = capsys.readouterr()
    assert "No recovery point for 9.9.9" in err.err
    assert "available: 1.0.0" in err.out
