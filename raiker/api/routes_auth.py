"""Authentication routes: register, login, MFA, logout, elevation.

The server drives the login state machine (see ``raiker.auth.accounts``). A
password-only success returns a ``mfa_pending`` ticket that cannot reach any
governed API; only MFA verification upgrades it to a ``control`` session.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from raiker.api import client_hint
from raiker.api.auth import REMOTE_ACCESS_SUSPENDED, AuthMiddleware
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.proxy_guard import is_remote_request
from raiker.api.refusals import refusal
from raiker.api.routes_instances import _require_loopback
from raiker.api.schemas import (
    ChangePasswordRequest,
    ElevateRequest,
    LoginRequest,
    MfaCodeRequest,
    MfaVerifyRequest,
    PasswordRecoveryBeginRequest,
    PasswordRecoveryCompleteRequest,
    RegisterRequest,
    serialize_dto,
)
from raiker.api.session_cookie import clear as clear_session_cookie
from raiker.api.session_cookie import issue as issue_session_cookie
from raiker.api.sessions import ApiSessionStore
from raiker.api.wire import Ok
from raiker.api.wire.auth import (
    AccountDeletionPreview,
    BootstrapStatusView,
    DeviceSessionView,
    ElevatedTokenView,
    LoginResultView,
    MfaEnrollmentView,
    PasswordRecoveryBeginView,
    SessionsRevokedView,
    SessionStateView,
    WhoamiView,
)
from raiker.auth.accounts import AccountService, AuthError, LoginResult, Origin

router = APIRouter()


def _service(request: Request) -> AccountService:
    return AccountService(_ws(request))


def _origin(request: Request) -> Origin:
    """BUG-358 — ``remote`` for anything that is not provably this computer."""
    return "remote" if is_remote_request(request.scope) else "local"


def _remote_event(request: Request, kind: str, **detail: object) -> None:
    from raiker.app.remote_access import record_event
    from raiker.storage.sqlite import SQLiteStore

    record_event(SQLiteStore(_ws(request)), kind, **detail)  # type: ignore[arg-type]


def _require_remote_ready(request: Request) -> None:
    """Remote sign-in is refused outright while remote access is suspended.

    It says so (``remote_access_suspended``) instead of the generic failure:
    whether two-step sign-in is on describes the host, not an account, and the
    owner at another device needs to know that a password will not help.
    """
    from raiker.app.remote_access import mfa_readiness
    from raiker.storage.sqlite import SQLiteStore

    if not mfa_readiness(SQLiteStore(_ws(request)))["ready"]:
        _remote_event(request, "remote_sign_in_refused", reason="suspended")
        raise refusal(status.HTTP_403_FORBIDDEN, REMOTE_ACCESS_SUSPENDED)


def _result_body(result: LoginResult, request: Request, response: Response) -> LoginResultView:
    """The login result, and — on a full session — the cookie that survives a reload.

    BUG-253. The bearer token still travels in the body on this computer,
    because the CLI, the tray and the tests use it. The cookie is set alongside
    it so refreshing the page keeps the session, and the CSRF token it must be
    paired with is returned here rather than parsed back out of a cookie by the
    page.

    BUG-358 — to another device the token is **not** returned: a browser there
    holds the session only as an ``HttpOnly``, ``Secure``, ``SameSite=Strict``
    cookie, which page script cannot read or send anywhere else.
    """
    csrf_token = None
    if result.stage == "session" and result.token:
        csrf_token = issue_session_cookie(request, response, result.token)
    remote = _origin(request) == "remote"
    return LoginResultView(
        stage=result.stage,
        principal_id=result.principal_id,
        token=None if remote else result.token,
        ticket=result.ticket,
        csrf_token=csrf_token,
    )


@router.post("/api/auth/register")
async def register(body: RegisterRequest, request: Request, response: Response) -> dict[str, Any]:
    _require_loopback(request)
    service = _service(request)
    try:
        service.register(body.username, body.password)
        result = service.login(body.username, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return serialize_dto(_result_body(result, request, response))


@router.post("/api/auth/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    origin = _origin(request)
    if origin == "remote":
        _require_remote_ready(request)
    try:
        result = _service(request).login(
            body.username,
            body.password,
            body.device_label,
            origin=origin,
            client_hint=client_hint.describe(request.headers.get("user-agent")),
        )
    except AuthError as exc:
        if origin == "remote":
            _remote_event(request, "remote_sign_in_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return serialize_dto(_result_body(result, request, response))


@router.get("/api/auth/bootstrap-status")
async def bootstrap_status(request: Request) -> dict[str, Any]:
    can_register = not AccountService(_ws(request))._store.list_accounts()  # noqa: SLF001
    return serialize_dto(BootstrapStatusView(can_register=can_register))


@router.post("/api/auth/password-recovery/begin")
async def begin_password_recovery(
    body: PasswordRecoveryBeginRequest, request: Request
) -> dict[str, Any]:
    # Always acknowledge with the same shape. The opaque ticket is returned for
    # both known and unknown users; only a real short-lived ticket can complete.
    _require_loopback(request)
    ticket = _service(request).begin_password_recovery(body.username)
    return serialize_dto(PasswordRecoveryBeginView(ok=True, ticket=ticket))


@router.post("/api/auth/password-recovery/complete")
async def complete_password_recovery(
    body: PasswordRecoveryCompleteRequest, request: Request
) -> dict[str, Any]:
    _require_loopback(request)
    try:
        _service(request).complete_password_recovery(body.ticket, body.code, body.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return serialize_dto(Ok())


@router.post("/api/auth/mfa/verify")
async def mfa_verify(body: MfaVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    origin = _origin(request)
    if origin == "remote":
        _require_remote_ready(request)
    try:
        result = _service(request).verify_mfa(body.ticket, body.code, origin=origin)
    except AuthError as exc:
        if origin == "remote":
            _remote_event(request, "remote_mfa_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    if origin == "remote":
        _remote_event(request, "remote_signed_in", device=client_hint.describe(request.headers.get("user-agent")))
    return serialize_dto(_result_body(result, request, response))


@router.post("/api/auth/mfa/enroll")
async def mfa_enroll(request: Request) -> dict[str, Any]:
    """Start enrolment, or (BUG-358) a reset of an active one, which needs fresh MFA.

    A reset is staged: the current authenticator keeps working, and remote
    access with it, until the new one's first code is confirmed.
    """
    middleware = AuthMiddleware(_ws(request))
    session, principal = middleware.authenticate(request)
    if _service(request).mfa_enrolled(principal.principal_id):
        session, principal = middleware.require_fresh_mfa(request)
    secret, uri, codes = _service(request).begin_enroll_mfa(principal.principal_id)
    return serialize_dto(
        MfaEnrollmentView(secret=secret, provisioning_uri=uri, backup_codes=tuple(codes))
    )


@router.post("/api/auth/mfa/activate")
async def mfa_activate(body: MfaCodeRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        _service(request).activate_mfa(principal.principal_id, body.code, session.session_id)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return serialize_dto(Ok())


@router.post("/api/auth/mfa/disable")
async def mfa_disable(request: Request) -> dict[str, Any]:
    """Turn MFA off, with fresh MFA; remote access is suspended at once (BUG-358)."""
    session, principal = AuthMiddleware(_ws(request)).require_fresh_mfa(request)
    # The page's own signed-in session (its cookie) is kept beside the
    # five-minute elevated one, so turning MFA off does not sign the owner out
    # of the page they did it from. Every other device is signed out.
    from raiker.api.session_cookie import cookie_token

    browser = cookie_token(request)
    store = ApiSessionStore(_ws(request))
    browser_session = store.get_by_token(browser) if browser else None
    also_keep = (
        browser_session.session_id
        if browser_session is not None and browser_session.principal_id == principal.principal_id
        else ""
    )
    _service(request).disable_mfa(
        principal.principal_id, keep_session_id=session.session_id, also_keep=also_keep
    )
    _suspend_remote_access(request, reason="mfa_disabled")
    return serialize_dto(Ok())


def _suspend_remote_access(request: Request, *, reason: str) -> None:
    """Record and announce that other devices just lost access, when they had it."""
    from raiker.app.remote_access import load_state
    from raiker.notify.remote_access_notifier import notify_remote_access_suspended
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(_ws(request))
    record = getattr(request.app.state, "remote_access", None)
    listening = record is not None and record.listener is not None and not record.disabled
    if not listening and load_state(store).desired.mode == "local":
        return
    _remote_event(request, "suspended", reason=reason)
    notify_remote_access_suspended(store, reason=reason)


@router.post("/api/auth/elevate")
async def elevate(body: ElevateRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        token = _service(request).grant_elevated(
            principal.principal_id,
            password=body.password,
            mfa_code=body.mfa_code,
            origin=_origin(request),
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return serialize_dto(ElevatedTokenView(token=token))


@router.post("/api/auth/password")
async def change_password(body: ChangePasswordRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        _service(request).change_password(
            principal.principal_id,
            body.old_password,
            body.new_password,
            keep_session_id=session.session_id,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return serialize_dto(Ok())


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, Any]:
    session, _principal = AuthMiddleware(_ws(request)).authenticate(request)
    ApiSessionStore(_ws(request)).revoke_session(session.session_id)
    # Revoking server-side is what actually ends the session; clearing the
    # cookie is what stops the next reload trying to use a dead one.
    clear_session_cookie(response)
    return serialize_dto(Ok())


@router.get("/api/auth/whoami")
async def whoami(request: Request) -> dict[str, Any]:
    """Who this browser is — the governed read, which refuses when nobody is (BUG-253).

    A safe read, so no CSRF proof is required. It answers 401 exactly as every
    other governed route does when there is no live session. That is right for a
    caller that *needs* an identity — the CLI, a script, a test — and wrong for
    the page's own boot probe, which has ``/api/auth/session-state`` instead.
    """
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    return serialize_dto(
        WhoamiView(
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            scope=session.scope,
        )
    )


@router.get("/api/auth/session-state")
async def session_state(request: Request, response: Response) -> dict[str, Any]:
    """Whether this browser is signed in — an answer, never a failure (BUG-267).

    The page asks this once on boot to decide between the workspace and the lock
    screen, and "nobody" is one of the two expected answers. Asking it of
    ``/api/auth/whoami`` made the browser write a failed request to the console
    on every locked load, which is how a console stops being the place a real
    fault stands out. So the boot question gets a route that answers it: ``200``
    with a null principal, and ``200`` with the principal when there is one.

    It is not a second way in. Nothing here is readable without a live session —
    a caller that is not signed in learns only that it is not signed in, which is
    what it asked. The stale readable CSRF cookie is cleared on that answer, so
    the *next* load has nothing to ask with and does not ask at all.
    """
    try:
        session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    except HTTPException as refusal:
        # Only "not authenticated" means nobody. Any other refusal is something
        # the caller should see rather than have translated into a null
        # principal — and clearing the owner's cookie on one would sign them out
        # over a fault that had nothing to do with their session.
        if refusal.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        clear_session_cookie(response)
        return serialize_dto(SessionStateView(principal_id=None, display_name=None, scope=None))
    return serialize_dto(
        SessionStateView(
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            scope=session.scope,
        )
    )


@router.get("/api/auth/sessions")
async def list_device_sessions(request: Request) -> list[dict[str, Any]]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    store = ApiSessionStore(_ws(request))
    epoch = _service(request).mfa_epoch(principal.principal_id)
    return serialize_dto(
        [
            DeviceSessionView(
                session_id=str(row["session_id"]),
                created_at=str(row["created_at"]),
                last_seen_at=row["last_seen_at"],
                device_label=row["device_label"],
                revoked=bool(row["revoked"]),
                expires_at=row["expires_at"],
                scope=str(row["scope"] or "control"),
                current=row["session_id"] == session.session_id,
                origin=str(row.get("origin") or "local"),
                # MFA-verified against the enrolment in force now; a session
                # verified before a reset reads as not verified.
                mfa_verified=str(row.get("assurance") or "") == "mfa"
                and row.get("mfa_epoch") is not None
                and int(row["mfa_epoch"]) == epoch,
                client_hint=row.get("client_hint"),
                absolute_expires_at=row.get("absolute_expires_at"),
            )
            for row in store.list_for_principal(principal.principal_id)
            # A sign-in ticket, a recovery ticket and a five-minute elevation
            # are steps of something the owner is doing, not devices.
            if str(row.get("scope") or "control") not in {"mfa_pending", "password_recovery", "elevated"}
        ]
    )


@router.post("/api/auth/sessions/revoke-others")
async def revoke_other_device_sessions(request: Request) -> dict[str, Any]:
    """Sign out every other device; this one stays signed in."""
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    revoked = ApiSessionStore(_ws(request)).revoke_others_for_principal(
        principal.principal_id, session.session_id
    )
    if _origin(request) == "remote" or revoked:
        _remote_event(request, "sessions_revoked", count=revoked)
    return serialize_dto(SessionsRevokedView(ok=True, revoked=revoked))


@router.post("/api/auth/sessions/{session_id}/revoke")
async def revoke_device_session(session_id: str, request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    store = ApiSessionStore(_ws(request))
    if not store.owns_session(principal.principal_id, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    store.revoke_session(session_id)
    return serialize_dto(Ok())


#: DEC-10 step 8 — what deleting an account does not reach. Said on the
#: confirmation, because "permanently removes this account" read as "and
#: everything it ever touched".
ACCOUNT_DELETION_KEEPS: tuple[str, ...] = (
    "Folders you attached to a project stay on disk, untouched.",
    "Raiker's audit log, checkpoints and generated files in this workspace's "
    ".raiker folder stay until you delete that folder.",
    "Anything already sent to a model provider, a messaging service or an MCP "
    "server stays with them under their own retention.",
    "Backups you made of this workspace keep a copy.",
)


def _account_username(workspace: Any, principal_id: str) -> str:
    from raiker.storage.sqlite import SQLiteStore

    for account in SQLiteStore(workspace).list_accounts():
        if account.get("principal_id") == principal_id:
            return str(account.get("username") or "")
    return ""


@router.get("/api/account/deletion-preview")
async def account_deletion_preview(request: Request) -> dict[str, Any]:
    """DEC-10 step 8 — the server's own count of what Delete account removes."""
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    from raiker.storage.sqlite import SQLiteStore

    counts = SQLiteStore(_ws(request)).account_deletion_preview(principal.principal_id)
    return serialize_dto(
        AccountDeletionPreview(
            username=_account_username(_ws(request), principal.principal_id),
            kept=list(ACCOUNT_DELETION_KEEPS),
            **counts,
        )
    )


@router.delete("/api/account")
async def delete_account(request: Request, confirm: str = "") -> dict[str, Any]:
    """Irreversibly delete this account (DEC-10 step 8).

    Requires an elevated (re-authenticated) session *and* the account's
    username typed as ``confirm``: the step-up proves who is asking, the typed
    name proves which irreversible thing they meant to ask for.
    """
    _session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    from raiker.storage.sqlite import SQLiteStore

    username = _account_username(_ws(request), principal.principal_id)
    if not username or confirm != username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason_code": "account_delete_unconfirmed"},
        )
    SQLiteStore(_ws(request)).purge_account(principal.principal_id)
    return serialize_dto(Ok())
