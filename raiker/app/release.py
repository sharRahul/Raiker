"""The release build: reproducible artifacts, and the signing they require.

BUG-44. Publishing Raiker as an application needs two things a source checkout
cannot invent: code-signing identities, and a machine of each target OS to build
and sign on. What it *can* own is everything either side of that — what a
release artifact contains, that building it twice produces the same bytes, which
signing identity each target requires, and the signed manifest the update
boundary in :mod:`raiker.app.update` will verify before it touches an
installation.

So this module is the release, as data and as code, and
``.github/workflows/release.yml`` is a thin manually-triggered wrapper that runs
it once per target on that target's own runner. The workflow holds the secrets;
this module holds the decisions, which is what makes them testable on any
machine.

**Nothing here ever claims an artifact is signed.** ``signing.applied`` is set
from whether the platform signing step actually ran with a real identity, it
travels inside the artifact in ``installation.json``, and it is what the running
application reports back to its owner. An unsigned build is a legitimate thing to
produce — you cannot test a pipeline you refuse to run — but it says so, in the
filename, in the manifest, and in the product.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import sys
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

RELEASE_SCHEMA = 1
#: A fixed timestamp for every archive member. Reproducibility is the point: two
#: builds of one commit must produce one digest, and a build clock is the
#: easiest way to lose that. 1980-01-01 is the earliest a zip can express.
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)
_EXECUTABLE = 0o755
_REGULAR = 0o644
#: Directories that are build output, caches, or another platform's noise. None
#: of them belong in an artifact, and each one that slipped in would be bytes
#: that differ between two builds of the same commit.
_EXCLUDED_DIRS = frozenset(
    {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}
)
_EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".so.debug")


class ReleaseError(RuntimeError):
    """A refusal from the release build. The message is a stable reason code."""


@dataclass(frozen=True)
class SigningIdentity:
    """What signing one target's installers actually requires.

    Held as data so the workflow, the documentation and the product all read the
    same list, and so a test can assert that no target is quietly allowed to
    publish without one.
    """

    tool: str
    secrets: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "secrets": list(self.secrets), "note": self.note}


@dataclass(frozen=True)
class ReleaseTarget:
    """One platform Raiker publishes for, and the runner that can build it."""

    target_id: str
    os_name: str
    arch: str
    runner: str
    installer_formats: tuple[str, ...]
    signing: SigningIdentity

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "os": self.os_name,
            "arch": self.arch,
            "runner": self.runner,
            "installer_formats": list(self.installer_formats),
            "signing": self.signing.to_dict(),
        }


_APPLE = SigningIdentity(
    tool="codesign + notarytool",
    secrets=(
        "APPLE_DEVELOPER_ID_CERTIFICATE",
        "APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD",
        "APPLE_DEVELOPER_ID_IDENTITY",
        "APPLE_NOTARY_ISSUER_ID",
        "APPLE_NOTARY_KEY_ID",
        "APPLE_NOTARY_PRIVATE_KEY",
    ),
    note=(
        "A Developer ID Application certificate signs the bundle; notarytool "
        "submits it to Apple and the ticket is stapled to the .dmg. Gatekeeper "
        "refuses an unnotarised build on a machine that did not create it."
    ),
)
_AUTHENTICODE = SigningIdentity(
    tool="signtool",
    secrets=("WINDOWS_AUTHENTICODE_CERTIFICATE", "WINDOWS_AUTHENTICODE_PASSWORD"),
    note=(
        "An Authenticode certificate signs the .msi with an RFC-3161 timestamp, "
        "so the signature outlives the certificate. SmartScreen treats an "
        "unsigned installer as unknown software."
    ),
)
_LINUX = SigningIdentity(
    tool="gpg (detached) + release Ed25519 manifest",
    secrets=("LINUX_PACKAGE_SIGNING_KEY", "LINUX_PACKAGE_SIGNING_KEY_PASSWORD"),
    note=(
        "The .deb is signed with the repository GPG key and the AppImage carries "
        "a detached signature; both are additionally covered by the release "
        "manifest the updater verifies."
    ),
)

#: Every platform of the distribution design's release table, with the runner
#: that can build it. macOS is two targets, not one universal binary: the native
#: dependency wheels differ per architecture, and a packaging failure must be
#: attributable to the architecture it happened on.
TARGETS: tuple[ReleaseTarget, ...] = (
    # The design allows ".dmg or .pkg"; the pipeline builds ".pkg", which is the
    # one of the two that installs rather than only presenting a folder.
    ReleaseTarget("macos-arm64", "macos", "arm64", "macos-14", (".pkg",), _APPLE),
    ReleaseTarget("macos-x86_64", "macos", "x86_64", "macos-13", (".pkg",), _APPLE),
    ReleaseTarget(
        "windows-x86_64", "windows", "x86_64", "windows-2022", (".msi",), _AUTHENTICODE
    ),
    ReleaseTarget(
        "linux-x86_64", "linux", "x86_64", "ubuntu-22.04", (".AppImage", ".deb"), _LINUX
    ),
)
TARGETS_BY_ID: dict[str, ReleaseTarget] = {target.target_id: target for target in TARGETS}


def target_for(target_id: str) -> ReleaseTarget:
    try:
        return TARGETS_BY_ID[target_id]
    except KeyError:
        raise ReleaseError("release_target_unknown") from None


def current_target() -> ReleaseTarget | None:
    """The target this machine can build, or ``None`` if it is not one."""
    systems = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
    machines = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64", "amd64": "x86_64"}
    os_name = systems.get(platform.system())
    arch = machines.get(platform.machine().lower())
    for target in TARGETS:
        if target.os_name == os_name and target.arch == arch:
            return target
    return None


@dataclass(frozen=True)
class BundleEntry:
    """One file in the artifact: where it comes from, and where it lands."""

    arcname: str
    source: Path


@dataclass(frozen=True)
class ReleaseArtifact:
    path: Path
    sha256: str
    version: str
    target_id: str
    channel: str
    signed: bool
    manifest_path: Path
    signature_path: Path | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.path.name,
            "sha256": self.sha256,
            "version": self.version,
            "target": self.target_id,
            "channel": self.channel,
            "signed": self.signed,
            "manifest": self.manifest_path.name,
            "signature": self.signature_path.name if self.signature_path else None,
        }


def artifact_name(version: str, target_id: str, *, signed: bool) -> str:
    """The filename, which states the target and whether it was signed.

    The ``-unsigned`` marker is not decoration. A pipeline run without signing
    identities is a useful thing — it proves the build works — and the one way it
    could do harm is by producing a file indistinguishable from a release.
    """
    suffix = "" if signed else "-unsigned"
    return f"raiker-{version}-{target_id}{suffix}.zip"


def _validate_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() and str(int(part)) == part for part in parts):
        raise ReleaseError("release_version_invalid")
    return version


def _iter_files(root: Path, prefix: str) -> Iterator[BundleEntry]:
    for path in sorted(root.rglob("*")):
        if any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if path.name.endswith(_EXCLUDED_SUFFIXES):
            continue
        relative = PurePosixPath(*path.relative_to(root).parts)
        yield BundleEntry(f"{prefix}/{relative}" if prefix else str(relative), path)


def collect_payload(
    *,
    source_root: Path,
    web_assets: Path | None = None,
    wheel_dir: Path | None = None,
) -> list[BundleEntry]:
    """The three things an artifact must carry, per the distribution design.

    The service (``raiker`` and ``apps``), the built web assets, and the
    platform-compatible native dependency wheels — ``sqlcipher3-wheels`` above
    all, which is why the workflow resolves them on the target's own runner
    rather than trusting a development machine's copy.
    """
    root = Path(source_root)
    entries: list[BundleEntry] = []
    for package in ("raiker", "apps"):
        package_root = root / package
        if not package_root.is_dir():
            raise ReleaseError("release_source_incomplete")
        entries.extend(_iter_files(package_root, f"service/{package}"))
    for name in ("pyproject.toml", "README.md", "LICENSE", "NOTICE"):
        candidate = root / name
        if candidate.is_file():
            entries.append(BundleEntry(f"service/{name}", candidate))
    if web_assets is not None:
        assets = Path(web_assets)
        if not (assets / "index.html").is_file():
            raise ReleaseError("release_web_assets_missing")
        entries.extend(_iter_files(assets, "web"))
    if wheel_dir is not None:
        wheels = Path(wheel_dir)
        if not wheels.is_dir() or not any(wheels.glob("*.whl")):
            raise ReleaseError("release_wheels_missing")
        entries.extend(
            BundleEntry(f"wheels/{path.name}", path) for path in sorted(wheels.glob("*.whl"))
        )
    return entries


def installation_record(
    *,
    version: str,
    target: ReleaseTarget,
    channel: str,
    signed: bool,
    commit: str | None = None,
    built_at: str | None = None,
) -> dict[str, Any]:
    """The provenance an installed Raiker reports back to its owner.

    It travels inside the artifact, so what the product says about itself comes
    from the build that produced it and not from a value someone typed later.
    """
    return {
        "schema": RELEASE_SCHEMA,
        "version": version,
        "target": target.target_id,
        "os": target.os_name,
        "arch": target.arch,
        "channel": channel,
        "installer_formats": list(target.installer_formats),
        "commit": commit,
        "built_at": built_at or _reproducible_timestamp(),
        "signing": {
            "tool": target.signing.tool,
            "required_secrets": list(target.signing.secrets),
            "applied": signed,
        },
    }


def _reproducible_timestamp() -> str:
    """``SOURCE_DATE_EPOCH`` when set, so two builds agree; now otherwise."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch.isdigit():
        return datetime.fromtimestamp(int(epoch), tz=UTC).isoformat().replace("+00:00", "Z")
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _write_deterministic_zip(destination: Path, members: Iterable[tuple[str, bytes, bool]]) -> None:
    """Write a zip whose bytes depend only on its contents.

    Sorted names, one fixed timestamp, and a mode normalised to executable or
    not. Anything else — build order, the umask of the runner, the clock —
    would make a second build of one commit produce a second digest, and a
    release that cannot be rebuilt cannot be checked.
    """
    ordered = sorted(members, key=lambda member: member[0])
    seen: set[str] = set()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, payload, executable in ordered:
            if arcname in seen:
                raise ReleaseError("release_duplicate_entry")
            seen.add(arcname)
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_TIME)
            info.create_system = 3  # Unix, on every builder
            info.external_attr = (_EXECUTABLE if executable else _REGULAR) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, payload)


def build_bundle(
    *,
    out_dir: Path | str,
    version: str,
    target: ReleaseTarget,
    entries: Iterable[BundleEntry],
    channel: str = "stable",
    signed: bool = False,
    commit: str | None = None,
    private_key: bytes | None = None,
) -> ReleaseArtifact:
    """Build one target's artifact, its schema-1 manifest, and its signature.

    The manifest is exactly the four fields :func:`raiker.app.update.
    apply_signed_update` will accept — schema, version, artifact filename and
    SHA-256 — signed over its exact bytes. Which target it belongs to lives in
    the artifact name and in the channel index, because widening the manifest
    would mean widening what the updater accepts.
    """
    _validate_version(version)
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    bundle = destination / artifact_name(version, target.target_id, signed=signed)

    record = installation_record(
        version=version, target=target, channel=channel, signed=signed, commit=commit
    )
    members: list[tuple[str, bytes, bool]] = [
        ("version.txt", f"{version}\n".encode(), False),
        (
            "installation.json",
            json.dumps(record, indent=2, sort_keys=True).encode() + b"\n",
            False,
        ),
    ]
    for entry in entries:
        source = Path(entry.source)
        if not source.is_file():
            raise ReleaseError("release_payload_missing")
        executable = bool(source.stat().st_mode & stat.S_IXUSR)
        members.append((entry.arcname, source.read_bytes(), executable))
    _write_deterministic_zip(bundle, members)

    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    manifest = {
        "schema": RELEASE_SCHEMA,
        "version": version,
        "artifact": bundle.name,
        "sha256": digest,
    }
    manifest_path = destination / f"{bundle.name}.manifest.json"
    manifest_bytes = _canonical(manifest)
    manifest_path.write_bytes(manifest_bytes)
    signature_path: Path | None = None
    if private_key is not None:
        signature_path = destination / f"{bundle.name}.manifest.json.sig"
        signature_path.write_bytes(sign(manifest_bytes, private_key))

    return ReleaseArtifact(
        path=bundle,
        sha256=digest,
        version=version,
        target_id=target.target_id,
        channel=channel,
        signed=signed,
        manifest_path=manifest_path,
        signature_path=signature_path,
    )


def _canonical(payload: dict[str, Any]) -> bytes:
    """One byte encoding per manifest. The signature is over these exact bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(payload: bytes, private_key: bytes) -> bytes:
    try:
        return Ed25519PrivateKey.from_private_bytes(private_key).sign(payload)
    except ValueError as exc:
        raise ReleaseError("release_signing_key_invalid") from exc


def public_key_of(private_key: bytes) -> bytes:
    try:
        key = Ed25519PrivateKey.from_private_bytes(private_key)
    except ValueError as exc:
        raise ReleaseError("release_signing_key_invalid") from exc
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def build_channel_index(
    *,
    out_dir: Path | str,
    version: str,
    channel: str,
    artifacts: Iterable[ReleaseArtifact],
    private_key: bytes | None = None,
    released_at: str | None = None,
) -> tuple[Path, Path | None]:
    """The index an installed Raiker reads to learn an update exists.

    One entry per target, each naming the artifact, its digest, and the
    per-artifact manifest and signature the updater will verify before it
    changes anything. The index is itself signed, so a swapped entry is a
    signature failure rather than a download.
    """
    _validate_version(version)
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    entries: dict[str, Any] = {}
    for artifact in artifacts:
        if artifact.version != version:
            raise ReleaseError("release_version_mismatch")
        if artifact.target_id in entries:
            raise ReleaseError("release_duplicate_target")
        if artifact.signature_path is None:
            raise ReleaseError("release_artifact_unsigned_manifest")
        entries[artifact.target_id] = {
            "artifact": artifact.path.name,
            "sha256": artifact.sha256,
            "manifest": artifact.manifest_path.name,
            "signature": artifact.signature_path.name,
            "signed": artifact.signed,
        }
    if not entries:
        raise ReleaseError("release_channel_empty")
    index = {
        "schema": RELEASE_SCHEMA,
        "kind": "channel",
        "channel": channel,
        "version": version,
        "released_at": released_at or _reproducible_timestamp(),
        "artifacts": entries,
    }
    index_path = destination / f"{channel}.json"
    index_bytes = _canonical(index)
    index_path.write_bytes(index_bytes)
    signature_path: Path | None = None
    if private_key is not None:
        signature_path = destination / f"{channel}.json.sig"
        signature_path.write_bytes(sign(index_bytes, private_key))
    return index_path, signature_path


# ── CLI ──────────────────────────────────────────────────────────────────
# The workflow calls these. Keeping the release logic behind a command rather
# than in workflow YAML is what lets `tests/test_release_pipeline.py` assert the
# same behaviour the runner gets.


def _key_from_env(variable: str) -> bytes | None:
    raw = os.environ.get(variable, "").strip()
    if not raw:
        return None
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise ReleaseError("release_signing_key_invalid") from None
    if len(key) != 32:
        raise ReleaseError("release_signing_key_invalid")
    return key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m raiker.app.release",
        description="Build, index and verify Raiker release artifacts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    targets = sub.add_parser("targets", help="Print the release matrix as JSON.")
    targets.add_argument("--target", default=None, help="Print only this target.")

    build = sub.add_parser("build", help="Build one target's artifact and manifest.")
    build.add_argument("--version", required=True)
    build.add_argument("--target", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--source-root", default=".")
    build.add_argument("--web-assets", default=None)
    build.add_argument("--wheel-dir", default=None)
    build.add_argument("--channel", default="stable")
    build.add_argument("--commit", default=None)
    build.add_argument(
        "--signed",
        action="store_true",
        help="Record that platform signing ran. Set only by the signing step.",
    )

    index = sub.add_parser("channel", help="Build and sign the channel index.")
    index.add_argument("--version", required=True)
    index.add_argument("--channel", default="stable")
    index.add_argument("--dir", required=True, help="Directory holding every target's artifacts.")

    verify = sub.add_parser("verify", help="Verify a built directory end to end.")
    verify.add_argument("--dir", required=True)
    verify.add_argument("--channel", default="stable")
    verify.add_argument("--public-key", default=None, help="Hex Ed25519 public key.")
    return parser


def _artifact_from_disk(directory: Path, target_id: str, entry: dict[str, Any]) -> ReleaseArtifact:
    manifest_path = directory / str(entry["manifest"])
    manifest = json.loads(manifest_path.read_bytes())
    return ReleaseArtifact(
        path=directory / str(entry["artifact"]),
        sha256=str(entry["sha256"]),
        version=str(manifest["version"]),
        target_id=target_id,
        channel="",
        signed=bool(entry["signed"]),
        manifest_path=manifest_path,
        signature_path=directory / str(entry["signature"]),
    )


def _rebuild_index(directory: Path, version: str, channel: str) -> list[ReleaseArtifact]:
    artifacts: list[ReleaseArtifact] = []
    for target in TARGETS:
        for signed in (True, False):
            bundle = directory / artifact_name(version, target.target_id, signed=signed)
            if not bundle.is_file():
                continue
            manifest_path = directory / f"{bundle.name}.manifest.json"
            signature_path = directory / f"{bundle.name}.manifest.json.sig"
            if not manifest_path.is_file() or not signature_path.is_file():
                raise ReleaseError("release_manifest_missing")
            artifacts.append(
                ReleaseArtifact(
                    path=bundle,
                    sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
                    version=version,
                    target_id=target.target_id,
                    channel=channel,
                    signed=signed,
                    manifest_path=manifest_path,
                    signature_path=signature_path,
                )
            )
    return artifacts


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except ReleaseError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.command == "targets":
        payload: Any = (
            target_for(args.target).to_dict()
            if args.target
            else [target.to_dict() for target in TARGETS]
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "build":
        target = target_for(args.target)
        entries = collect_payload(
            source_root=Path(args.source_root),
            web_assets=Path(args.web_assets) if args.web_assets else None,
            wheel_dir=Path(args.wheel_dir) if args.wheel_dir else None,
        )
        artifact = build_bundle(
            out_dir=args.out,
            version=args.version,
            target=target,
            entries=entries,
            channel=args.channel,
            signed=bool(args.signed),
            commit=args.commit,
            private_key=_key_from_env("RAIKER_RELEASE_SIGNING_KEY"),
        )
        print(json.dumps(artifact.to_dict(), indent=2))
        return 0

    if args.command == "channel":
        directory = Path(args.dir)
        artifacts = _rebuild_index(directory, args.version, args.channel)
        index_path, signature_path = build_channel_index(
            out_dir=directory,
            version=args.version,
            channel=args.channel,
            artifacts=artifacts,
            private_key=_key_from_env("RAIKER_RELEASE_SIGNING_KEY"),
        )
        print(
            json.dumps(
                {
                    "index": index_path.name,
                    "signature": signature_path.name if signature_path else None,
                    "targets": sorted(a.target_id for a in artifacts),
                },
                indent=2,
            )
        )
        return 0

    # verify
    from raiker.app.update import UpdateError, read_channel_index

    directory = Path(args.dir)
    index_path = directory / f"{args.channel}.json"
    signature_path = directory / f"{args.channel}.json.sig"
    key_hex = args.public_key or os.environ.get("RAIKER_RELEASE_PUBLIC_KEY", "")
    if not key_hex:
        private = _key_from_env("RAIKER_RELEASE_SIGNING_KEY")
        if private is None:
            raise ReleaseError("release_public_key_missing")
        public = public_key_of(private)
    else:
        public = bytes.fromhex(key_hex.strip())
    try:
        index = read_channel_index(
            index_path.read_bytes(), signature_path.read_bytes(), public
        )
    except UpdateError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    for target_id, entry in sorted(index["artifacts"].items()):
        bundle = directory / str(entry["artifact"])
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        if digest != str(entry["sha256"]):
            print(f"refused: artifact_digest_mismatch {target_id}", file=sys.stderr)
            return 2
        print(f"verified {target_id} {bundle.name} {digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
