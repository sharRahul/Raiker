"""Which GitHub account a credential belongs to, asked of GitHub (ADD-27 GH-18).

An account is identified by GitHub's immutable numeric id; the login is for
display, because a login can be renamed and a renamed login must not move a
credential to someone else. The answer comes from ``GET /user`` on the fixed API
host — a control-plane request the owner started — and never carries anything
but the id, the login and what GitHub says about the token's reach and expiry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from raiker.github.hosts import GITHUB_API_BASE
from raiker.github.http import GitHubHttp, GitHubHttpError


@dataclass(frozen=True)
class Account:
    account_id: str
    login: str
    #: What GitHub says the token may do: classic OAuth scopes, if it reports any.
    scopes: list[str] = field(default_factory=list)
    #: When GitHub says the token expires, if it does.
    expires_at: str | None = None


class AccountCheckError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _expiry(raw: str | None) -> str | None:
    """GitHub's ``github-authentication-token-expiration`` (``2026-12-31 23:59:59 UTC``) as ISO."""
    if not raw:
        return None
    from datetime import UTC, datetime

    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S %z"):
        try:
            moment = datetime.strptime(raw.strip(), pattern)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return None


def check_account(token: str, http: GitHubHttp | None = None) -> Account:
    """The account *token* belongs to, or a reason it does not answer for one."""
    client = http or GitHubHttp()
    try:
        response = client.get_json(f"{GITHUB_API_BASE}/user", token=token)
    except GitHubHttpError as exc:
        raise AccountCheckError(exc.reason) from None
    if response.status == 401:
        raise AccountCheckError("github_credential_rejected")
    if response.status == 403:
        raise AccountCheckError("github_credential_forbidden")
    data: Any = response.data
    if response.status != 200 or not isinstance(data, dict) or "id" not in data:
        raise AccountCheckError(f"github_account_unreadable:{response.status}")
    scopes = [
        part.strip()
        for part in response.headers.get("x-oauth-scopes", "").split(",")
        if part.strip()
    ]
    return Account(
        account_id=str(data["id"]),
        login=str(data.get("login") or ""),
        scopes=scopes,
        expires_at=_expiry(response.headers.get("github-authentication-token-expiration")),
    )
