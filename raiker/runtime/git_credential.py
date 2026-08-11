"""Lending the git credential for one command, and taking it back afterwards.

``RAIKER_GITHUB_TOKEN`` used to be read straight from the host's environment. Two
things follow from that, and both are worse than they look:

* **Every child process inherited it.** A push needed the token, so the host held
  it, so every command the runtime ever launched had it in its environment —
  including the ones that had nothing to do with git.
* **The owner could not take it back.** A credential that lives in the process
  environment is withdrawn by restarting the host, which is not a control anyone
  reaches for.

So the token is held in the workspace vault instead, and reaches a child process
only when three things are true at once: the owner stored it, the owner granted
its use (for one command, or for this session), and the command about to run is
the one the grant was for. It is passed in a constructed environment rather than
on a command line, so it never enters the process table; it is registered with
the redactor before the command starts, so it cannot reach a log, an error, or a
captured stdout even if the command echoes it back.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

CREDENTIAL_KEY = "github_token"
LEGACY_TOKEN_ENV = "RAIKER_GITHUB_TOKEN"

#: The variable the inline credential helper reads inside the child. Deliberately
#: not the name the owner knows: nothing that inherits the host's environment
#: should be able to find the token under the name it was stored as.
RUNTIME_TOKEN_VAR = "RAIKER_GIT_RUNTIME_TOKEN"

#: How long a grant may last, by scope. A session grant is not "forever" — it is
#: a working period, after which the owner is asked again.
GRANT_SECONDS: dict[str, int] = {"once": 300, "session": 3600}
GRANT_SCOPES = frozenset(GRANT_SECONDS)

#: Read by the helper below; never interpolated into a command string.
CREDENTIAL_HELPER = (
    f'!f() {{ echo username=x-access-token; echo "password=${RUNTIME_TOKEN_VAR}"; }}; f'
)


class GitCredentialError(Exception):
    """The credential cannot be lent, and the reason is safe to show."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class GrantView:
    """An owner decision about the credential, as a surface can show it."""

    grant_id: str
    scope: str
    status: str
    granted_at: str
    expires_at: str
    session_id: str | None
    uses: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "scope": self.scope,
            "status": self.status,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "session_id": self.session_id,
            "uses": self.uses,
        }


def grant_expiry(scope: str, *, now: datetime | None = None) -> str:
    if scope not in GRANT_SCOPES:
        raise GitCredentialError("git_grant_scope_invalid", f"Unknown grant scope: {scope}.")
    moment = now or datetime.now(UTC)
    return (
        (moment + timedelta(seconds=GRANT_SECONDS[scope]))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class GitCredentialBroker:
    """Stores the token, records the owner's decision, and lends it once."""

    def __init__(self, store: SQLiteStore, principal_id: str) -> None:
        self._store = store
        self._principal_id = principal_id

    # ── storage ──────────────────────────────────────────────────────────
    def _vault(self) -> Any:
        from raiker.runtime.connector_ecosystem import ConnectorVault

        return ConnectorVault(self._store)

    def store_token(self, token: str) -> None:
        """Encrypt and keep the owner's token. Never echoed back by any read."""
        value = (token or "").strip()
        if not value:
            raise GitCredentialError("git_token_empty", "A GitHub token is required.")
        if len(value) > 512:
            raise GitCredentialError("git_token_too_long", "That is not a GitHub token.")
        self._vault().put(self._principal_id, CREDENTIAL_KEY, {"token": value})

    def forget_token(self) -> None:
        with contextlib.suppress(Exception), self._store.connect() as connection:
            connection.execute(
                "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
                (self._principal_id, CREDENTIAL_KEY),
            )
        self._store.revoke_git_credential_grants(self._principal_id)

    def _token(self) -> str:
        """The stored token, falling back to the legacy environment variable.

        The fallback keeps an existing deployment working across this change; it
        is reported as ``environment`` by :meth:`status` so the owner can see
        which one they are on rather than guessing.
        """
        with contextlib.suppress(Exception):
            stored = self._vault().get(self._principal_id, CREDENTIAL_KEY)
            if stored and stored.get("token"):
                return str(stored["token"]).strip()
        import os

        return os.environ.get(LEGACY_TOKEN_ENV, "").strip()

    def token_configured(self) -> bool:
        return bool(self._token())

    def token_source(self) -> str:
        with contextlib.suppress(Exception):
            stored = self._vault().get(self._principal_id, CREDENTIAL_KEY)
            if stored and stored.get("token"):
                return "vault"
        import os

        return "environment" if os.environ.get(LEGACY_TOKEN_ENV, "").strip() else "none"

    # ── grants ───────────────────────────────────────────────────────────
    def grant(self, scope: str, *, session_id: str | None = None, reason: str = "") -> GrantView:
        """Record the owner's decision to lend the credential."""
        if scope not in GRANT_SCOPES:
            raise GitCredentialError(
                "git_grant_scope_invalid",
                "A git grant is either 'once' or 'session'.",
            )
        if not self.token_configured():
            raise GitCredentialError(
                "git_token_not_configured",
                "Store a GitHub token before approving git commands "
                "(Settings → Git credential).",
            )
        row = self._store.create_git_credential_grant(
            principal_id=self._principal_id,
            scope=scope,
            expires_at=grant_expiry(scope),
            session_id=session_id if scope == "session" else None,
            reason=reason,
        )
        return GrantView(
            row["grant_id"], scope, "active", row["granted_at"], row["expires_at"],
            row.get("session_id"), 0,
        )

    def revoke(self) -> int:
        return self._store.revoke_git_credential_grants(self._principal_id)

    def active_grant(self, *, session_id: str | None = None) -> GrantView | None:
        row = self._store.active_git_credential_grant(
            self._principal_id, session_id=session_id
        )
        if row is None:
            return None
        return GrantView(
            str(row["grant_id"]), str(row["scope"]), str(row["status"]),
            str(row["granted_at"]), str(row["expires_at"]),
            row.get("session_id"), int(row.get("uses") or 0),
        )

    def status(self, *, session_id: str | None = None) -> dict[str, Any]:
        """What a surface needs to render the control. Never the token."""
        grant = self.active_grant(session_id=session_id)
        return {
            "token_configured": self.token_configured(),
            "token_source": self.token_source(),
            "grant": grant.as_dict() if grant else None,
            "scopes": sorted(GRANT_SCOPES),
            "grant_seconds": dict(GRANT_SECONDS),
            "checked_at": utc_now(),
        }

    # ── lending ──────────────────────────────────────────────────────────
    @contextlib.contextmanager
    def lend(self, *, session_id: str | None = None) -> Iterator[dict[str, str]]:
        """Yield the environment additions one git command may run with.

        A context manager because the loan has to end. On the way in the token is
        registered with the redactor so nothing captured while it is out can
        carry it; on the way out the grant is consumed and the registration is
        dropped. The value is only ever inside the yielded mapping — callers pass
        that to the child's environment and never log it.
        """
        grant = self.active_grant(session_id=session_id)
        if grant is None:
            raise GitCredentialError(
                "git_grant_required",
                "This git command needs your approval. Approve it once, or for this "
                "session, from the composer or Settings → Git credential.",
            )
        token = self._token()
        if not token:
            raise GitCredentialError(
                "git_token_not_configured",
                "No GitHub token is stored. Add one in Settings → Git credential.",
            )
        from raiker.context.redaction import forget_secret, remember_secret

        remember_secret(token)
        try:
            yield {
                RUNTIME_TOKEN_VAR: token,
                # git reads the helper from config we pass per-invocation; the
                # token itself is only ever in the variable above.
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "credential.helper",
                "GIT_CONFIG_VALUE_0": CREDENTIAL_HELPER,
            }
        finally:
            self._store.consume_git_credential_grant(grant.grant_id)
            forget_secret(token)
