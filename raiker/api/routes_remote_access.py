"""Settings → Security → Remote access (BUG-347, BUG-358).

Who may do what here:

* **Read** the status: any signed-in session, on this computer or another
  device. It is the running host's own account of what is open, never what was
  merely asked for.
* **Check, apply and roll back** a configuration: this computer only
  (``loopback_only``), with fresh MFA (an elevated session granted on a code
  from the current enrolment), and — to apply — an explicit confirmation. A
  configuration that fails a check is refused, not saved; it takes effect when
  the host restarts. Start options (``raiker-web --proxy-port`` …) are the
  operator's, so Settings shows them and does not change them.
* **Disable**: any signed-in session, from anywhere. It only narrows, so it
  needs no fresh proof, and it takes effect at once: the remote listener
  refuses everything from this moment until the restart closes it.

Nothing here can bind an arbitrary address: the only remote listener is one of
the three shapes ``raiker.app.remote_access`` validates, and the local listener
is not configurable at all.
"""

from __future__ import annotations

import sys
from typing import Any, cast

from fastapi import APIRouter, Request, status
from pydantic import Field

from raiker.api.auth import AuthMiddleware
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.proxy_guard import RemoteAccessRecord, is_local_request
from raiker.api.refusals import refusal
from raiker.api.routes_instances import _require_loopback
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.wire.remote_access import (
    RemoteAccessChecksView,
    RemoteAccessCheckView,
    RemoteAccessConfigView,
    RemoteAccessEventView,
    RemoteAccessLastStart,
    RemoteAccessListenerView,
    RemoteAccessProblem,
    RemoteAccessStatusView,
)
from raiker.app import remote_access as ra

router = APIRouter()


class RemoteAccessConfigBody(StrictRequest):
    mode: str = Field(max_length=16)
    proxy_kind: str | None = Field(default=None, max_length=16)
    proxy_port: int | None = None
    proxy_socket: str | None = Field(default=None, max_length=512)
    private_host: str | None = Field(default=None, max_length=64)
    private_port: int | None = None
    tls_cert: str | None = Field(default=None, max_length=1024)
    tls_key: str | None = Field(default=None, max_length=1024)


class RemoteAccessApplyBody(StrictRequest):
    config: RemoteAccessConfigBody
    #: The owner read what this exposes and said yes.
    confirm: bool = False


def _store(request: Request) -> Any:
    from raiker.storage.sqlite import SQLiteStore

    return SQLiteStore(_ws(request))


def _record(request: Request) -> RemoteAccessRecord | None:
    record = getattr(request.app.state, "remote_access", None)
    return record if isinstance(record, RemoteAccessRecord) else None


def _local_port(request: Request) -> int:
    port = getattr(request.app.state, "local_port", None)
    if isinstance(port, int):
        return port
    from raiker.app.host import HostControl

    saved = HostControl(_ws(request)).record().get("port")
    return saved if isinstance(saved, int) else 8765


def _platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def _config_view(config: ra.RemoteAccessConfig) -> RemoteAccessConfigView:
    return cast(RemoteAccessConfigView, config.to_dict())


def _parse(body: RemoteAccessConfigBody) -> ra.RemoteAccessConfig:
    try:
        return ra.RemoteAccessConfig.from_dict(body.model_dump())
    except ra.RemoteAccessError as error:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code) from error


def _restartable(request: Request) -> bool:
    from raiker.app.service import registration

    try:
        return registration(_ws(request), port=_local_port(request)).registered
    except Exception:  # noqa: BLE001 - unknown means "restart it yourself"
        return False


def access_summary(request: Request) -> dict[str, Any]:
    """The Host menu's one line: how this host is reached, from the running host."""
    store = _store(request)
    owner = store.original_account_principal_id() or ""
    full = remote_access_status(request, principal_id=owner)
    return {"state": full["state"], "mode": full["active"]["mode"], "address": full["active"]["address"]}


def remote_access_status(request: Request, *, principal_id: str) -> RemoteAccessStatusView:
    """The status Settings, the Host menu and Diagnostics all read."""
    store = _store(request)
    state = ra.load_state(store)
    record = _record(request)
    listener = record.listener if record is not None else None
    refusing = bool(record is not None and record.disabled)
    readiness = ra.mfa_readiness(store)
    account = store.get_account(principal_id) or {}
    enrolled = bool(account.get("mfa_enrolled"))
    startup = record.startup if record is not None else {}
    source = cast(Any, (record.source if record is not None else "settings") or "settings")
    running_config = ra.RemoteAccessConfig.from_dict(startup.get("config") or {}) if listener is not None else ra.RemoteAccessConfig()

    active_mode = running_config.mode if listener is not None else "local"
    https_verified = bool(listener is not None and (listener.kind == "private" or (record is not None and record.https_seen)))
    problems: list[RemoteAccessProblem] = []
    if state.unreadable:
        problems.append({"code": "settings_unreadable", "message": "The remote-access setting could not be read, so Raiker started for this device only."})
    outcome = str(startup.get("outcome") or "local")
    if outcome in {"failed", "fell_back", "unreadable"} and startup.get("message"):
        problems.append({"code": str(startup.get("reason") or outcome), "message": str(startup["message"])})
    if listener is not None and not readiness["ready"]:
        problems.append({"code": "mfa_required", "message": "Two-step sign-in is off, so remote access is suspended. Turn it on again to restore it."})
    if outcome == "suspended_mfa":
        problems.append({"code": "mfa_required", "message": "Remote access did not start because two-step sign-in is off. Turn it on, then restart Raiker."})
    if listener is not None and listener.kind == "proxy" and record is not None and record.https_refused and not record.https_seen:
        problems.append({"code": "remote_https_required", "message": "Requests reached the proxy listener without HTTPS and were refused. Check that the proxy serves https:// and sends X-Forwarded-Proto: https."})
    if record is not None and record.refused:
        problems.append({"code": "proxied_request_refused", "message": f"{record.refused} request{'s' if record.refused != 1 else ''} reached Raiker's local listener through a proxy and {'were' if record.refused != 1 else 'was'} refused. Point the proxy at the remote listener instead."})

    desired = state.desired if state.unreadable is None else ra.RemoteAccessConfig()
    attempted = startup.get("attempted")
    failed_as_chosen = (
        outcome in {"failed", "suspended_mfa"}
        and isinstance(attempted, dict)
        and ra.RemoteAccessConfig.from_dict(attempted) == desired
    )
    restart_required = (
        source == "settings"
        and not (outcome == "failed" and failed_as_chosen)
        and (
            desired.mode != active_mode
            or (listener is not None and desired != running_config)
            or (refusing and desired.mode != "local")
        )
        and not (desired.mode != "local" and outcome == "suspended_mfa" and not readiness["ready"])
    )
    if refusing:
        # Turned off while running: it refuses everything until a restart
        # closes it, or reopens it if remote access was turned on again since.
        state_name = "disabled" if desired.mode == "local" or source != "settings" else "pending_restart"
    elif listener is not None and not readiness["ready"]:
        state_name = "suspended"
    elif listener is not None:
        state_name = "pending_restart" if restart_required else "enabled"
    elif desired.mode != "local" and source == "settings":
        if outcome == "suspended_mfa" or not readiness["ready"]:
            state_name = "suspended"
        elif outcome == "failed" and failed_as_chosen:
            # The setting that failed is still the chosen one: a restart alone
            # would fail again, so it is a problem to fix, not a wait.
            state_name = "error"
        else:
            state_name = "pending_restart"
    else:
        state_name = "disabled"

    if listener is None:
        address = None
    elif listener.kind == "private":
        address = listener.describe()
    else:
        address = None  # the proxy's public https:// address is the proxy's to know
    last_start: RemoteAccessLastStart | None = None
    if startup:
        last_start = {
            "at": cast(Any, startup.get("at")),
            "outcome": outcome,
            "reason": cast(Any, startup.get("reason")),
            "message": cast(Any, startup.get("message")),
        }
    events: list[RemoteAccessEventView] = [
        {"at": str(event["at"]), "kind": str(event["kind"])} for event in ra.recent_events(store, limit=10)
    ]
    active: RemoteAccessListenerView = {
        "mode": cast(Any, active_mode),
        "address": listener.describe() if listener is not None else None,
        "source": source,
        "https_verified": https_verified,
        "refusing": refusing,
    }
    answer: RemoteAccessStatusView = {
        "state": cast(Any, state_name),
        "desired": _config_view(desired),
        "previous": _config_view(state.previous) if state.previous is not None else None,
        "active": active,
        "mfa": {
            "enrolled": enrolled,
            "ready": bool(readiness["ready"]),
            "accounts_without_mfa": int(readiness["without_mfa"]),
            "reset_pending": account.get("mfa_pending_secret_encrypted") is not None,
        },
        "https": "not_applicable" if listener is None else ("verified" if https_verified else "not_verified"),
        "connection_address": address,
        "restart_required": bool(restart_required),
        "restartable": _restartable(request),
        "can_configure": is_local_request(request.scope) and source == "settings",
        "local_listener": f"127.0.0.1:{_local_port(request)}",
        "problems": problems,
        "last_start": last_start,
        "recent_events": events,
        "platform": cast(Any, _platform()),
    }
    return answer


@router.get("/api/remote-access")
async def get_remote_access(request: Request) -> dict[str, Any]:
    """Remote access as the running host has it, and what the next start opens."""
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    answer: RemoteAccessStatusView = remote_access_status(request, principal_id=principal.principal_id)
    return serialize_dto(answer)


def _require_configurable(request: Request) -> None:
    _require_loopback(request)
    record = _record(request)
    if record is not None and record.listener is not None and record.source == "start_options":
        raise refusal(status.HTTP_409_CONFLICT, "remote_access_set_by_start_options")


def _checks(request: Request, config: ra.RemoteAccessConfig) -> list[ra.Check]:
    record = _record(request)
    # The listener this process holds is not "in use by another program", even
    # when it is refusing everything after remote access was turned off.
    running = record.listener if record is not None else None
    checks = ra.validate(config, local_port=_local_port(request), running=running)
    if config.mode != "local" and not ra.mfa_readiness(_store(request))["ready"]:
        checks.insert(
            0,
            ra.Check(
                "mfa_required",
                False,
                "Turn on two-step sign-in first. Remote access needs it for every account, and stays "
                "suspended while it is off.",
                None,
            ),
        )
    return checks


@router.post("/api/remote-access/check")
async def check_remote_access(body: RemoteAccessConfigBody, request: Request) -> dict[str, Any]:
    """Everything that would stop a configuration working, before anything is saved."""
    AuthMiddleware(_ws(request)).authenticate(request)
    _require_configurable(request)
    checks = _checks(request, _parse(body))
    answer: RemoteAccessChecksView = {
        "ok": not ra.blocking(checks),
        "checks": [cast(RemoteAccessCheckView, check.to_dict()) for check in checks],
    }
    return serialize_dto(answer)


@router.post("/api/remote-access/apply")
async def apply_remote_access(body: RemoteAccessApplyBody, request: Request) -> dict[str, Any]:
    """Save a checked configuration for the next start. Fresh MFA and a confirmation."""
    _session, principal = AuthMiddleware(_ws(request)).require_fresh_mfa(request)
    _require_configurable(request)
    config = _parse(body.config)
    if config.mode != "local" and not body.confirm:
        raise refusal(status.HTTP_400_BAD_REQUEST, "remote_access_unconfirmed")
    failing = ra.blocking(_checks(request, config))
    if failing:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, failing[0].code)
    store = _store(request)
    ra.save_desired(store, config, by=principal.principal_id)
    chosen = config.listener()
    ra.record_event(
        store,
        "configured" if config.mode != "local" else "disabled",
        mode=config.mode,
        listener=chosen.describe() if chosen is not None else None,
    )
    if config.mode == "local":
        record = _record(request)
        if record is not None:
            record.disable_now()
    answer: RemoteAccessStatusView = remote_access_status(request, principal_id=principal.principal_id)
    return serialize_dto(answer)


@router.post("/api/remote-access/rollback")
async def rollback_remote_access(request: Request) -> dict[str, Any]:
    """Go back to the configuration before the last change, for the next start."""
    _session, principal = AuthMiddleware(_ws(request)).require_fresh_mfa(request)
    _require_configurable(request)
    store = _store(request)
    state = ra.load_state(store)
    if state.previous is None:
        raise refusal(status.HTTP_409_CONFLICT, "nothing_to_roll_back")
    if state.previous.mode != "local":
        failing = ra.blocking(_checks(request, state.previous))
        if failing:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, failing[0].code)
    ra.rollback(store, by=principal.principal_id)
    ra.record_event(store, "rolled_back", automatic=False, mode=state.previous.mode)
    if state.previous.mode == "local":
        record = _record(request)
        if record is not None:
            record.disable_now()
    answer: RemoteAccessStatusView = remote_access_status(request, principal_id=principal.principal_id)
    return serialize_dto(answer)


@router.post("/api/remote-access/disable")
async def disable_remote_access(request: Request) -> dict[str, Any]:
    """Turn remote access off now, from any signed-in device."""
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    record = _record(request)
    if record is not None and record.listener is not None and record.source == "start_options":
        # Start options cannot be unsaved from here, but the listener can still
        # stop answering at once; the next start without them is local.
        record.disable_now()
    else:
        store = _store(request)
        if ra.load_state(store).desired.mode != "local":
            ra.save_desired(store, ra.RemoteAccessConfig(), by=principal.principal_id)
        if record is not None:
            record.disable_now()
    ra.record_event(_store(request), "disabled", by="remote" if not is_local_request(request.scope) else "local")
    answer: RemoteAccessStatusView = remote_access_status(request, principal_id=principal.principal_id)
    return serialize_dto(answer)
