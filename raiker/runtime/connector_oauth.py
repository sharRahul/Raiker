# SPDX-License-Identifier: Apache-2.0
"""Signing in to a mail or calendar account in the owner's browser.

A desktop app's OAuth sign-in, as RFC 8252 describes it: **Connect** opens
the provider's own sign-in page in the browser, and the provider sends the
browser back to this host on the loopback address. Raiker never sees the
password.

* **PKCE S256** and a random single-use ``state`` bind the answer to the
  attempt that asked for it. An attempt belongs to the owner who started it
  and expires after ten minutes.
* The redirect goes only to ``127.0.0.1`` or ``localhost``, the loopback
  redirect both Google and Microsoft accept for a desktop client.
* The access and refresh tokens are kept encrypted in the connector vault,
  under the connector's own slot, where the connector tools read them. They
  never appear in an event, a log or an API response.
* The client is the owner's own registration: a Google Cloud *Desktop app*
  client or a Microsoft Entra *Mobile and desktop* app. Its ID is saved in the
  vault from Settings, or set with ``RAIKER_GOOGLE_OAUTH_CLIENT_ID`` /
  ``RAIKER_MICROSOFT_OAUTH_CLIENT_ID``. Google also issues a desktop client
  secret, which Google documents as not confidential for installed apps.
  Microsoft public clients have none.

Nothing here grants anything. A signed-in account is a credential the
connector's own gate and decision mode still govern.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: How long a sign-in may take before its answer is refused.
ATTEMPT_SECONDS = 600
#: Vault slot prefix for the owner's registered client of a provider.
CLIENT_SLOT = "oauth_client:"


@dataclass(frozen=True)
class OAuthProvider:
    provider_id: str
    label: str
    authorize_url: str
    token_url: str
    token_host: str
    needs_secret: bool
    client_id_env: str
    client_secret_env: str | None
    extra_authorize: tuple[tuple[str, str], ...] = ()
    #: The loopback name the redirect uses. Microsoft ignores the port only on a
    #: registered ``localhost`` redirect; Google accepts any loopback address.
    redirect_host: str = "127.0.0.1"


PROVIDERS: dict[str, OAuthProvider] = {
    "google": OAuthProvider(
        provider_id="google",
        label="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        token_host="oauth2.googleapis.com",
        needs_secret=True,
        client_id_env="RAIKER_GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="RAIKER_GOOGLE_OAUTH_CLIENT_SECRET",
        # A refresh token is issued only with offline access, and only again
        # on a consent screen, so a reconnect gets a fresh one.
        extra_authorize=(("access_type", "offline"), ("prompt", "consent")),
    ),
    "microsoft": OAuthProvider(
        provider_id="microsoft",
        label="Microsoft",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        token_host="login.microsoftonline.com",
        needs_secret=False,
        client_id_env="RAIKER_MICROSOFT_OAUTH_CLIENT_ID",
        client_secret_env=None,
        extra_authorize=(("prompt", "select_account"),),
        redirect_host="localhost",
    ),
}


@dataclass(frozen=True)
class SignInTarget:
    """What one connector signs in to: a provider and the least scope it reads with."""

    connector_id: str
    provider_id: str
    scopes: tuple[str, ...]
    api_host: str


#: Read-only scopes: the connector tools only read.
TARGETS: dict[str, SignInTarget] = {
    "gmail": SignInTarget(
        "gmail", "google", ("https://www.googleapis.com/auth/gmail.readonly",), "gmail.googleapis.com"
    ),
    "gcal": SignInTarget(
        "gcal", "google", ("https://www.googleapis.com/auth/calendar.readonly",), "www.googleapis.com"
    ),
    "outlook": SignInTarget(
        "outlook",
        "microsoft",
        ("offline_access", "User.Read", "Mail.Read", "Calendars.Read"),
        "graph.microsoft.com",
    ),
}

#: The fields of a signed-in credential, as stored in the vault.
SIGNED_IN_SOURCE = "browser_sign_in"


class SignInError(Exception):
    """A sign-in refused for a named reason (a fixed code, never provider text)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class _Attempt:
    principal_id: str
    connector_id: str
    verifier: str
    redirect_uri: str
    created: float


_ATTEMPTS: dict[str, _Attempt] = {}
_LOCK = threading.Lock()


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sweep(now: float) -> None:
    for state in [s for s, a in _ATTEMPTS.items() if now - a.created > ATTEMPT_SECONDS]:
        _ATTEMPTS.pop(state, None)


def target(connector_id: str) -> SignInTarget:
    found = TARGETS.get(connector_id)
    if found is None:
        raise SignInError("connector_sign_in_unsupported")
    return found


def loopback_redirect(base_url: str, redirect_host: str = "127.0.0.1") -> str:
    """The callback on this host, refused unless Raiker was reached on the loopback address."""
    parts = urllib.parse.urlsplit(base_url)
    if parts.scheme != "http" or (parts.hostname or "") not in {"127.0.0.1", "localhost"}:
        raise SignInError("connector_sign_in_needs_loopback")
    port = f":{parts.port}" if parts.port else ""
    return f"http://{redirect_host}{port}/api/connector-oauth/callback"


# ── the owner's registered client ──────────────────────────────────────


def client_for(store: SQLiteStore, principal_id: str, provider_id: str) -> dict[str, str] | None:
    """The client to sign in with: the one saved in Settings, else the environment."""
    from raiker.runtime.connector_ecosystem import ConnectorVault

    provider = PROVIDERS[provider_id]
    saved = ConnectorVault(store).get(principal_id, CLIENT_SLOT + provider_id) if ConnectorVault(store).configured() else None
    client_id = (saved or {}).get("client_id") or os.environ.get(provider.client_id_env, "").strip()
    if not client_id:
        return None
    secret = (saved or {}).get("client_secret") or (
        os.environ.get(provider.client_secret_env, "").strip() if provider.client_secret_env else ""
    )
    if provider.needs_secret and not secret:
        return None
    return {"client_id": client_id, **({"client_secret": secret} if secret else {})}


def save_client(
    store: SQLiteStore, principal_id: str, provider_id: str, client_id: str, client_secret: str | None
) -> None:
    from raiker.runtime.connector_ecosystem import ConnectorVault

    provider = PROVIDERS.get(provider_id)
    if provider is None:
        raise SignInError("oauth_provider_unknown")
    client_id = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not client_id or len(client_id) > 300 or any(ch.isspace() for ch in client_id):
        raise SignInError("oauth_client_id_invalid")
    if provider.needs_secret and not secret:
        raise SignInError("oauth_client_secret_required")
    ConnectorVault(store).put(
        principal_id, CLIENT_SLOT + provider_id, {"client_id": client_id, **({"client_secret": secret} if secret else {})}
    )


def clients_configured(store: SQLiteStore, principal_id: str) -> dict[str, bool]:
    return {pid: client_for(store, principal_id, pid) is not None for pid in PROVIDERS}


# ── the sign-in ────────────────────────────────────────────────────────


def start(store: SQLiteStore, principal_id: str, connector_id: str, base_url: str) -> str:
    """Begin a sign-in; returns the provider URL the owner's browser opens."""
    chosen = target(connector_id)
    provider = PROVIDERS[chosen.provider_id]
    client = client_for(store, principal_id, provider.provider_id)
    if client is None:
        raise SignInError("oauth_client_not_configured")
    redirect_uri = loopback_redirect(base_url, provider.redirect_host)
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(32))
    now = time.monotonic()
    with _LOCK:
        _sweep(now)
        _ATTEMPTS[state] = _Attempt(principal_id, connector_id, verifier, redirect_uri, now)
    query = {
        "client_id": client["client_id"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(chosen.scopes),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        **dict(provider.extra_authorize),
    }
    return f"{provider.authorize_url}?{urllib.parse.urlencode(query)}"


def _take(state: str) -> _Attempt:
    now = time.monotonic()
    with _LOCK:
        _sweep(now)
        attempt = _ATTEMPTS.pop(state, None)
    if attempt is None:
        raise SignInError("connector_sign_in_unknown_or_expired")
    return attempt


def _expires_at(payload: dict[str, Any]) -> str | None:
    seconds = payload.get("expires_in")
    if isinstance(seconds, (int, float)) and seconds > 0:
        return (datetime.now(UTC) + timedelta(seconds=int(seconds))).isoformat()
    return None


def complete(
    store: SQLiteStore,
    state: str,
    code: str | None,
    error: str | None = None,
    *,
    client: httpx.Client | None = None,
) -> str:
    """Finish the sign-in the provider answered; returns the connector connected.

    The attempt is spent whatever happens, so a replayed callback is refused.
    """
    from raiker.contracts.ids import utc_now
    from raiker.runtime.connector_ecosystem import ConnectorVault

    attempt = _take(state or "")
    if error:
        raise SignInError("connector_sign_in_declined")
    if not code:
        raise SignInError("connector_sign_in_code_missing")
    chosen = target(attempt.connector_id)
    provider = PROVIDERS[chosen.provider_id]
    registered = client_for(store, attempt.principal_id, provider.provider_id)
    if registered is None:
        raise SignInError("oauth_client_not_configured")
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": attempt.redirect_uri,
        "client_id": registered["client_id"],
        "code_verifier": attempt.verifier,
        **({"client_secret": registered["client_secret"]} if registered.get("client_secret") else {}),
    }
    owned = client is None
    http = client or httpx.Client(timeout=20.0, follow_redirects=False)
    try:
        response = http.post(provider.token_url, data=form, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise SignInError("connector_sign_in_token_unreachable") from exc
    finally:
        if owned:
            http.close()
    if response.status_code >= 400:
        raise SignInError("connector_sign_in_token_refused")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SignInError("connector_sign_in_token_invalid") from exc
    access = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(access, str) or not access:
        raise SignInError("connector_sign_in_token_invalid")
    credential = {
        "access_token": access,
        "token_url": provider.token_url,
        "client_id": registered["client_id"],
        "source": SIGNED_IN_SOURCE,
        "provider": provider.provider_id,
        "scope": str(payload.get("scope") or " ".join(chosen.scopes)),
    }
    if isinstance(payload.get("refresh_token"), str):
        credential["refresh_token"] = payload["refresh_token"]
    if registered.get("client_secret"):
        credential["client_secret"] = registered["client_secret"]
    ConnectorVault(store).put(attempt.principal_id, attempt.connector_id, credential, _expires_at(payload))
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO connector_installations
               (principal_id, connector_id, enabled, auth_status, installed_at, updated_at)
               VALUES (?, ?, 0, 'connected', ?, ?)
               ON CONFLICT(principal_id, connector_id) DO UPDATE SET
               auth_status='connected', updated_at=excluded.updated_at""",
            (attempt.principal_id, attempt.connector_id, now, now),
        )
    return attempt.connector_id


# ── using a signed-in account ──────────────────────────────────────────


def signed_in(store: SQLiteStore, principal_id: str | None, connector_id: str) -> bool:
    """Whether the owner connected this connector by signing in here."""
    from raiker.runtime.connector_ecosystem import ConnectorVault

    if not principal_id or connector_id not in TARGETS:
        return False
    vault = ConnectorVault(store)
    if not vault.configured():
        return False
    credential = vault.get(principal_id, connector_id)
    return bool(credential and credential.get("source") == SIGNED_IN_SOURCE)


def access_token(
    store: SQLiteStore, principal_id: str | None, connector_id: str, *, client: httpx.Client | None = None
) -> str | None:
    """A current access token for a signed-in connector, refreshed when it has expired."""
    from raiker.runtime.connector_ecosystem import ConnectorVault, credential_status

    if not signed_in(store, principal_id, connector_id):
        return None
    assert principal_id is not None
    vault = ConnectorVault(store)
    credential = vault.get(principal_id, connector_id) or {}
    meta = vault.metadata(principal_id, connector_id) or {}
    if credential_status(meta.get("expires_at")) == "connected":
        return credential.get("access_token") or None
    refresh = credential.get("refresh_token")
    provider = PROVIDERS.get(credential.get("provider", ""))
    if not refresh or provider is None:
        return None
    form = {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": credential.get("client_id", "")}
    if credential.get("client_secret"):
        form["client_secret"] = credential["client_secret"]
    owned = client is None
    http = client or httpx.Client(timeout=20.0, follow_redirects=False)
    try:
        response = http.post(provider.token_url, data=form, headers={"Accept": "application/json"})
    except httpx.HTTPError:
        return None
    finally:
        if owned:
            http.close()
    if response.status_code >= 400:
        return None
    payload = response.json()
    fresh = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(fresh, str) or not fresh:
        return None
    rotated = {**credential, "access_token": fresh}
    if isinstance(payload.get("refresh_token"), str):
        rotated["refresh_token"] = payload["refresh_token"]
    vault.put(principal_id, connector_id, rotated, _expires_at(payload))
    return fresh


def reset_attempts() -> None:
    """Forget every pending attempt (tests only)."""
    with _LOCK:
        _ATTEMPTS.clear()
