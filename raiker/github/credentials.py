"""The owner's GitHub credentials, by method, and which one is in use (ADD-27 GH-18).

Every credential Raiker may lend is a row in ``git_credentials`` naming its
method, the GitHub account it was verified to belong to, and — for the methods
where Raiker holds the secret — the vault entry the secret is kept under. One
row is *selected*; only it is ever lent, and only under a grant.

Methods are never silently interchangeable. The broker records which credential
and account a grant was made with, and a lend under a different one is refused.
A method whose secret Raiker does not hold (the GitHub CLI's sign-in, an OS
credential-manager entry) is read at lend time and checked against the account
the owner selected, every time, because the program that holds it can switch
accounts without asking Raiker.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.github.accounts import Account, AccountCheckError, check_account
from raiker.github.http import GitHubHttp
from raiker.github.local_methods import (
    GhCli,
    LocalCredentialError,
    OsCredentialHelper,
    SshKeys,
    ssh_command,
    write_known_hosts,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

METHOD_PAT = "pat"
METHOD_ENVIRONMENT = "environment"
METHOD_GH_CLI = "gh_cli"
METHOD_OS_HELPER = "os_helper"
METHOD_SSH = "ssh"
METHOD_APP_USER = "app_user"
#: M-APP-INSTALL — the App acting as itself on one installation (automation).
METHOD_APP_INSTALLATION = "app_installation"

METHODS = (
    METHOD_PAT, METHOD_ENVIRONMENT, METHOD_GH_CLI, METHOD_OS_HELPER, METHOD_SSH,
    METHOD_APP_USER, METHOD_APP_INSTALLATION,
)
#: Methods that authenticate HTTPS with a token; SSH authenticates with a key.
TOKEN_METHODS = frozenset({
    METHOD_PAT, METHOD_ENVIRONMENT, METHOD_GH_CLI, METHOD_OS_HELPER, METHOD_APP_USER,
    METHOD_APP_INSTALLATION,
})
#: Methods whose secret lives somewhere Raiker does not control, so the account
#: is checked again at every lend.
REREAD_METHODS = frozenset({METHOD_GH_CLI, METHOD_OS_HELPER})

#: The vault key the original personal token lives under (RAIKER-2022).
LEGACY_VAULT_KEY = "github_token"
LEGACY_ENV = "RAIKER_GITHUB_TOKEN"

LABELS = {
    METHOD_PAT: "Personal access token",
    METHOD_ENVIRONMENT: "Token in the host environment",
    METHOD_GH_CLI: "GitHub CLI sign-in",
    METHOD_OS_HELPER: "Saved Git credential",
    METHOD_SSH: "SSH key",
    METHOD_APP_USER: "GitHub sign-in",
    METHOD_APP_INSTALLATION: "GitHub App installation",
}

#: How long a re-read credential's account answer is trusted in this process.
_VERIFIED_SECONDS = 600
_verified: dict[str, float] = {}


class CredentialMethodError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


def _fingerprint(secret: str, account_id: str) -> str:
    return hashlib.sha256(f"{account_id}\0{secret}".encode()).hexdigest()


def app_user_vault_keys(credential_id: str) -> tuple[str, str]:
    """Where a GitHub App sign-in's access and refresh tokens are kept — apart (P17)."""
    return f"github_app_user:{credential_id}", f"github_app_refresh:{credential_id}"


class CredentialMethods:
    """The owner's credential rows, and how to read the selected one's secret."""

    def __init__(
        self,
        store: SQLiteStore,
        principal_id: str,
        *,
        http: GitHubHttp | None = None,
        gh: GhCli | None = None,
        helper: OsCredentialHelper | None = None,
        ssh: SshKeys | None = None,
        record: Callable[[str, dict[str, Any]], None] | None = None,
        refresher: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self._store = store
        self._principal_id = principal_id
        self._http = http
        self._gh = gh or GhCli()
        self._helper = helper or OsCredentialHelper()
        self._ssh = ssh or SshKeys()
        self._record = record or (lambda _kind, _payload: None)
        self._refresher = refresher

    # ── vault ────────────────────────────────────────────────────────────
    def _vault(self) -> Any:
        from raiker.runtime.connector_ecosystem import ConnectorVault

        return ConnectorVault(self._store)

    def vault_get(self, key: str) -> dict[str, str] | None:
        with contextlib.suppress(Exception):
            value: dict[str, str] | None = self._vault().get(self._principal_id, key)
            return value
        return None

    def vault_put(self, key: str, payload: dict[str, str], expires_at: str | None = None) -> None:
        self._vault().put(self._principal_id, key, payload, expires_at)

    def vault_delete(self, key: str) -> None:
        with contextlib.suppress(Exception), self._store.connect() as connection:
            connection.execute(
                "DELETE FROM connector_credentials WHERE principal_id=? AND connector_id=?",
                (self._principal_id, key),
            )

    # ── rows ─────────────────────────────────────────────────────────────
    def ensure_legacy(self) -> None:
        """Rows for the credentials that predate them, so nothing working stops.

        The vault's ``github_token`` and the ``RAIKER_GITHUB_TOKEN`` variable each
        get a row the first time anything asks, referencing the secret where it
        already is — it is not decrypted, moved or copied (DEC-21b-Q). If the
        owner selected nothing yet, the vault token is selected, else the
        variable, which is what the broker lent before rows existed.
        """
        rows = self._store.list_git_credentials(self._principal_id)
        methods = {row["method"]: row for row in rows}
        changed = False
        vault_row = next(
            (row for row in rows if row["method"] == METHOD_PAT and row.get("secret_ref") == LEGACY_VAULT_KEY),
            None,
        )
        if vault_row is None and self.vault_get(LEGACY_VAULT_KEY):
            self._store.create_git_credential(
                principal_id=self._principal_id, method=METHOD_PAT, status="unverified",
                label=LABELS[METHOD_PAT], secret_ref=LEGACY_VAULT_KEY,
            )
            changed = True
        if METHOD_ENVIRONMENT not in methods and os.environ.get(LEGACY_ENV, "").strip():
            self._store.create_git_credential(
                principal_id=self._principal_id, method=METHOD_ENVIRONMENT, status="unverified",
                label=LABELS[METHOD_ENVIRONMENT], selector=LEGACY_ENV,
            )
            changed = True
        if changed or not any(row.get("selected") for row in rows):
            current = self._store.list_git_credentials(self._principal_id)
            if current and not any(row.get("selected") for row in current):
                preferred = sorted(
                    (row for row in current if self.usable(row)),
                    key=lambda row: (row["method"] != METHOD_PAT, row["created_at"]),
                )
                if preferred:
                    self._store.select_git_credential(self._principal_id, preferred[0]["credential_id"])

    def list(self) -> list[dict[str, Any]]:
        self.ensure_legacy()
        return self._store.list_git_credentials(self._principal_id)

    def selected(self) -> dict[str, Any] | None:
        self.ensure_legacy()
        row = self._store.selected_git_credential(self._principal_id)
        return row if row is not None and self.usable(row) else None

    def get(self, credential_id: str) -> dict[str, Any]:
        row = self._store.load_git_credential(credential_id)
        if row is None or row["principal_id"] != self._principal_id:
            raise CredentialMethodError("git_credential_unknown", "No such credential.")
        return row

    def usable(self, row: dict[str, Any]) -> bool:
        """Whether *row* could be lent now, without running anything or reaching GitHub."""
        if row.get("status") in {"revoked", "removed", "disabled", "expired"}:
            return False
        method = row["method"]
        if method == METHOD_PAT:
            return bool((self.vault_get(str(row.get("secret_ref") or "")) or {}).get("token"))
        if method == METHOD_ENVIRONMENT:
            return bool(os.environ.get(LEGACY_ENV, "").strip())
        if method == METHOD_APP_USER:
            access_key, _refresh = app_user_vault_keys(row["credential_id"])
            return bool((self.vault_get(access_key) or {}).get("access_token"))
        if method == METHOD_SSH:
            return bool(row.get("key_path")) and Path(str(row["key_path"])).is_file()
        if method == METHOD_APP_INSTALLATION:
            installation = self._store.load_github_installation(str(row.get("selector") or ""))
            app = self._store.load_github_app(str(row.get("app_ref") or ""))
            return (
                installation is not None and installation.get("status") == "active"
                and app is not None and bool(app.get("private_key_ref"))
            )
        # gh CLI and credential-manager entries are read at lend time; a row the
        # owner verified is usable until that read says otherwise.
        return row.get("status") == "active"

    def select(self, credential_id: str) -> dict[str, Any]:
        row = self.get(credential_id)
        if not self.usable(row):
            raise CredentialMethodError(
                "git_credential_unavailable", "That credential is not available on this machine."
            )
        previous = self._store.selected_git_credential(self._principal_id)
        self._store.select_git_credential(self._principal_id, credential_id)
        if previous is not None and previous.get("account_id") != row.get("account_id"):
            # Switching account ends every grant made for the old one at once
            # (§6.4): nothing lent for one account may run as another.
            self._store.revoke_git_credential_grants(self._principal_id)
        self._record(
            "git_credential_selected",
            {"credential_id": credential_id, "method": row["method"], "account_id": row.get("account_id")},
        )
        return self.get(credential_id)

    def discover(self) -> dict[str, Any]:
        """What this machine offers, found without reading a secret (§10 Discovery).

        The CLI's signed-in accounts, the credential helpers git is configured
        with (a helper cannot list its usernames without answering for one), and
        SSH keys by fingerprint. A program that is missing or fails offers nothing.
        """
        found: dict[str, Any] = {"gh_accounts": [], "credential_helpers": [], "ssh_keys": []}
        with contextlib.suppress(Exception):
            found["gh_accounts"] = [{"login": a.login, "active": a.active} for a in self._gh.accounts()]
        with contextlib.suppress(Exception):
            found["credential_helpers"] = list(self._helper.helpers())
        with contextlib.suppress(Exception):
            found["ssh_keys"] = [{"path": k.path, "fingerprint": k.fingerprint} for k in self._ssh.discover()]
        return found

    # ── adding methods ──────────────────────────────────────────────────
    def _create_verified(
        self, method: str, account: Account, *, select: bool = True, **fields: Any
    ) -> dict[str, Any]:
        for existing in self._store.list_git_credentials(self._principal_id):
            if (
                existing["method"] == method
                and existing.get("selector") == fields.get("selector")
                and (method != METHOD_SSH or existing.get("key_path") == fields.get("key_path"))
            ):
                self._store.delete_git_credential(existing["credential_id"])
        row = self._store.create_git_credential(
            principal_id=self._principal_id, method=method, status="active",
            label=fields.pop("label", LABELS[method]), account_id=account.account_id,
            account_login=account.login, permissions={"scopes": account.scopes},
            expires_at=account.expires_at, **fields,
        )
        self._record(
            "git_credential_stored",
            {"source": method, "credential_id": row["credential_id"], "account_id": account.account_id},
        )
        if select:
            return self.select(row["credential_id"])
        return row

    def check_token(self, token: str) -> Account:
        try:
            return check_account(token, self._http)
        except AccountCheckError as exc:
            raise CredentialMethodError(exc.reason, "GitHub did not confirm which account this is.") from None

    def add_gh_cli(self, login: str) -> dict[str, Any]:
        """Use the GitHub CLI's sign-in for *login*: read once to learn the account, never stored."""
        try:
            token = self._gh.token(login)
        except LocalCredentialError as exc:
            raise CredentialMethodError(exc.reason) from None
        account = self.check_token(token)
        if account.login.lower() != login.lower():
            raise CredentialMethodError("git_account_mismatch", "gh answered for a different account.")
        return self._create_verified(METHOD_GH_CLI, account, selector=login)

    def add_os_helper(self, username: str) -> dict[str, Any]:
        """Use the credential manager's entry for *username* on github.com."""
        try:
            token = self._helper.token(username)
        except LocalCredentialError as exc:
            raise CredentialMethodError(exc.reason) from None
        account = self.check_token(token)
        if account.login.lower() != username.lower():
            raise CredentialMethodError(
                "git_account_mismatch", "The saved credential belongs to a different account."
            )
        return self._create_verified(METHOD_OS_HELPER, account, selector=username)

    def add_ssh(self, key_path: str) -> dict[str, Any]:
        """Use one SSH key, after github.com says which account it authenticates."""
        path = Path(key_path).expanduser()
        if not path.is_file():
            raise CredentialMethodError("ssh_key_missing", "No key at that path.")
        fingerprint = self._ssh.fingerprint(str(path))
        if not fingerprint:
            raise CredentialMethodError("ssh_key_unreadable", "That is not an SSH key ssh can read.")
        known_hosts = write_known_hosts(self._store.paths.workspace_root)
        try:
            login = self._ssh.account(str(path), known_hosts)
        except LocalCredentialError as exc:
            raise CredentialMethodError(exc.reason) from None
        return self._create_verified(
            METHOD_SSH, Account(account_id=f"ssh:{login.lower()}", login=login),
            selector=fingerprint, key_path=str(path),
        )

    def add_app_installation(self, installation_id: str, app_ref: str = "byo") -> dict[str, Any]:
        """Use the App's own identity on one installation (M-APP-INSTALL).

        For automation the owner delegates: tokens are minted per operation by
        the trusted service and narrowed to the repository it touches.
        """
        installation = self._store.load_github_installation(installation_id)
        if installation is None or installation.get("app_ref") != app_ref:
            raise CredentialMethodError("github_installation_unknown", "That installation is not known here.")
        if installation.get("status") != "active":
            raise CredentialMethodError(
                f"github_installation_{installation.get('status')}", "The Raiker app is not active there."
            )
        account = Account(
            account_id=f"installation:{installation_id}",
            login=str(installation.get("account_login") or installation_id),
        )
        return self._create_verified(
            METHOD_APP_INSTALLATION, account, selector=installation_id, app_ref=app_ref,
            label=f"GitHub App on {account.login}",
        )

    # ── checking and removing ───────────────────────────────────────────
    def check(self, credential_id: str) -> dict[str, Any]:
        """Ask GitHub which account the credential belongs to now, and record the answer."""
        row = self.get(credential_id)
        try:
            if row["method"] == METHOD_SSH:
                login = self._ssh.account(
                    str(row.get("key_path") or ""), write_known_hosts(self._store.paths.workspace_root)
                )
                account = Account(account_id=f"ssh:{login.lower()}", login=login)
            elif row["method"] == METHOD_APP_INSTALLATION:
                account = self._check_installation(row)
            else:
                account = self.check_token(self.secret(row, verify=False))
        except (CredentialMethodError, LocalCredentialError) as exc:
            reason = exc.reason
            status = "revoked" if reason == "github_credential_rejected" else row["status"]
            self._store.update_git_credential(credential_id, status=status, last_error=reason)
            self._record("git_credential_checked", {"credential_id": credential_id, "result": reason})
            raise CredentialMethodError(reason) from None
        if row.get("account_id") and row["account_id"] != account.account_id:
            self._store.update_git_credential(credential_id, last_error="git_account_mismatch")
            raise CredentialMethodError(
                "git_account_mismatch", f"This credential now belongs to @{account.login}."
            )
        self._store.update_git_credential(
            credential_id, status="active", account_id=account.account_id,
            account_login=account.login, validated_at=utc_now(), last_error=None,
            expires_at=account.expires_at or row.get("expires_at"),
            permissions_json={"scopes": account.scopes},
        )
        self._record(
            "git_credential_checked",
            {"credential_id": credential_id, "result": "ok", "account_id": account.account_id},
        )
        return self.get(credential_id)

    def _check_installation(self, row: dict[str, Any]) -> Account:
        """An installation has no user to ask about: ask GitHub whether it is still there."""
        from raiker.github.app_service import AppServiceError, GitHubAppService

        installation_id = str(row.get("selector") or "")
        try:
            GitHubAppService(
                self._store, str(row.get("app_ref") or "byo"), http=self._http
            ).sync_installations(strict=True)
        except AppServiceError as exc:
            raise CredentialMethodError(exc.reason, exc.message) from None
        installation = self._store.load_github_installation(installation_id)
        if installation is None or installation.get("status") != "active":
            status = (installation or {}).get("status") or "removed"
            raise CredentialMethodError(f"github_installation_{status}", "The Raiker app is no longer installed there.")
        return Account(
            account_id=f"installation:{installation_id}",
            login=str(installation.get("account_login") or installation_id),
        )

    def remove(self, credential_id: str) -> dict[str, Any]:
        """Forget one credential: its vault entries, its row, and every grant."""
        row = self.get(credential_id)
        if row["method"] == METHOD_PAT and row.get("secret_ref"):
            self.vault_delete(str(row["secret_ref"]))
        if row["method"] == METHOD_APP_USER:
            for key in app_user_vault_keys(credential_id):
                self.vault_delete(key)
        if row["method"] == METHOD_ENVIRONMENT:
            # The variable is the host's; what Raiker can do is stop using it.
            self._store.update_git_credential(credential_id, status="disabled")
            if row.get("selected"):
                self._store.clear_git_credential_selection(self._principal_id)
        else:
            self._store.delete_git_credential(credential_id)
        revoked = self._store.revoke_git_credential_grants(self._principal_id)
        self._record(
            "git_credential_forgotten",
            {"credential_id": credential_id, "method": row["method"], "grants_revoked": revoked},
        )
        return row

    # ── reading the selected secret ─────────────────────────────────────
    def secret(
        self,
        row: dict[str, Any],
        *,
        verify: bool = True,
        repository: str | None = None,
        operation: str | None = None,
    ) -> str:
        """The token *row* lends, read from wherever it lives.

        For the CLI and the credential manager the token is read now, and — with
        *verify* — GitHub is asked whose it is: a program that switched accounts
        since the owner selected it does not get to lend the other one.
        """
        method = row["method"]
        if method == METHOD_PAT:
            token = (self.vault_get(str(row.get("secret_ref") or "")) or {}).get("token", "")
        elif method == METHOD_ENVIRONMENT:
            token = os.environ.get(LEGACY_ENV, "")
        elif method == METHOD_APP_USER:
            token = self._app_user_token(row)
        elif method == METHOD_APP_INSTALLATION:
            token = self._installation_token(row, repository, operation)
        elif method == METHOD_GH_CLI:
            try:
                token = self._gh.token(str(row.get("selector") or ""))
            except LocalCredentialError as exc:
                raise CredentialMethodError(exc.reason) from None
        elif method == METHOD_OS_HELPER:
            try:
                token = self._helper.token(str(row.get("selector") or ""))
            except LocalCredentialError as exc:
                raise CredentialMethodError(exc.reason) from None
        else:
            raise CredentialMethodError("git_method_has_no_token", "This credential is an SSH key.")
        token = token.strip()
        if not token:
            raise CredentialMethodError(
                "git_token_not_configured", "No GitHub token is stored. Add one in Settings → GitHub."
            )
        if verify and method in REREAD_METHODS:
            self._confirm_account(row, token)
        return token

    def _confirm_account(self, row: dict[str, Any], token: str) -> None:
        expected = str(row.get("account_id") or "")
        if not expected:
            raise CredentialMethodError("git_account_unverified", "Check this credential before using it.")
        key = _fingerprint(token, expected)
        now = time.monotonic()
        if _verified.get(key, 0.0) > now:
            return
        account = self.check_token(token)
        if account.account_id != expected:
            self._store.update_git_credential(row["credential_id"], last_error="git_account_mismatch")
            raise CredentialMethodError(
                "git_account_mismatch",
                f"The {LABELS[row['method']]} now answers for @{account.login}, not @{row.get('account_login')}.",
            )
        _verified[key] = now + _VERIFIED_SECONDS

    def _installation_token(self, row: dict[str, Any], repository: str | None, operation: str | None) -> str:
        """A token minted now for this one repository and operation (P3), never stored."""
        from raiker.github.app_service import AppServiceError, GitHubAppService

        if not repository or not operation:
            raise CredentialMethodError(
                "github_installation_needs_scope", "An installation token is minted for one repository."
            )
        full_name = repository.split("/", 1)[1] if "/" in repository else repository
        repo = self._store.github_repository_by_name(self._principal_id, full_name)
        if repo is None or repo.get("status") != "available" or repo.get("installation_id") != row.get("selector"):
            raise CredentialMethodError(
                "github_repository_not_authorised", "That repository is not one the app was given."
            )
        try:
            token, _expires = GitHubAppService(
                self._store, str(row.get("app_ref") or "byo"), http=self._http
            ).installation_token(
                str(row.get("selector")), repository_ids=[str(repo["repository_id"])], operation=operation
            )
        except AppServiceError as exc:
            raise CredentialMethodError(exc.reason, exc.message) from None
        return token

    def _app_user_token(self, row: dict[str, Any]) -> str:
        access_key, _refresh = app_user_vault_keys(row["credential_id"])
        stored = self.vault_get(access_key) or {}
        expires = str(row.get("expires_at") or "")
        if expires and expires <= utc_now():
            if self._refresher is None:
                raise CredentialMethodError("github_sign_in_expired", "Your GitHub sign-in expired.")
            return self._refresher(row)
        return stored.get("access_token", "")

    def set_refresher(self, refresher: Callable[[dict[str, Any]], str]) -> None:
        self._refresher = refresher

    def ssh_environment(self, row: dict[str, Any]) -> dict[str, str]:
        """``GIT_SSH_COMMAND`` for the selected key, with Raiker's pinned host keys."""
        if row["method"] != METHOD_SSH or not row.get("key_path"):
            raise CredentialMethodError("git_method_not_ssh", "The selected credential is not an SSH key.")
        known_hosts = write_known_hosts(self._store.paths.workspace_root)
        return {"GIT_SSH_COMMAND": ssh_command(str(row["key_path"]), known_hosts)}


def reset_verification_cache() -> None:
    """Forget every cached account answer (tests, and a disconnect)."""
    _verified.clear()
