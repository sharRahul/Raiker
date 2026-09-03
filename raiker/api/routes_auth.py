"""Authentication routes: register, login, MFA, logout, elevation.

The server drives the login state machine (see ``raiker.auth.accounts``). A
password-only success returns a ``mfa_pending`` ticket that cannot reach any
governed API; only MFA verification upgrades it to a ``control`` session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from raiker.api.auth import AuthMiddleware
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
)
from raiker.api.session_cookie import clear as clear_session_cookie
from raiker.api.session_cookie import issue as issue_session_cookie
from raiker.api.sessions import ApiSessionStore
from raiker.auth.accounts import AccountService, AuthError

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _service(request: Request) -> AccountService:
    return AccountService(_ws(request))


def _result_body(result: Any, request: Request, response: Response) -> dict[str, Any]:
    """The login result, and — on a full session — the cookie that survives a reload.

    BUG-253. The bearer token still travels in the body, because the CLI, the
    tray and the tests use it. The cookie is set alongside it so refreshing the
    page keeps the session, and the CSRF token it must be paired with is
    returned here rather than parsed back out of a cookie by the page.
    """
    body = {
        "stage": result.stage,
        "principal_id": result.principal_id,
        "token": result.token,
        "ticket": result.ticket,
        "csrf_token": None,
    }
    if result.stage == "session" and result.token:
        body["csrf_token"] = issue_session_cookie(request, response, result.token)
    return body


@router.post("/api/auth/register")
async def register(body: RegisterRequest, request: Request, response: Response) -> dict[str, Any]:
    _require_loopback(request)
    service = _service(request)
    try:
        service.register(body.username, body.password)
        result = service.login(body.username, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _result_body(result, request, response)


@router.post("/api/auth/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = _service(request).login(body.username, body.password, body.device_label)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return _result_body(result, request, response)


@router.get("/api/auth/bootstrap-status")
async def bootstrap_status(request: Request) -> dict[str, bool]:
    return {"can_register": not AccountService(_ws(request))._store.list_accounts()}  # noqa: SLF001


@router.post("/api/auth/password-recovery/begin")
async def begin_password_recovery(
    body: PasswordRecoveryBeginRequest, request: Request
) -> dict[str, Any]:
    # Always acknowledge with the same shape. The opaque ticket is returned for
    # both known and unknown users; only a real short-lived ticket can complete.
    _require_loopback(request)
    return {"ok": True, "ticket": _service(request).begin_password_recovery(body.username)}


@router.post("/api/auth/password-recovery/complete")
async def complete_password_recovery(
    body: PasswordRecoveryCompleteRequest, request: Request
) -> dict[str, bool]:
    _require_loopback(request)
    try:
        _service(request).complete_password_recovery(body.ticket, body.code, body.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/api/auth/mfa/verify")
async def mfa_verify(body: MfaVerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    try:
        result = _service(request).verify_mfa(body.ticket, body.code)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return _result_body(result, request, response)


@router.post("/api/auth/mfa/enroll")
async def mfa_enroll(request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    secret, uri, codes = _service(request).begin_enroll_mfa(principal.principal_id)
    return {"secret": secret, "provisioning_uri": uri, "backup_codes": codes}


@router.post("/api/auth/mfa/activate")
async def mfa_activate(body: MfaCodeRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        _service(request).activate_mfa(principal.principal_id, body.code, session.session_id)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return {"ok": True}


@router.post("/api/auth/mfa/disable")
async def mfa_disable(request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    _service(request).disable_mfa(principal.principal_id, keep_session_id=session.session_id)
    return {"ok": True}


@router.post("/api/auth/elevate")
async def elevate(body: ElevateRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        token = _service(request).grant_elevated(
            principal.principal_id, password=body.password, mfa_code=body.mfa_code
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return {"token": token}


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
    return {"ok": True}


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, Any]:
    session, _principal = AuthMiddleware(_ws(request)).authenticate(request)
    ApiSessionStore(_ws(request)).revoke_session(session.session_id)
    # Revoking server-side is what actually ends the session; clearing the
    # cookie is what stops the next reload trying to use a dead one.
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/api/auth/whoami")
async def whoami(request: Request) -> dict[str, Any]:
    """Who this browser is, if anyone — the question a reload has to ask (BUG-253).

    A safe read, so no CSRF proof is required. It answers 401 exactly as every
    other governed route does when there is no live session, which is what makes
    it usable as the lock screen's own test.
    """
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    return {
        "principal_id": principal.principal_id,
        "display_name": principal.display_name,
        "scope": session.scope,
    }


@router.get("/api/auth/sessions")
async def list_device_sessions(request: Request) -> list[dict[str, Any]]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    store = ApiSessionStore(_ws(request))
    rows = store.list_for_principal(principal.principal_id)
    for row in rows:
        row["current"] = row["session_id"] == session.session_id
    return rows


@router.post("/api/auth/sessions/{session_id}/revoke")
async def revoke_device_session(session_id: str, request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    store = ApiSessionStore(_ws(request))
    if not store.owns_session(principal.principal_id, session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    store.revoke_session(session_id)
    return {"ok": True}


@router.delete("/api/account")
async def delete_account(request: Request) -> dict[str, Any]:
    # Irreversible: requires an elevated (re-authenticated) session.
    _session, principal = AuthMiddleware(_ws(request)).authenticate(
        request, required_scope="elevated"
    )
    from raiker.storage.sqlite import SQLiteStore

    SQLiteStore(_ws(request)).purge_account(principal.principal_id)
    return {"ok": True}
