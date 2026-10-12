"""Lending the git credential for one command, and taking it back afterwards.

The token is never read from the host's environment, where two things follow:
every child process inherits it, including the ones that have nothing to do
with git, and the owner cannot take it back short of restarting the host.

So the token is held in the workspace vault, and reaches a child process
only when three things are true at once: the owner stored it, the owner granted
its use (for one command, or for this session), and the command about to run is
the one the grant was for. It is passed in a constructed environment rather than
on a command line, so it never enters the process table; it is registered with
the redactor before the command starts, so it cannot reach a log, an error, or a
captured stdout even if the command echoes it back.
"""
from __future__ import annotations

import contextlib
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from typing_extensions import TypedDict

from raiker.contracts.ids import utc_now
from raiker.storage.deletion_journal import GIT_CREDENTIAL_FORGET, GIT_GRANT_REVOKE

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

#: The hosts this credential belongs to. A GitHub token answered to another
#: forge is a credential leak wearing a feature's clothes, so the helper built
#: below answers for these names and stays silent for every other one.
CREDENTIAL_HOSTS: tuple[str, ...] = ("github.com", "www.github.com")

#: Everything a lent credential is ever used for. Reads of a public repository
#: need no credential, and nothing here writes to an account: the loan exists so
#: a branch the owner approved can leave this machine.
CREDENTIAL_OPERATIONS: tuple[str, ...] = ("Push a branch you approved",)


def credential_helper(token_var: str, hosts: Sequence[str] = CREDENTIAL_HOSTS) -> str:
    """An inline git credential helper that answers only *hosts*, and only ``get``.

    The helper git ran before this was three words long: it echoed the username
    and the token for whatever git asked about. Git asks about the URL it is
    *currently* contacting, which is not always the URL the remote names — a
    redirect, an ``insteadOf`` rewrite or a submodule points it somewhere else,
    and the helper would have answered each of them with the owner's GitHub
    token. So the request is read and the host in it is checked here, inside the
    child, where it is true regardless of which caller installed the helper and
    how carefully they scoped it.

    ``$1`` is the operation git wants (``get``, ``store`` or ``erase``): only a
    read is answered, so nothing git decides to cache can write back through it.
    The port, when git sends one, is not part of the identity being checked.
    """
    pattern = "|".join(hosts)
    return (
        "!f() { "
        # Only a read. `store` and `erase` exit quietly rather than erroring,
        # because a helper that fails an operation git considers optional turns
        # a successful fetch into a failed command.
        '[ "$1" = get ] || exit 0; '
        "h=; "
        'while IFS= read -r line; do case "$line" in host=*) h=${line#host=} ;; esac; done; '
        f'case "${{h%%:*}}" in {pattern}) ;; *) exit 0 ;; esac; '
        "echo username=x-access-token; "
        f'echo "password=${token_var}"; '
        "}; f"
    )


def credential_config(token_var: str, hosts: Sequence[str] = CREDENTIAL_HOSTS) -> list[str]:
    """``git -c`` values that install the helper for *hosts* and nothing else.

    The empty ``credential.helper`` comes first and is what clears the list:
    whatever this machine has configured — a keychain, a manager, another
    account's token — is dropped, so the credential a governed push uses is the
    one the owner governed. Each host then gets the helper under its own URL, so
    git does not even consult it for an address the credential does not belong
    to; :func:`credential_helper` checks again inside the child.
    """
    helper = credential_helper(token_var, hosts)
    return ["credential.helper=", *(f"credential.https://{host}.helper={helper}" for host in hosts)]


#: Read by the helper below; never interpolated into a command string.
CREDENTIAL_HELPER = credential_helper(RUNTIME_TOKEN_VAR)


#: The dimensions a grant can be narrowed on (GH-17), in the order a refusal
#: names the first one that does not match.
GRANT_BOUNDS: tuple[str, ...] = ("operation", "repository", "branch")


def repository_key(remote_url: str) -> str:
    """``host/owner/name`` for an HTTPS or SSH remote URL, lower-case, without ``.git``.

    The one spelling a grant, a binding and an audit record agree on, so a
    remote written ``https://GitHub.com/Owner/Repo.git/`` and one written
    ``https://github.com/owner/repo`` are the same repository.
    """
    from urllib.parse import urlsplit

    value = (remote_url or "").strip()
    scp = re.match(r"^[A-Za-z0-9._-]+@(?P<host>[A-Za-z0-9.-]+):(?P<path>[^/].*)$", value)
    if scp and "://" not in value:
        host, path = scp.group("host").lower(), scp.group("path").strip("/").lower()
    else:
        parsed = urlsplit(value)
        host, path = (parsed.hostname or "").lower(), parsed.path.strip("/").lower()
    # One repository whichever GitHub host or transport names it.
    if host in ("www.github.com", "ssh.github.com"):
        host = "github.com"
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return f"{host}/{path}" if host and path else ""


class GitCredentialGrant(TypedDict):
    grant_id: str
    scope: str
    status: str
    granted_at: str
    expires_at: str
    session_id: str | None
    uses: int
    operation: str | None
    repository: str | None
    branch: str | None
    credential_id: str | None


class GitCredentialLastUse(TypedDict):
    """DEC-21 Git credential — when the credential was last lent, and for what."""

    at: str
    operation: str | None
    scope: str


class GitCredentialStatus(TypedDict):
    """What a surface needs to render the control. Never the token.

    ``credential_*`` rather than ``token_*``: the API redactor masks any key
    containing "token", which is the right blunt instrument to keep.
    """

    credential_configured: bool
    credential_source: str
    #: ADD-27 GH-18 — the selected credential's method, id and account.
    credential_method: str | None
    credential_id: str | None
    account_login: str | None
    grant: GitCredentialGrant | None
    #: The most recent loan under any grant, or ``None`` if it was never lent.
    last_used: GitCredentialLastUse | None
    scopes: list[str]
    grant_seconds: dict[str, int]
    hosts: list[str]
    operations: list[str]
    checked_at: str


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
    operation: str | None = None
    repository: str | None = None
    branch: str | None = None
    credential_id: str | None = None
    account_id: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> GrantView:
        return cls(
            str(row["grant_id"]), str(row["scope"]), str(row["status"]),
            str(row["granted_at"]), str(row["expires_at"]),
            row.get("session_id"), int(row.get("uses") or 0),
            row.get("operation"), row.get("repository"), row.get("branch"),
            row.get("credential_id"), row.get("account_id"),
        )

    def as_dict(self) -> GitCredentialGrant:
        return {
            "grant_id": self.grant_id,
            "scope": self.scope,
            "status": self.status,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "session_id": self.session_id,
            "uses": self.uses,
            "operation": self.operation,
            "repository": self.repository,
            "branch": self.branch,
            "credential_id": self.credential_id,
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

    def __init__(self, store: SQLiteStore, principal_id: str, *, methods: Any = None, **method_options: Any) -> None:
        from raiker.github.credentials import CredentialMethods

        self._store = store
        self._principal_id = principal_id
        #: ADD-27 GH-18 — which credential, by method, is the one in use.
        self.methods: CredentialMethods = methods or CredentialMethods(
            store, principal_id, record=self._record, **method_options
        )
        if methods is None:
            from raiker.github.auth import GitHubSignIn

            # An App sign-in past its eight hours is refreshed where that can be
            # done without exposing a secret, and otherwise asks for sign-in.
            self.methods.set_refresher(
                lambda row: GitHubSignIn(
                    store, principal_id, http=method_options.get("http"), methods=self.methods
                ).refresh(row)
            )

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        """GH-14 — one metadata-only event per credential decision. Never the token."""
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        with contextlib.suppress(Exception):
            EventLogWriter(self._store).append(
                make_event(
                    session_id="git_credential",
                    turn_id=None,
                    event_type=event_type,
                    actor="git_credential_broker",
                    payload={"principal_id": self._principal_id, **payload},
                )
            )

    def _journal(self, kind: str, object_id: str) -> None:
        """GH-16 — written outside the database, so restoring a backup cannot undo it."""
        from raiker.storage.deletion_journal import record_deletion

        record_deletion(self._store.paths.workspace_root, kind, object_id, self._principal_id)

    # ── storage ──────────────────────────────────────────────────────────
    def _vault(self) -> Any:
        from raiker.runtime.connector_ecosystem import ConnectorVault

        return ConnectorVault(self._store)

    def store_token(self, token: str) -> None:
        """Encrypt and keep the owner's personal token, and make it the one in use.

        Never echoed back by any read. The token keeps the vault key it has had
        since RAIKER-2022, so an existing deployment's token is the same entry.
        """
        from raiker.github.credentials import LEGACY_VAULT_KEY, METHOD_PAT

        value = (token or "").strip()
        if not value:
            raise GitCredentialError("git_token_empty", "A GitHub token is required.")
        if len(value) > 512:
            raise GitCredentialError("git_token_too_long", "That is not a GitHub token.")
        self._vault().put(self._principal_id, CREDENTIAL_KEY, {"token": value})
        rows = self._store.list_git_credentials(self._principal_id)
        row = next(
            (r for r in rows if r["method"] == METHOD_PAT and r.get("secret_ref") == LEGACY_VAULT_KEY),
            None,
        )
        if row is None:
            self.methods.ensure_legacy()
            row = next(
                r for r in self._store.list_git_credentials(self._principal_id)
                if r["method"] == METHOD_PAT and r.get("secret_ref") == LEGACY_VAULT_KEY
            )
        else:
            # A new value is a new credential as far as its account goes.
            self._store.update_git_credential(
                row["credential_id"], status="unverified", account_id=None, account_login=None,
                last_error=None,
            )
        self._store.select_git_credential(self._principal_id, row["credential_id"])
        self._record("git_credential_stored", {"source": "vault", "credential_id": row["credential_id"]})

    def forget_token(self) -> None:
        from raiker.github.credentials import LEGACY_VAULT_KEY, METHOD_PAT

        with contextlib.suppress(Exception), self._store.connect() as connection:
            connection.execute(
                "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
                (self._principal_id, CREDENTIAL_KEY),
            )
        for row in self._store.list_git_credentials(self._principal_id):
            if row["method"] == METHOD_PAT and row.get("secret_ref") == LEGACY_VAULT_KEY:
                self._store.delete_git_credential(row["credential_id"])
        revoked = self._store.revoke_git_credential_grants(self._principal_id)
        self._journal(GIT_CREDENTIAL_FORGET, CREDENTIAL_KEY)
        self._record("git_credential_forgotten", {"grants_revoked": revoked})

    def selected_credential(self) -> dict[str, Any] | None:
        return self.methods.selected()

    def token_configured(self) -> bool:
        """Whether a credential is selected and could be lent — asked without reading it."""
        return self.methods.selected() is not None

    def selected_method(self) -> str | None:
        row = self.methods.selected()
        return str(row["method"]) if row else None

    def token_source(self) -> str:
        """``vault``, ``environment`` or ``none`` as before, or the selected method's name."""
        method = self.selected_method()
        if method is None:
            return "none"
        return {"pat": "vault", "environment": "environment"}.get(method, method)

    # ── grants ───────────────────────────────────────────────────────────
    def grant(
        self,
        scope: str,
        *,
        session_id: str | None = None,
        reason: str = "",
        operation: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
    ) -> GrantView:
        """Record the owner's decision to lend the credential.

        A session grant has to name its session (BUG-335): one made without a
        session lent the credential to every chat and routine for its hour.
        ``operation``, ``repository`` and ``branch`` narrow it further (GH-17).
        """
        if scope not in GRANT_SCOPES:
            raise GitCredentialError(
                "git_grant_scope_invalid",
                "A git grant is either 'once' or 'session'.",
            )
        if scope == "session" and not (session_id or "").strip():
            raise GitCredentialError(
                "git_grant_session_required",
                "A grant for a session has to be made from that conversation; "
                "approve once instead.",
            )
        if not self.token_configured():
            raise GitCredentialError(
                "git_token_not_configured",
                "Store a GitHub token before approving git commands "
                "(Settings → Git credential).",
            )
        selected = self.methods.selected() or {}
        row = self._store.create_git_credential_grant(
            principal_id=self._principal_id,
            scope=scope,
            expires_at=grant_expiry(scope),
            session_id=session_id if scope == "session" else None,
            reason=reason,
            operation=(operation or None),
            repository=(repository or None),
            branch=(branch or None),
            # A grant lends the credential it was made for, not whichever one is
            # selected later (DEC-21b-H: methods are never interchangeable).
            credential_id=selected.get("credential_id"),
            account_id=selected.get("account_id"),
        )
        view = GrantView.from_row({**row, "uses": 0})
        self._record(
            "git_grant_created",
            {
                "grant_id": view.grant_id, "scope": scope, "expires_at": view.expires_at,
                "session_id": view.session_id, "operation": view.operation,
                "repository": view.repository, "branch": view.branch,
            },
        )
        return view

    def revoke(self) -> int:
        revoked = self._store.revoke_git_credential_grants(self._principal_id)
        self._journal(GIT_GRANT_REVOKE, self._principal_id)
        if revoked:
            self._record("git_grant_revoked", {"grants_revoked": revoked})
        return revoked

    def live_grant(self) -> GrantView | None:
        """The one grant in force, whatever it covers — what a surface shows."""
        row = self._store.live_git_credential_grant(self._principal_id)
        return GrantView.from_row(row) if row is not None else None

    def active_grant(self, *, session_id: str | None = None) -> GrantView | None:
        row = self._store.active_git_credential_grant(
            self._principal_id, session_id=session_id
        )
        return GrantView.from_row(row) if row is not None else None

    def covering_grant(
        self,
        *,
        session_id: str | None,
        operation: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
    ) -> GrantView:
        """The grant that covers this exact use, or a refusal naming what does not match."""
        grant = self.live_grant()
        if grant is None:
            raise GitCredentialError(
                "git_grant_required",
                "This git command needs your approval. Approve it once from "
                "Settings → Git credential, or for this conversation from the approval.",
            )
        if grant.scope == "session" and (
            not grant.session_id or not session_id or grant.session_id != session_id
        ):
            raise GitCredentialError(
                "git_grant_other_session",
                "The credential was lent for another conversation. Approve it for this one.",
            )
        selected = self.methods.selected() or {}
        if grant.credential_id and grant.credential_id != selected.get("credential_id"):
            raise GitCredentialError(
                "git_grant_other_credential",
                "The approval was for a different credential than the one now selected.",
            )
        if grant.account_id and selected.get("account_id") and grant.account_id != selected["account_id"]:
            raise GitCredentialError(
                "git_account_mismatch",
                "The selected credential now belongs to a different GitHub account.",
            )
        wanted = {"operation": operation, "repository": repository, "branch": branch}
        for bound in GRANT_BOUNDS:
            granted = getattr(grant, bound)
            if granted and granted != (wanted[bound] or ""):
                raise GitCredentialError(
                    f"git_grant_other_{bound}",
                    f"The credential was lent for {bound} {granted}, not this one.",
                )
        return grant

    @contextlib.contextmanager
    def borrow_for_api(
        self, *, repository: str, operation: str, session_id: str | None = None
    ) -> Iterator[str]:
        """The selected credential as a bearer token for one GitHub API request (GH-56).

        Selection and lending only: the API connector keeps its own gate,
        decision mode and approvals, and nothing here grants it anything. What
        changes is where the token comes from — the method the owner selected,
        narrowed to this repository and operation where the method can be — and
        that the loan is recorded and redacted like a git one. An SSH key cannot
        call the API, so it is refused rather than worked around.
        """
        from raiker.context.redaction import forget_secret, remember_secret
        from raiker.github.credentials import METHOD_SSH, CredentialMethodError

        selected = self.methods.selected()
        if selected is None:
            raise GitCredentialError(
                "git_token_not_configured",
                "No GitHub credential is selected. Connect GitHub in Settings → Connections.",
            )
        if selected["method"] == METHOD_SSH:
            raise GitCredentialError(
                "github_api_needs_token",
                "An SSH key cannot call the GitHub API. Select a sign-in or token for GitHub.",
            )
        try:
            token = self.methods.secret(selected, verify=True, repository=repository, operation=operation)
        except CredentialMethodError as exc:
            raise GitCredentialError(exc.reason, exc.message) from None
        remember_secret(token)
        try:
            self._record(
                "git_credential_lent",
                {
                    "grant_id": None, "scope": "api", "source": self.token_source(),
                    "credential_id": selected["credential_id"], "account_id": selected.get("account_id"),
                    "session_id": session_id, "operation": operation, "repository": repository, "branch": None,
                },
            )
            yield token
        finally:
            forget_secret(token)

    def delegation_grant(
        self,
        delegation_id: str,
        *,
        operation: str | None,
        repository: str | None,
        branch: str | None,
    ) -> GrantView:
        """The owner's delegation, as the grant a lend is made under (GH-50)."""
        from raiker.github.delegations import DelegationError, DelegationService

        try:
            row = DelegationService(self._store, self._principal_id).covering(
                repository or "", operation or "", branch, delegation_id=delegation_id
            )
        except DelegationError:
            row = None
        if row is None:
            raise GitCredentialError(
                "git_delegation_does_not_cover",
                "Your delegation does not cover this repository, branch or operation.",
            )
        selected = self.methods.selected() or {}
        if row.get("credential_id") and row["credential_id"] != selected.get("credential_id"):
            raise GitCredentialError(
                "git_grant_other_credential",
                "The delegation was made for a different credential than the one now selected.",
            )
        return GrantView(
            str(row["delegation_id"]), "delegation", "active", str(row["created_at"]),
            str(row["expires_at"]), None, int(row.get("actions_used") or 0),
            operation, row.get("repository"), branch, row.get("credential_id"), selected.get("account_id"),
        )

    def status(self, *, session_id: str | None = None) -> GitCredentialStatus:
        """What a surface needs to render the control. Never the token."""
        grant = self.live_grant()
        # `credential_*` rather than `token_*`: the API redactor masks any field
        # whose *key* contains "token", which is the right blunt instrument to
        # keep. Renaming the field is cheaper than punching a hole in it.
        selected = self.methods.selected()
        return {
            "credential_configured": selected is not None,
            "credential_source": self.token_source(),
            "credential_method": str(selected["method"]) if selected else None,
            "credential_id": str(selected["credential_id"]) if selected else None,
            "account_login": selected.get("account_login") if selected else None,
            "grant": grant.as_dict() if grant else None,
            "last_used": self._last_use(),
            "scopes": sorted(GRANT_SCOPES),
            "grant_seconds": dict(GRANT_SECONDS),
            # The boundary the credential is issued inside, said by the runtime
            # that enforces it rather than repeated as prose on a page. A
            # surface that asks for a secret should be able to state what the
            # secret will be used for first, and be right about it.
            "hosts": list(CREDENTIAL_HOSTS),
            "operations": list(CREDENTIAL_OPERATIONS),
            "checked_at": utc_now(),
        }

    def _last_use(self) -> GitCredentialLastUse | None:
        row = self._store.last_git_credential_use(self._principal_id)
        if row is None:
            return None
        return {
            "at": str(row["last_used_at"]),
            "operation": row.get("last_operation"),
            "scope": str(row.get("scope") or ""),
        }

    # ── lending ──────────────────────────────────────────────────────────
    @contextlib.contextmanager
    def lend(
        self,
        *,
        session_id: str | None = None,
        operation: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
        delegation_id: str | None = None,
    ) -> Iterator[dict[str, str]]:
        """Yield the environment additions one git command may run with.

        A context manager because the loan has to end. On the way in the token is
        registered with the redactor so nothing captured while it is out can
        carry it; on the way out the grant is consumed and the registration is
        dropped. The value is only ever inside the yielded mapping — callers pass
        that to the child's environment and never log it.

        The grant has to cover this use: its session, and any operation,
        repository or branch it was narrowed to. The legacy
        ``RAIKER_GITHUB_TOKEN`` is lent under exactly the same rule (GH-13).

        With *delegation_id* the router has already found the owner's
        delegation covering this use (GH-50); it stands in for the grant, is
        checked again here against the same operation, repository and branch,
        and is not consumed — its budget was spent when the router let it run.
        """
        from raiker.github.credentials import METHOD_SSH, CredentialMethodError

        grant = (
            self.delegation_grant(delegation_id, operation=operation, repository=repository, branch=branch)
            if delegation_id
            else self.covering_grant(
                session_id=session_id, operation=operation, repository=repository, branch=branch
            )
        )
        selected = self.methods.selected()
        if selected is None:
            raise GitCredentialError(
                "git_token_not_configured",
                "No GitHub credential is selected. Add one in Settings → Git credential.",
            )
        try:
            if selected["method"] == METHOD_SSH:
                token = ""
                environment = self.methods.ssh_environment(selected)
            else:
                token = self.methods.secret(
                    selected, verify=True, repository=repository, operation=operation
                )
                environment = {}
        except CredentialMethodError as exc:
            raise GitCredentialError(exc.reason, exc.message) from None
        from raiker.context.redaction import forget_secret, remember_secret

        if token:
            remember_secret(token)
        try:
            if token:
                # git reads the helper from config we pass per-invocation; the
                # token itself is only ever in the variable above. The entries
                # are host-scoped, so a command that wanders to another address
                # is not offered this credential at all.
                config = credential_config(RUNTIME_TOKEN_VAR)
                environment = {RUNTIME_TOKEN_VAR: token, "GIT_CONFIG_COUNT": str(len(config))}
                for index, entry in enumerate(config):
                    key, _, value = entry.partition("=")
                    environment[f"GIT_CONFIG_KEY_{index}"] = key
                    environment[f"GIT_CONFIG_VALUE_{index}"] = value
            self._record(
                "git_credential_lent",
                {
                    "grant_id": grant.grant_id, "scope": grant.scope,
                    "source": self.token_source(), "credential_id": selected["credential_id"],
                    "account_id": selected.get("account_id"), "session_id": session_id,
                    "operation": operation, "repository": repository, "branch": branch,
                },
            )
            yield environment
        finally:
            if grant.scope != "delegation":
                self._store.consume_git_credential_grant(grant.grant_id, operation)
            if token:
                forget_secret(token)
