from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from raiker.api.proxy_guard import is_remote_request
from raiker.api.refusals import refusal
from raiker.api.session_cookie import cookie_token, csrf_failure
from raiker.api.sessions import ApiSession, ApiSessionStore
from raiker.runtime.authority.models import RAIKER_RUNTIME, Principal, PrincipalType
from raiker.storage.sqlite import SQLiteStore

#: How often a session's last activity is written. Often enough to show which
#: device is in use; rare enough not to write on every request.
TOUCH_INTERVAL_SECONDS = 60

#: BUG-358 — refusal codes for a remote request without the assurance it needs.
REMOTE_MFA_REQUIRED = "remote_mfa_required"
REMOTE_ACCESS_SUSPENDED = "remote_access_suspended"
FRESH_MFA_REQUIRED = "fresh_mfa_required"


class AuthMiddleware:
    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._session_store = ApiSessionStore(self._workspace_root)
        self._sqlite = SQLiteStore(self._workspace_root)

    @staticmethod
    def _scope_satisfies(session_scope: str, required_scope: str) -> bool:
        if required_scope == "host_control":
            return session_scope in {"host_control", "control", "elevated"}
        if required_scope == "control":
            return session_scope in {"control", "elevated"}
        if required_scope == "elevated":
            return session_scope == "elevated"
        return session_scope == required_scope

    def authenticate(
        self, request: Request, required_scope: str = "control"
    ) -> tuple[ApiSession, Principal]:
        # Two ways in, and the difference decides whether CSRF applies (BUG-253).
        # A bearer header is never attached by a browser on its own, so a
        # cross-site page cannot produce one and the header path needs no further
        # proof. A cookie *is* attached automatically, which is what makes it
        # survive a reload and what makes the double-submit check below
        # mandatory for anything that changes state.
        auth_header = request.headers.get("Authorization", "")
        raw_token: str
        from_cookie = False
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[len("Bearer "):]
            if not raw_token.strip():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Empty token",
                )
        else:
            cookie = cookie_token(request)
            if cookie is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing or malformed Authorization header",
                )
            raw_token = cookie
            from_cookie = True
        if from_cookie:
            failure = csrf_failure(request)
            if failure is not None:
                raise refusal(status.HTTP_403_FORBIDDEN, failure)
        session = self._session_store.get_by_token(raw_token)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        if session.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )
        if session.is_expired():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        principal = self._resolve_principal(session.principal_id)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session principal not found",
            )
        if not principal.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session principal not active",
            )
        if not self._scope_satisfies(session.scope, required_scope):
            raise refusal(status.HTTP_403_FORBIDDEN, "scope_insufficient")
        remote = is_remote_request(request.scope)
        if remote:
            self._require_remote_assurance(session)
        self._touch(session, remote=remote)
        return session, principal

    def _require_remote_assurance(self, session: ApiSession) -> None:
        """BUG-358 — another device needs a session made there with a password and a code.

        Enforced here, on every authenticated request, so no route and no
        client can skip it. A session from this computer — password-only or
        not — is refused from another device, so a token copied off this
        machine opens nothing remotely. A remote session is refused once the
        enrolment it was verified against is reset or turned off, and every
        remote session is refused while the account has no MFA at all: that is
        remote access suspended. Both answer 401, so a remote page returns to
        its sign-in screen rather than showing an error over a dead session.
        """
        account = self._sqlite.get_account(session.principal_id)
        if account is None or not account.get("mfa_enrolled"):
            raise refusal(status.HTTP_401_UNAUTHORIZED, REMOTE_ACCESS_SUSPENDED)
        epoch = int(account.get("mfa_epoch") or 0)
        if session.origin != "remote" or session.assurance != "mfa" or session.mfa_epoch != epoch:
            raise refusal(status.HTTP_401_UNAUTHORIZED, REMOTE_MFA_REQUIRED)

    def _touch(self, session: ApiSession, *, remote: bool) -> None:
        """Note activity at most once a minute; a remote session's idle limit slides with it."""
        from datetime import UTC, datetime

        from raiker.auth.accounts import REMOTE_SESSION_IDLE_TTL
        from raiker.contracts.ids import utc_now

        now = utc_now()
        if session.last_seen_at:
            try:
                last = datetime.fromisoformat(session.last_seen_at.replace("Z", "+00:00"))
                if (datetime.now(UTC) - last).total_seconds() < TOUCH_INTERVAL_SECONDS:
                    return
            except ValueError:
                pass
        try:
            self._session_store.touch(
                session.session_id,
                now,
                slide_seconds=REMOTE_SESSION_IDLE_TTL if remote and session.origin == "remote" and session.scope == "control" else None,
            )
        except Exception:  # noqa: BLE001 - activity is a record, never a reason to refuse
            return

    def require_fresh_mfa(self, request: Request) -> tuple[ApiSession, Principal]:
        """An elevated session granted, minutes ago, on an MFA code from the current enrolment.

        For the actions that change who can reach Raiker or how it is
        protected: turning MFA off, resetting it, and changing remote access.
        A password-only elevation does not count.
        """
        session, principal = self.authenticate(request, required_scope="elevated")
        account = self._sqlite.get_account(session.principal_id)
        epoch = int(account.get("mfa_epoch") or 0) if account else -1
        if session.assurance != "mfa" or session.mfa_epoch != epoch:
            raise refusal(status.HTTP_403_FORBIDDEN, FRESH_MFA_REQUIRED)
        return session, principal

    def _resolve_principal(self, principal_id: str) -> Principal | None:
        raw = self._sqlite.get_principal(principal_id)
        if raw is None:
            return None
        return Principal(
            principal_id=str(raw["principal_id"]),
            principal_type=PrincipalType(str(raw["principal_type"])),
            display_name=str(raw.get("display_name", "")),
            delegated_by_user_id=str(raw["delegated_by_user_id"]) if raw.get("delegated_by_user_id") else None,
            model_profile_id=str(raw["model_profile_id"]) if raw.get("model_profile_id") else None,
            session_id=str(raw["session_id"]) if raw.get("session_id") else None,
            role_ids=raw.get("role_ids", ()),
            domain_scopes=raw.get("domain_scopes", ()),
            max_runtime_mode=str(raw.get("max_runtime_mode", RAIKER_RUNTIME)),
            created_at=str(raw.get("created_at", "")),
            expires_at=str(raw["expires_at"]) if raw.get("expires_at") else None,
            is_active=bool(raw.get("is_active", 1)),
        )


def denial_403(reason_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"ok": False, "reason_code": reason_code},
    )
