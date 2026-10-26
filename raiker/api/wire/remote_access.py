"""BUG-347 / BUG-358 — what the remote-access routes answer with."""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict


class RemoteAccessConfigView(TypedDict):
    mode: Literal["local", "private", "proxy"]
    proxy_kind: Literal["port", "socket"]
    proxy_port: int | None
    proxy_socket: str | None
    private_host: str | None
    private_port: int | None
    tls_cert: str | None
    tls_key: str | None


class RemoteAccessCheckView(TypedDict):
    code: str
    ok: bool
    message: str
    field: str | None
    severity: Literal["error", "warning", "info"]


class RemoteAccessProblem(TypedDict):
    code: str
    message: str


class RemoteAccessMfaView(TypedDict):
    #: This account has two-step sign-in.
    enrolled: bool
    #: Every account has it, so a remote listener may open.
    ready: bool
    accounts_without_mfa: int
    #: A reset is staged and waits for the new authenticator's first code.
    reset_pending: bool


class RemoteAccessListenerView(TypedDict):
    """The remote listener this running host has open; nothing when there is none."""

    mode: Literal["local", "private", "proxy"]
    address: str | None
    source: Literal["settings", "start_options"]
    #: An HTTPS request has reached it, or it serves HTTPS itself.
    https_verified: bool
    #: Turned off while running: it refuses everything until the restart closes it.
    refusing: bool


class RemoteAccessLastStart(TypedDict):
    at: str | None
    outcome: str
    reason: str | None
    message: str | None


class RemoteAccessEventView(TypedDict):
    at: str
    kind: str


class RemoteAccessStatusView(TypedDict):
    """Remote access as it is now, from the running host, and what was asked for."""

    state: Literal["disabled", "enabled", "suspended", "pending_restart", "error"]
    #: What the owner chose. It opens on the next start.
    desired: RemoteAccessConfigView
    #: The one before it, for Roll back; null when there is none.
    previous: RemoteAccessConfigView | None
    active: RemoteAccessListenerView
    mfa: RemoteAccessMfaView
    https: Literal["verified", "not_verified", "not_applicable"]
    #: Where another device opens Raiker, when Raiker can know it.
    connection_address: str | None
    #: The running listener is not the chosen one; a restart applies it.
    restart_required: bool
    #: The host can restart itself (it is registered as a service).
    restartable: bool
    #: Changing the configuration is possible from here (this computer, not start options).
    can_configure: bool
    local_listener: str
    problems: list[RemoteAccessProblem]
    last_start: RemoteAccessLastStart | None
    recent_events: list[RemoteAccessEventView]
    platform: Literal["windows", "macos", "linux", "other"]


class RemoteAccessChecksView(TypedDict):
    ok: bool
    checks: list[RemoteAccessCheckView]
