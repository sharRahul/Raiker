"""What this installation is, and where its updates would come from.

BUG-44. The product has to be able to answer two questions honestly before it can
offer to update itself: *what am I running*, and *is there a channel to ask*. Both
answers must be able to be "nothing" — the overwhelmingly common case in
development is a source checkout with no channel at all, and a build that
described itself as a signed release because a file was missing would be the one
failure mode worth caring about.

So provenance is read from ``installation.json``, which
:func:`raiker.app.release.build_bundle` writes *inside* the artifact. It is
produced by the build, not typed afterwards, and its ``signing.applied`` flag is
set from whether platform signing actually ran. Absent, malformed, or from a
schema this code does not know: the installation is reported as a source
checkout, unpackaged and unsigned, with the reason stated. Nothing infers
"signed" from the absence of evidence.

The channel is owner-configured and absent by default. Raiker makes no outbound
request to look for updates until someone has said where to look and pinned the
public key that signs it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import raiker
from raiker.app.release import TARGETS_BY_ID, current_target
from raiker.app.update import (
    ChannelUpdate,
    RecoveryPoint,
    UpdateError,
    recovery_points,
    select_update,
)

INSTALLATION_FILE = "installation.json"
#: The version an installation reports when it has no record to read. Kept
#: identical to the placeholder in ``pyproject.toml`` so nothing invents a
#: release number for a checkout that has never been released.
UNKNOWN_VERSION = "0.0.0"


@dataclass(frozen=True)
class Installation:
    """Provenance of the running Raiker, as it will be shown to its owner."""

    version: str
    target: str | None
    packaged: bool
    signed: bool
    channel: str | None
    commit: str | None
    built_at: str | None
    installer_formats: tuple[str, ...]
    install_root: Path
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "target": self.target,
            "packaged": self.packaged,
            "signed": self.signed,
            "channel": self.channel,
            "commit": self.commit,
            "built_at": self.built_at,
            "installer_formats": list(self.installer_formats),
            "install_root": str(self.install_root),
            "note": self.note,
        }


_SOURCE_NOTE = (
    "Running from a source checkout. This installation was not produced by the "
    "release pipeline, so it carries no signature and cannot update itself in "
    "place — update it the way you installed it."
)
_MALFORMED_NOTE = (
    "An installation record is present but could not be read, so this is "
    "reported as an unsigned source installation. Reinstall from a signed "
    "release artifact to restore verifiable provenance."
)


#: How far above the installed package to look for the record before concluding
#: there isn't one. A ``.deb`` installs to ``/opt/raiker`` and puts the package
#: inside ``/opt/raiker/venv/lib/pythonX.Y/site-packages/raiker`` — five levels —
#: so the walk has to be deep enough for that and bounded enough that it cannot
#: wander up to ``/`` and adopt a stranger's file.
_RECORD_SEARCH_DEPTH = 6


def _record_path(install_root: Path | None = None) -> tuple[Path, Path | None]:
    """The install root and its record, or ``None`` when there is no record.

    Three layouts have to resolve, and the installer's is the awkward one:

    * the unpacked artifact — ``<root>/installation.json`` beside
      ``<root>/service/raiker``;
    * a source checkout — no record at all, which is the honest answer;
    * an installed package — the environment lives *inside* the install root, so
      the record is several directories above ``site-packages``.

    ``RAIKER_INSTALL_ROOT`` short-circuits all of it and is what the installers'
    launcher scripts set, because a value the installer knows beats a search.
    """
    if install_root is not None:
        root = Path(install_root)
        candidate = root / INSTALLATION_FILE
        return root, candidate if candidate.is_file() else None
    declared = os.environ.get("RAIKER_INSTALL_ROOT", "").strip()
    if declared:
        root = Path(declared)
        candidate = root / INSTALLATION_FILE
        if candidate.is_file():
            return root, candidate
    package_root = Path(raiker.__file__).resolve().parent
    root = package_root.parent
    for ancestor in [root, *root.parents][:_RECORD_SEARCH_DEPTH]:
        candidate = ancestor / INSTALLATION_FILE
        if candidate.is_file():
            return ancestor, candidate
    return root, None


def detect_installation(install_root: Path | None = None) -> Installation:
    """Read this installation's provenance, defaulting to "source checkout"."""
    root, record = _record_path(install_root)
    if record is None:
        return Installation(
            version=UNKNOWN_VERSION,
            target=None,
            packaged=False,
            signed=False,
            channel=None,
            commit=None,
            built_at=None,
            installer_formats=(),
            install_root=root,
            note=_SOURCE_NOTE,
        )
    try:
        parsed = json.loads(record.read_text(encoding="utf-8"))
        signing = parsed["signing"]
        installation = Installation(
            version=str(parsed["version"]),
            target=str(parsed["target"]),
            packaged=True,
            signed=bool(signing["applied"]),
            channel=str(parsed["channel"]),
            commit=parsed.get("commit"),
            built_at=parsed.get("built_at"),
            installer_formats=tuple(str(item) for item in parsed.get("installer_formats", ())),
            install_root=root,
            note="",
        )
    except (OSError, ValueError, KeyError, TypeError):
        return Installation(
            version=UNKNOWN_VERSION,
            target=None,
            packaged=False,
            signed=False,
            channel=None,
            commit=None,
            built_at=None,
            installer_formats=(),
            install_root=root,
            note=_MALFORMED_NOTE,
        )
    if parsed.get("schema") != 1 or installation.target not in TARGETS_BY_ID:
        return Installation(
            version=UNKNOWN_VERSION,
            target=None,
            packaged=False,
            signed=False,
            channel=None,
            commit=None,
            built_at=None,
            installer_formats=(),
            install_root=root,
            note=_MALFORMED_NOTE,
        )
    note = (
        ""
        if installation.signed
        else (
            "This build was produced without platform signing. It is a test "
            "build; automatic updates refuse unsigned artifacts."
        )
    )
    return Installation(**{**installation.__dict__, "note": note})


# ── the update channel, as the owner configured it ───────────────────────


@dataclass(frozen=True)
class ChannelConfig:
    """Where to ask for updates, and the key whose signature will be trusted."""

    url: str
    public_key: bytes
    channel: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "channel": self.channel,
            # The key identifies the publisher; a short fingerprint is enough to
            # confirm the right one is pinned without pasting it around.
            "public_key_fingerprint": self.public_key.hex()[:16],
        }


def update_root(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "updates"


def recovery_root(workspace_root: str | Path) -> Path:
    return update_root(workspace_root) / "recovery"


def channel_config_path(workspace_root: str | Path) -> Path:
    return update_root(workspace_root) / "channel.json"


def read_channel_config(workspace_root: str | Path) -> ChannelConfig | None:
    """The configured channel, or ``None``. A malformed one is ``None`` too."""
    path = channel_config_path(workspace_root)
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return ChannelConfig(
            url=str(parsed["url"]),
            public_key=bytes.fromhex(str(parsed["public_key"])),
            channel=str(parsed.get("channel", "stable")),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_channel_config(
    workspace_root: str | Path, *, url: str, public_key: str, channel: str = "stable"
) -> ChannelConfig:
    """Pin a channel. HTTPS only, and a key that is actually an Ed25519 key.

    Refusing plain HTTP is not the security boundary — the signature is — but a
    channel fetched in the clear tells a network observer exactly which version
    a host runs, and there is no reason to offer that.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise UpdateError("channel_url_invalid")
    try:
        key = bytes.fromhex(public_key.strip())
    except ValueError:
        raise UpdateError("channel_public_key_invalid") from None
    if len(key) != 32:
        raise UpdateError("channel_public_key_invalid")
    if not channel.strip() or Path(channel).name != channel:
        raise UpdateError("channel_name_invalid")
    path = channel_config_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"url": url, "public_key": key.hex(), "channel": channel}, indent=2) + "\n",
        encoding="utf-8",
    )
    return ChannelConfig(url=url, public_key=key, channel=channel)


@dataclass(frozen=True)
class UpdateStatus:
    """Everything the owner is shown about updating, in one honest answer."""

    state: str
    message: str
    installation: Installation
    channel: ChannelConfig | None
    available: ChannelUpdate | None
    recovery: list[RecoveryPoint]
    checked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "installation": self.installation.to_dict(),
            "channel": self.channel.to_dict() if self.channel else None,
            "available": self.available.to_dict() if self.available else None,
            "recovery_points": [point.to_dict() for point in self.recovery],
            "checked_at": self.checked_at,
        }


#: States, and what each one means to the person reading it:
#:
#: ``source_checkout``  this Raiker was not installed from a release artifact.
#: ``no_channel``       packaged, but no update channel has been pinned.
#: ``unsigned_build``   packaged from a build that never ran platform signing.
#: ``up_to_date``       the channel has nothing newer.
#: ``available``        a newer, signed release exists for this target.
#: ``unreachable``      the channel could not be read; nothing was changed.
STATE_MESSAGES = {
    "source_checkout": _SOURCE_NOTE,
    "no_channel": (
        "No update channel is configured, so Raiker never contacts one. Pin a "
        "channel URL and its release public key to receive signed updates."
    ),
    "unsigned_build": (
        "This build was produced without platform signing, so it is not eligible "
        "for automatic updates. Reinstall from a signed release artifact."
    ),
    "up_to_date": "This is the newest release on the configured channel.",
    "unreachable": (
        "The update channel could not be read. Nothing was downloaded and "
        "nothing about this installation changed."
    ),
}


def update_status(
    workspace_root: str | Path,
    *,
    installation: Installation | None = None,
    fetched_index: tuple[bytes, bytes] | None = None,
    checked_at: str | None = None,
) -> UpdateStatus:
    """Decide, from local facts plus an optionally-fetched index, what to say.

    Split from the fetch on purpose: every refusal above is reachable without a
    network, which is what lets a test cover them and what keeps a status read
    in the UI from being an outbound request.
    """
    install = installation or detect_installation()
    config = read_channel_config(workspace_root)
    points = recovery_points(recovery_root(workspace_root))

    def status(state: str, *, available: ChannelUpdate | None = None, message: str = "") -> UpdateStatus:
        return UpdateStatus(
            state=state,
            message=message or STATE_MESSAGES.get(state, state),
            installation=install,
            channel=config,
            available=available,
            recovery=points,
            checked_at=checked_at,
        )

    if not install.packaged:
        return status("source_checkout")
    if not install.signed:
        return status("unsigned_build")
    if config is None:
        return status("no_channel")
    if fetched_index is None:
        return status("up_to_date", message="Not checked yet on this host.")

    index, signature = fetched_index
    detected = current_target()
    target = install.target or (detected.target_id if detected is not None else "")
    try:
        available = select_update(
            index=index,
            signature=signature,
            public_key=config.public_key,
            target=target,
            current_version=install.version,
        )
    except UpdateError as exc:
        return status(
            "unreachable",
            message=(
                f"The update channel was refused ({exc}). Nothing was downloaded "
                "and nothing about this installation changed."
            ),
        )
    if available is None:
        return status("up_to_date")
    return status(
        "available",
        available=available,
        message=(
            f"Version {available.version} is available on the "
            f"{available.channel} channel for {available.target}."
        ),
    )


def last_check_path(workspace_root: str | Path) -> Path:
    return update_root(workspace_root) / "last-check.json"


def record_check(workspace_root: str | Path, status: UpdateStatus) -> None:
    """Remember the last answer, so a later read is not silently a stale one.

    Only the outcome is kept — state, message, offered version, and when. The
    index itself is not cached: a cached index is a second copy of the thing the
    signature protects, and re-fetching costs one request.
    """
    path = last_check_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "state": status.state,
                "message": status.message,
                "available_version": status.available.version if status.available else None,
                "checked_at": status.checked_at,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_last_check(workspace_root: str | Path) -> dict[str, Any] | None:
    path = last_check_path(workspace_root)
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def artifact_url(config: ChannelConfig, name: str) -> str:
    """Resolve one artifact name against the channel index URL.

    ``name`` has already been checked by :func:`raiker.app.update.
    read_channel_index` to be a bare filename, so this cannot walk out of the
    channel's directory; the check is repeated here because this function is
    also reachable on its own.
    """
    if Path(name).name != name or name in {".", ".."}:
        raise UpdateError("channel_artifact_name_invalid")
    resolved = urljoin(config.url, name)
    base = config.url.rsplit("/", 1)[0] + "/"
    if not resolved.startswith(base):
        raise UpdateError("channel_artifact_name_invalid")
    return resolved
