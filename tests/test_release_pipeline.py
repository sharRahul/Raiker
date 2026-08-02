"""BUG-44 — the release build, its matrix, and the honesty of both.

The signing identities live in GitHub secrets and the per-OS runners live in
GitHub Actions, so the two things worth testing on any machine are the decisions
either side of them: that an artifact rebuilds to the same bytes, and that
nothing in the pipeline can describe an unsigned build as a signed one.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from raiker.app.release import (
    TARGETS,
    TARGETS_BY_ID,
    ReleaseArtifact,
    ReleaseError,
    artifact_name,
    build_bundle,
    build_channel_index,
    collect_payload,
    main,
    public_key_of,
    target_for,
)
from raiker.app.update import UpdateError, read_channel_index, select_update


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "raiker" / "app").mkdir(parents=True)
    (root / "apps" / "api").mkdir(parents=True)
    (root / "raiker" / "__init__.py").write_text("", encoding="utf-8")
    (root / "raiker" / "app" / "host.py").write_text("host", encoding="utf-8")
    (root / "apps" / "api" / "main.py").write_text("main", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='raiker'\n", encoding="utf-8")
    # Two things an artifact must never carry: build caches, and another
    # platform's compiled leftovers. Both would differ between two builds.
    (root / "raiker" / "__pycache__").mkdir()
    (root / "raiker" / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"cache")
    return root


@pytest.fixture
def web_assets(tmp_path: Path) -> Path:
    assets = tmp_path / "web"
    (assets / "assets").mkdir(parents=True)
    (assets / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (assets / "assets" / "app.js").write_text("export const app = 1;", encoding="utf-8")
    return assets


@pytest.fixture
def wheel_dir(tmp_path: Path) -> Path:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    (wheels / "sqlcipher3_wheels-0.5.0-cp311-cp311-manylinux.whl").write_bytes(b"wheel")
    return wheels


@pytest.fixture
def signing_key() -> bytes:
    return Ed25519PrivateKey.generate().private_bytes_raw()


@pytest.fixture(autouse=True)
def source_date_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reproducibility is conditional on a fixed build clock, so fix it.

    The workflow sets ``SOURCE_DATE_EPOCH`` from the commit being released, which
    is the value every runner in a matrix agrees on. Without it, a build stamps
    itself with the wall clock and two builds of one commit differ by exactly
    that stamp — which is why the workflow sets it and this fixture does too.
    """
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1750000000")


def _build(
    out: Path, source_root: Path, web_assets: Path, wheel_dir: Path, **kwargs: object
) -> ReleaseArtifact:
    entries = collect_payload(
        source_root=source_root, web_assets=web_assets, wheel_dir=wheel_dir
    )
    return build_bundle(
        out_dir=out,
        version=str(kwargs.pop("version", "1.2.3")),
        target=target_for(str(kwargs.pop("target", "linux-x86_64"))),
        entries=entries,
        **kwargs,  # type: ignore[arg-type]
    )


def test_every_target_names_the_signing_identity_it_requires() -> None:
    """A target that could publish without an identity is the whole defect."""
    assert {target.target_id for target in TARGETS} == {
        "macos-arm64",
        "macos-x86_64",
        "windows-x86_64",
        "linux-x86_64",
    }
    for target in TARGETS:
        assert target.installer_formats, target.target_id
        assert target.signing.secrets, target.target_id
        assert target.signing.tool.strip(), target.target_id
        assert target.runner.strip(), target.target_id
    # Both macOS architectures are built, because a native wheel that packages on
    # Apple Silicon is not evidence about Intel.
    assert {t.arch for t in TARGETS if t.os_name == "macos"} == {"arm64", "x86_64"}
    assert ".deb" in TARGETS_BY_ID["linux-x86_64"].installer_formats
    assert ".AppImage" in TARGETS_BY_ID["linux-x86_64"].installer_formats


def test_a_bundle_rebuilds_to_the_same_bytes(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path
) -> None:
    first = _build(tmp_path / "a", source_root, web_assets, wheel_dir)
    second = _build(tmp_path / "b", source_root, web_assets, wheel_dir)
    assert first.sha256 == second.sha256
    assert first.sha256 == hashlib.sha256(first.path.read_bytes()).hexdigest()


def test_a_bundle_carries_the_service_the_web_assets_and_the_native_wheels(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path
) -> None:
    artifact = _build(tmp_path / "out", source_root, web_assets, wheel_dir)
    with zipfile.ZipFile(artifact.path) as archive:
        names = set(archive.namelist())
    assert "service/raiker/app/host.py" in names
    assert "service/apps/api/main.py" in names
    assert "web/index.html" in names
    assert "wheels/sqlcipher3_wheels-0.5.0-cp311-cp311-manylinux.whl" in names
    assert "version.txt" in names and "installation.json" in names
    assert not any(name.endswith(".pyc") for name in names)


def test_an_unsigned_build_says_so_in_its_name_manifest_and_record(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path
) -> None:
    """The one failure mode worth caring about is a build that lies."""
    artifact = _build(tmp_path / "out", source_root, web_assets, wheel_dir, signed=False)
    assert artifact.path.name.endswith("-unsigned.zip")
    assert artifact.signed is False
    with zipfile.ZipFile(artifact.path) as archive:
        record = json.loads(archive.read("installation.json"))
    assert record["signing"]["applied"] is False
    assert record["signing"]["required_secrets"] == list(
        TARGETS_BY_ID["linux-x86_64"].signing.secrets
    )
    signed = _build(tmp_path / "signed", source_root, web_assets, wheel_dir, signed=True)
    assert signed.path.name == artifact_name("1.2.3", "linux-x86_64", signed=True)
    assert "-unsigned" not in signed.path.name


def test_the_manifest_is_exactly_what_the_updater_accepts(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path, signing_key: bytes
) -> None:
    artifact = _build(
        tmp_path / "out", source_root, web_assets, wheel_dir, private_key=signing_key
    )
    manifest = json.loads(artifact.manifest_path.read_bytes())
    assert set(manifest) == {"schema", "version", "artifact", "sha256"}
    assert manifest["artifact"] == artifact.path.name
    assert manifest["sha256"] == artifact.sha256
    assert artifact.signature_path is not None and artifact.signature_path.is_file()


def test_the_channel_index_is_signed_and_names_one_artifact_per_target(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path, signing_key: bytes
) -> None:
    out = tmp_path / "out"
    artifacts = [
        _build(
            out,
            source_root,
            web_assets,
            wheel_dir,
            target=target.target_id,
            signed=True,
            private_key=signing_key,
        )
        for target in TARGETS
    ]
    index_path, signature_path = build_channel_index(
        out_dir=out, version="1.2.3", channel="stable", artifacts=artifacts, private_key=signing_key
    )
    assert signature_path is not None
    index = read_channel_index(
        index_path.read_bytes(), signature_path.read_bytes(), public_key_of(signing_key)
    )
    assert set(index["artifacts"]) == {target.target_id for target in TARGETS}
    for target_id, entry in index["artifacts"].items():
        assert entry["artifact"].endswith(f"{target_id}.zip")
        assert entry["signed"] is True


def test_a_channel_index_cannot_be_built_from_unsignable_artifacts(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path
) -> None:
    artifact = _build(tmp_path / "out", source_root, web_assets, wheel_dir)
    with pytest.raises(ReleaseError, match="release_artifact_unsigned_manifest"):
        build_channel_index(
            out_dir=tmp_path / "out", version="1.2.3", channel="stable", artifacts=[artifact]
        )


def test_the_build_refuses_an_incomplete_or_mislabelled_release(
    tmp_path: Path, source_root: Path, web_assets: Path
) -> None:
    with pytest.raises(ReleaseError, match="release_wheels_missing"):
        collect_payload(source_root=source_root, web_assets=web_assets, wheel_dir=tmp_path / "none")
    with pytest.raises(ReleaseError, match="release_web_assets_missing"):
        collect_payload(source_root=source_root, web_assets=tmp_path / "empty")
    with pytest.raises(ReleaseError, match="release_source_incomplete"):
        collect_payload(source_root=tmp_path / "nothing")
    with pytest.raises(ReleaseError, match="release_target_unknown"):
        target_for("solaris-sparc")
    with pytest.raises(ReleaseError, match="release_version_invalid"):
        build_bundle(
            out_dir=tmp_path / "out",
            version="1.2",
            target=target_for("linux-x86_64"),
            entries=[],
        )


def test_the_cli_builds_indexes_and_verifies_a_whole_release(
    tmp_path: Path,
    source_root: Path,
    web_assets: Path,
    wheel_dir: Path,
    signing_key: bytes,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The workflow calls exactly this. Testing it here is testing the pipeline."""
    monkeypatch.setenv("RAIKER_RELEASE_SIGNING_KEY", signing_key.hex())
    out = tmp_path / "dist"
    for target in TARGETS:
        assert (
            main(
                [
                    "build",
                    "--version",
                    "1.2.3",
                    "--target",
                    target.target_id,
                    "--out",
                    str(out),
                    "--source-root",
                    str(source_root),
                    "--web-assets",
                    str(web_assets),
                    "--wheel-dir",
                    str(wheel_dir),
                    "--signed",
                ]
            )
            == 0
        )
    assert main(["channel", "--version", "1.2.3", "--dir", str(out)]) == 0
    capsys.readouterr()
    assert main(["verify", "--dir", str(out)]) == 0
    verified = capsys.readouterr().out
    for target in TARGETS:
        assert f"verified {target.target_id}" in verified


def test_verification_fails_on_a_tampered_artifact(
    tmp_path: Path,
    source_root: Path,
    web_assets: Path,
    wheel_dir: Path,
    signing_key: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_RELEASE_SIGNING_KEY", signing_key.hex())
    out = tmp_path / "dist"
    main(
        [
            "build", "--version", "1.2.3", "--target", "linux-x86_64", "--out", str(out),
            "--source-root", str(source_root), "--web-assets", str(web_assets),
            "--wheel-dir", str(wheel_dir), "--signed",
        ]
    )
    main(["channel", "--version", "1.2.3", "--dir", str(out)])
    bundle = out / artifact_name("1.2.3", "linux-x86_64", signed=True)
    bundle.write_bytes(bundle.read_bytes() + b"tampered")
    assert main(["verify", "--dir", str(out)]) == 2


def test_an_index_for_another_target_is_refused_not_ignored(
    tmp_path: Path, source_root: Path, web_assets: Path, wheel_dir: Path, signing_key: bytes
) -> None:
    out = tmp_path / "out"
    artifact = _build(
        out, source_root, web_assets, wheel_dir, target="macos-arm64", signed=True,
        private_key=signing_key,
    )
    index_path, signature_path = build_channel_index(
        out_dir=out, version="1.2.3", channel="stable", artifacts=[artifact],
        private_key=signing_key,
    )
    assert signature_path is not None
    with pytest.raises(UpdateError, match="channel_target_unavailable"):
        select_update(
            index=index_path.read_bytes(),
            signature=signature_path.read_bytes(),
            public_key=public_key_of(signing_key),
            target="windows-x86_64",
            current_version="1.0.0",
        )
