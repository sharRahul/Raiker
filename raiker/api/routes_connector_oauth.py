# SPDX-License-Identifier: Apache-2.0
"""Browser sign-in for mail and calendar connectors (see ``connector_oauth``)."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.connectors import ConnectorSignInStarted, OAuthClientSaved, OAuthClientsView
from raiker.runtime import connector_oauth
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Raiker sign-in</title><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem">
<h1 style="font-size:1.25rem">{title}</h1><p>{body}</p>
<p><a href="/#/settings?tab=connections">Back to Raiker</a></p></body></html>"""

_REASONS = {
    "connector_sign_in_unknown_or_expired": "This sign-in has expired or was already used. Start it again from Raiker.",
    "connector_sign_in_declined": "Access was not granted, so nothing was connected.",
    "connector_sign_in_code_missing": "The provider did not return a sign-in code. Start it again from Raiker.",
    "connector_sign_in_token_refused": "The provider refused to finish the sign-in. Check the registered client, then try again.",
    "connector_sign_in_token_unreachable": "The provider could not be reached to finish the sign-in. Try again.",
    "connector_sign_in_token_invalid": "The provider answered in a way Raiker could not use. Try again.",
    "oauth_client_not_configured": "No sign-in client is registered for this provider. Add one in Raiker first.",
}


class OAuthClientRequest(StrictRequest):
    client_id: str
    client_secret: str | None = None


def _refuse(exc: connector_oauth.SignInError, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail={"reason_code": exc.reason})


@router.post("/api/connector-oauth/{connector_id}/start")
async def start_connector_sign_in(
    connector_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    session, principal = auth_data
    require_human(principal)
    try:
        url = connector_oauth.start(
            SQLiteStore(_ws(request)), session.principal_id, connector_id, str(request.base_url)
        )
    except connector_oauth.SignInError as exc:
        code = status.HTTP_409_CONFLICT if exc.reason == "oauth_client_not_configured" else status.HTTP_400_BAD_REQUEST
        raise _refuse(exc, code) from exc
    started: ConnectorSignInStarted = {"ok": True, "connector_id": connector_id, "authorize_url": url}
    return serialize_dto(started)


@router.get("/api/connector-oauth/callback")
async def connector_sign_in_callback(
    request: Request, state: str = "", code: str | None = None, error: str | None = None
) -> HTMLResponse:
    """Where the provider sends the browser back.

    No Raiker session comes with it: the owner's system browser is not the app.
    The single-use ``state`` from the owner's own start is what admits it.
    """
    try:
        connector_id = connector_oauth.complete(SQLiteStore(_ws(request)), state, code, error)
    except connector_oauth.SignInError as exc:
        body = _REASONS.get(exc.reason, "The sign-in did not complete.")
        return HTMLResponse(_PAGE.format(title="Sign-in did not complete", body=escape(body)), status_code=400)
    name = {"gmail": "Gmail", "gcal": "Google Calendar", "outlook": "Outlook"}.get(connector_id, connector_id)
    return HTMLResponse(_PAGE.format(title=f"Signed in to {escape(name)}", body="You can close this tab and go back to Raiker."))


@router.get("/api/connector-oauth/clients")
async def connector_oauth_clients(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, object]:
    session, _principal = auth_data
    configured = connector_oauth.clients_configured(SQLiteStore(_ws(request)), session.principal_id)
    view: OAuthClientsView = {"google": configured["google"], "microsoft": configured["microsoft"]}
    return serialize_dto(view)


@router.put("/api/connector-oauth/clients/{provider}")
async def save_connector_oauth_client(
    provider: str,
    body: OAuthClientRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    session, principal = auth_data
    require_human(principal)
    try:
        connector_oauth.save_client(
            SQLiteStore(_ws(request)), session.principal_id, provider, body.client_id, body.client_secret
        )
    except connector_oauth.SignInError as exc:
        raise _refuse(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"reason_code": str(exc)}) from exc
    saved: OAuthClientSaved = {"ok": True, "provider": provider}
    return serialize_dto(saved)
