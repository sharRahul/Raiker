# SPDX-License-Identifier: Apache-2.0
"""The host process: its state, the work a quit would interrupt, the folders
the Browse dialog lists, and what this installation says about updating."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.app.release import ReleaseTarget
from raiker.app.service import ServiceRegistration
from raiker.app.update import ChannelUpdate


class HostWaitingWork(TypedDict):
    """One thing a quit would interrupt or leave undone, in the owner's terms."""

    kind: str
    label: str
    detail: str


class HostStatusView(TypedDict):
    state: str
    detail: str
    pid: int | None
    port: int | None
    started_at: str | None
    paused: bool
    paused_since: str | None
    paused_reason: str | None
    waiting: list[HostWaitingWork]


class HostView(HostStatusView):
    """BUG-40 — state, in-flight work, and whether the host starts on its own."""

    service: ServiceRegistration
    restartable: bool


class HostActionResult(HostView):
    """A pause, resume, quit or restart. A quit or restart that would interrupt
    work answers ``waiting_work`` and does nothing until confirmed."""

    ok: bool
    reason_code: NotRequired[str]
    stopping: NotRequired[bool]
    restarting: NotRequired[bool]


class HostPathEntry(TypedDict):
    name: str
    #: The absolute path, which is the whole point: the browser cannot make one.
    path: str
    is_directory: bool


class HostPathListing(TypedDict):
    """BUG-251 — one directory listing from the host, for the Browse… dialog."""

    #: Empty means the top of the machine: drives, home, and the usual folders.
    path: str
    #: Null at the top, "" when the listing is already a root.
    parent: str | None
    separator: str
    workspace_root: str
    entries: list[HostPathEntry]
    truncated: bool
    #: The location is gone or cannot be read — not the same as empty.
    missing: bool


class InstallationView(TypedDict):
    """BUG-44 — what this installation is, read from the build that produced it."""

    version: str
    target: str | None
    packaged: bool
    signed: bool
    channel: str | None
    commit: str | None
    built_at: str | None
    installer_formats: list[str]
    install_root: str
    note: str


class UpdateChannelView(TypedDict):
    url: str
    channel: str
    public_key_fingerprint: str


class RecoveryPointView(TypedDict):
    version: str
    path: str
    files: int
    bytes: int


class ReleaseSigning(TypedDict):
    """What signing a target's installers requires.

    ``required_env`` names the CI variables that hold the signing material. On
    the wire it is not called ``secrets``: the response redactor masks any key
    containing that word, which turned this list of names into a string.
    """

    tool: str
    required_env: list[str]
    note: str


class ReleaseTargetView(TypedDict):
    target_id: str
    os: str
    arch: str
    runner: str
    installer_formats: list[str]
    signing: ReleaseSigning


def release_target(target: ReleaseTarget) -> ReleaseTargetView:
    return {
        "target_id": target.target_id,
        "os": target.os_name,
        "arch": target.arch,
        "runner": target.runner,
        "installer_formats": list(target.installer_formats),
        "signing": {
            "tool": target.signing.tool,
            "required_env": list(target.signing.secrets),
            "note": target.signing.note,
        },
    }


class LastUpdateCheck(TypedDict):
    state: str
    message: str
    available_version: str | None
    checked_at: str | None


UpdateState = Literal[
    "source_checkout", "no_channel", "unsigned_build", "not_checked",
    "up_to_date", "available", "unreachable",
]


class UpdateStatusView(TypedDict):
    """Provenance, channel and recovery points; ``not_checked`` is not an assurance."""

    state: UpdateState
    message: str
    installation: InstallationView
    channel: UpdateChannelView | None
    available: ChannelUpdate | None
    recovery_points: list[RecoveryPointView]
    checked_at: str | None
    targets: list[ReleaseTargetView]
    last_check: LastUpdateCheck | None


class UpdateCheckResult(UpdateStatusView):
    ok: bool


class UpdateApplyResult(UpdateStatusView):
    """The verified update handed to the helper, or why it was not."""

    ok: bool
    updating: bool
    version: NotRequired[str]
    reason_code: NotRequired[str]


class UpdateDeferred(HostStatusView):
    """An update that would interrupt work: the host's own account of that work."""

    ok: bool
    updating: bool
    reason_code: Literal["waiting_work"]
    message: str
