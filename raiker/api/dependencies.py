"""The request-scoped values every route module shares (OPT-04).

The workspace off the application and the authenticated caller are read here
once, not redefined per route module. A module imports the one it needs, so
the route's own signature still says what
authority it requires — ``Depends(authenticate)`` — rather than a decorator
deciding it somewhere out of sight.

Nothing here decides authority. ``authenticate`` is :class:`AuthMiddleware`,
unchanged; ``require_human`` is the one principal-type check three routes had
spelled out inline. A route with a different requirement (a host-control scope,
an elevated session) keeps its own helper and says so.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.refusals import refusal
from raiker.api.sessions import ApiSession
from raiker.runtime.authority.models import Principal, PrincipalType

__all__ = [
    "authenticate",
    "refusal",
    "require_human",
    "workspace_path",
    "workspace_root",
]


def workspace_root(request: Request) -> str | Path:
    """The workspace this application instance serves."""
    root: str | Path = request.app.state.workspace_root
    return root


def workspace_path(request: Request) -> Path:
    """The same workspace, as a :class:`Path` for routes that join onto it."""
    return Path(str(request.app.state.workspace_root))


def authenticate(request: Request) -> tuple[ApiSession, Principal]:
    """The caller's session and principal, or the refusal ``AuthMiddleware`` raises."""
    return AuthMiddleware(workspace_root(request)).authenticate(request)


def require_human(principal: Principal) -> None:
    """Refuse a non-human principal: the routes that change what runs are the owner's."""
    if principal.principal_type != PrincipalType.HUMAN:
        raise refusal(status.HTTP_403_FORBIDDEN, "human_principal_required")

