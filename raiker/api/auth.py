from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from raiker.api.sessions import ApiSession, ApiSessionStore
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.storage.sqlite import SQLiteStore


class AuthMiddleware:
    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._session_store = ApiSessionStore(self._workspace_root)
        self._sqlite = SQLiteStore(self._workspace_root)

    @staticmethod
    def _scope_satisfies(session_scope: str, required_scope: str) -> bool:
        if required_scope == "control":
            return session_scope in {"control", "elevated"}
        if required_scope == "elevated":
            return session_scope == "elevated"
        return session_scope == required_scope

    def authenticate(
        self, request: Request, required_scope: str = "control"
    ) -> tuple[ApiSession, Principal]:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header",
            )
        raw_token = auth_header[len("Bearer "):]
        if not raw_token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty token",
            )
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
        if not self._scope_satisfies(session.scope, required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"ok": False, "reason_code": "scope_insufficient"},
            )
        principal = self._resolve_principal(session.principal_id)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session principal not found",
            )
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
            max_runtime_mode=str(raw.get("max_runtime_mode", "development_preview")),
            created_at=str(raw.get("created_at", "")),
            expires_at=str(raw["expires_at"]) if raw.get("expires_at") else None,
            is_active=bool(raw.get("is_active", 1)),
        )


def denial_403(reason_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"ok": False, "reason_code": reason_code},
    )
