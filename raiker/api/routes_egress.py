"""The two owner controls this build adds: what web access may not reach, and
whether the git credential is currently lent.

Both are surfaces over decisions the owner makes, not over secrets. The blocklist
routes carry rules; the git routes carry *whether* a token is stored and *what*
the owner approved. **No route here ever returns the token**, and the one that
accepts it takes it and does not read it back.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.runtime.authority.models import Principal
from raiker.runtime.git_credential import GitCredentialBroker, GitCredentialError
from raiker.runtime.web_policy import (
    BLOCKLIST_ENV,
    DEFAULT_BLOCKED_NAMES,
    BlocklistRuleError,
    env_blocklist,
    evaluate_host,
    load_blocklist,
    parse_rule,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _store(request: Request) -> SQLiteStore:
    return SQLiteStore(_ws(request))


class BlocklistRuleRequest(BaseModel):
    rule: str = Field(min_length=1, max_length=253)
    note: str = Field(default="", max_length=500)


class BlocklistTestRequest(BaseModel):
    host: str = Field(min_length=1, max_length=253)


class GitTokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class GitGrantRequest(BaseModel):
    scope: str = Field(default="once")
    session_id: str | None = None
    reason: str = Field(default="", max_length=500)


# ── Web egress blocklist ─────────────────────────────────────────────────────


@router.get("/api/web-access/blocklist")
async def get_blocklist(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """The rules in force, and where each of them came from.

    Three sources with different affordances, so the page can say which rules the
    owner can delete here and which are set outside the app: the built-in names,
    the environment variable, and the owner's own rows.
    """
    session, _principal = auth_data
    store = _store(request)
    return {
        "stored": store.list_web_blocklist(principal_id=session.principal_id),
        "environment": [rule.raw for rule in env_blocklist()],
        "environment_variable": BLOCKLIST_ENV,
        "builtin": list(DEFAULT_BLOCKED_NAMES),
        "effective_count": len(load_blocklist(store, session.principal_id)),
        # Stated on the page rather than left implied: the blocklist governs
        # public destinations, and the address guard is neither in this list nor
        # editable from it.
        "address_guard": {
            "enforced": True,
            "editable": False,
            "description": (
                "Private, loopback, link-local, unique-local, reserved and multicast "
                "addresses are refused on every fetch, including a public name that "
                "resolves to one. This is not a setting."
            ),
        },
    }


@router.post("/api/web-access/blocklist", status_code=status.HTTP_201_CREATED)
async def add_blocklist_rule(
    body: BlocklistRuleRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Add one rule, refusing it here if it cannot be compiled into a matcher."""
    session, _principal = auth_data
    try:
        rule = parse_rule(body.rule)
    except BlocklistRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    rule_id = _store(request).add_web_blocklist_rule(
        rule.raw, rule.kind,
        principal_id=session.principal_id, note=body.note, created_by=session.principal_id,
    )
    return {"rule_id": rule_id, "rule": rule.raw, "kind": rule.kind}


@router.delete("/api/web-access/blocklist/{rule_id}")
async def delete_blocklist_rule(
    rule_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, bool]:
    session, _principal = auth_data
    removed = _store(request).delete_web_blocklist_rule(
        rule_id, principal_id=session.principal_id
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown_rule")
    return {"deleted": True}


@router.post("/api/web-access/blocklist/test")
async def test_blocklist(
    body: BlocklistTestRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Answer "would this host be reachable" without fetching anything.

    A blocklist nobody can check is a blocklist nobody trusts. This runs the same
    evaluation a fetch runs — the owner's rules, then the address guard — and
    performs no request to the host itself.
    """
    session, _principal = auth_data
    decision = evaluate_host(body.host, load_blocklist(_store(request), session.principal_id))
    return {
        "host": body.host,
        "allowed": decision.allowed,
        "reason": decision.reason_code,
        # The addresses are the evidence for the verdict; they are the machine's
        # own DNS answer, not content from the host.
        "addresses": list(decision.addresses),
    }


# ── Git credential and grants ────────────────────────────────────────────────


def _broker(request: Request, session: ApiSession) -> GitCredentialBroker:
    return GitCredentialBroker(_store(request), session.principal_id)


@router.get("/api/git-credential")
async def get_git_credential(
    request: Request,
    session_id: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Whether a token is stored and what is currently approved. Never the token."""
    session, _principal = auth_data
    return _broker(request, session).status(session_id=session_id)


@router.put("/api/git-credential")
async def put_git_credential(
    body: GitTokenRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Store the owner's GitHub token, encrypted. Write-only by design."""
    session, _principal = auth_data
    broker = _broker(request, session)
    try:
        broker.store_token(body.token)
    except GitCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        ) from None
    return broker.status()


@router.delete("/api/git-credential")
async def delete_git_credential(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Forget the token and revoke every grant that depended on it."""
    session, _principal = auth_data
    broker = _broker(request, session)
    broker.forget_token()
    return broker.status()


@router.post("/api/git-credential/grant")
async def grant_git_credential(
    body: GitGrantRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Approve git commands once, or for this session."""
    session, _principal = auth_data
    broker = _broker(request, session)
    try:
        broker.grant(body.scope, session_id=body.session_id, reason=body.reason)
    except GitCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.reason
        ) from None
    return broker.status(session_id=body.session_id)


@router.delete("/api/git-credential/grant")
async def revoke_git_credential(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    """Withdraw the approval. The token stays stored; nothing may use it."""
    session, _principal = auth_data
    broker = _broker(request, session)
    broker.revoke()
    return broker.status()
