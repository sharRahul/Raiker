"""Authentication routes: register, login, MFA, logout, elevation.

The server drives the login state machine (see ``raiker.auth.accounts``). A
password-only success returns a ``mfa_pending`` ticket that cannot reach any
governed API; only MFA verification upgrades it to a ``control`` session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    ChangePasswordRequest,
    ElevateRequest,
    LoginRequest,
    MfaCodeRequest,
    MfaVerifyRequest,
    RegisterRequest,
)
from raiker.api.sessions import ApiSessionStore
from raiker.auth.accounts import AccountService, AuthError

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _service(request: Request) -> AccountService:
    return AccountService(_ws(request))


def _result_body(result: Any) -> dict[str, Any]:
    return {
        "stage": result.stage,
        "principal_id": result.principal_id,
        "token": result.token,
        "ticket": result.ticket,
    }


@router.post("/api/auth/register")
async def register(body: RegisterRequest, request: Request) -> dict[str, Any]:
    service = _service(request)
    try:
        service.register(body.username, body.password)
        result = service.login(body.username, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _result_body(result)


@router.post("/api/auth/login")
async def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    try:
        result = _service(request).login(body.username, body.password, body.device_label)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return _result_body(result)


@router.post("/api/auth/mfa/verify")
async def mfa_verify(body: MfaVerifyRequest, request: Request) -> dict[str, Any]:
    try:
        result = _service(request).verify_mfa(body.ticket, body.code)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    return _result_body(result)


@router.post("/api/auth/mfa/enroll")
async def mfa_enroll(request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    secret, uri, codes = _service(request).begin_enroll_mfa(principal.principal_id)
    return {"secret": secret, "provisioning_uri": uri, "backup_codes": codes}


@router.post("/api/auth/mfa/activate")
async def mfa_activate(body: MfaCodeRequest, request: Request) -> dict[str, Any]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        _service(request).activate_mfa(principal.principal_id, body.code)
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
async def logout(request: Request) -> dict[str, Any]:
    session, _principal = AuthMiddleware(_ws(request)).authenticate(request)
    ApiSessionStore(_ws(request)).revoke_session(session.session_id)
    return {"ok": True}
