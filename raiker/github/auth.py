"""Signing in with a GitHub App, and what follows from it (ADD-27 GH-31…GH-37).

A sign-in is an **attempt** first: who started it, in which Raiker session,
which App, how it will end, and when it stops being valid. Only a completed
attempt creates a credential, and only a credential whose account GitHub
confirmed. Installation of the App, the user's authorisation and the token are
three separate facts; any one can exist without the others.

* **Device flow** — the desktop release and terminal or headless hosts. Needs
  only the App's Client ID: no secret for sign-in or for refresh (P7, P8). The
  device code stays in the vault; the owner sees only the user code.
* **Browser flow** — authorisation code with ``state`` and PKCE S256, where a
  server holds the client secret (a self-hosted App, or the managed service).
  The callback is completed by the Raiker client that started it, so an
  attempt only finishes in the session it began in.

Nothing here grants anything: a connected account is a credential the broker
may lend under a grant, like any other.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.github.apps import AppConfigError, identity, read_secret
from raiker.github.credentials import (
    METHOD_APP_INSTALLATION,
    METHOD_APP_USER,
    METHOD_SSH,
    CredentialMethodError,
    CredentialMethods,
    app_user_vault_keys,
)
from raiker.github.hosts import (
    ACCESS_TOKEN_URL,
    AUTHORIZE_URL,
    DEVICE_CODE_URL,
    GITHUB_API_BASE,
)
from raiker.github.http import GitHubHttp, GitHubHttpError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: How long a browser sign-in may take before it is refused (§6.1).
BROWSER_ATTEMPT_SECONDS = 600
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_MAX_REPOSITORY_PAGES = 10


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class SignInError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


def _iso_in(seconds: int) -> str:
    moment = datetime.now(UTC) + timedelta(seconds=max(0, int(seconds)))
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_pair() -> tuple[str, str]:
    """A verifier and its S256 challenge (RFC 7636)."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _attempt_key(attempt_id: str) -> str:
    return f"github_attempt:{attempt_id}"


class GitHubSignIn:
    """Starts, advances and completes sign-in attempts for one owner."""

    def __init__(
        self,
        store: SQLiteStore,
        principal_id: str,
        *,
        http: GitHubHttp | None = None,
        methods: CredentialMethods | None = None,
    ) -> None:
        self._store = store
        self._principal_id = principal_id
        self._http = http or GitHubHttp()
        self._methods = methods or CredentialMethods(store, principal_id, http=self._http)

    # ── shared ──────────────────────────────────────────────────────────
    def _owned_attempt(self, attempt_id: str, session_ref: str) -> dict[str, Any]:
        attempt = self._store.load_github_auth_attempt(attempt_id)
        if attempt is None or attempt["principal_id"] != self._principal_id:
            raise SignInError("github_sign_in_unknown", "No such sign-in.")
        if attempt["session_ref"] != session_ref:
            # The attempt belongs to the session that started it, and only there.
            raise SignInError("github_sign_in_other_session", "This sign-in was started elsewhere.")
        return attempt

    def _app(self, app_ref: str) -> Any:
        app = identity(self._store, app_ref)
        if app is None:
            raise SignInError(
                "github_app_not_available",
                "Signing in with GitHub is not available in this build yet.",
            )
        return app

    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        try:
            response = self._http.post_json(ACCESS_TOKEN_URL, form=form, accept="application/json")
        except GitHubHttpError as exc:
            raise SignInError(exc.reason, "Couldn't reach GitHub.") from None
        data = response.data if isinstance(response.data, dict) else {}
        if response.status >= 500:
            raise SignInError("github_unavailable", "GitHub did not answer.")
        return data

    def _vault(self) -> Any:
        from raiker.runtime.connector_ecosystem import ConnectorVault

        return ConnectorVault(self._store)

    def _connect(self, attempt: dict[str, Any], tokens: dict[str, Any], flow: str) -> dict[str, Any]:
        """Turn a token response into a verified, selected credential."""
        access = str(tokens.get("access_token") or "")
        if not access:
            raise SignInError("github_token_missing", "GitHub returned no token.")
        try:
            account = self._methods.check_token(access)
        except CredentialMethodError as exc:
            raise SignInError(exc.reason, exc.message) from None
        expires_at = _iso_in(int(tokens["expires_in"])) if tokens.get("expires_in") else None
        refresh_expires_at = (
            _iso_in(int(tokens["refresh_token_expires_in"])) if tokens.get("refresh_token_expires_in") else None
        )
        # One row per account and App: signing in again replaces the old tokens.
        for existing in self._store.list_git_credentials(self._principal_id):
            if (
                existing["method"] == METHOD_APP_USER
                and existing.get("account_id") == account.account_id
                and existing.get("app_ref") == attempt["app_ref"]
            ):
                for key in app_user_vault_keys(existing["credential_id"]):
                    self._methods.vault_delete(key)
                self._store.delete_git_credential(existing["credential_id"])
        row = self._store.create_git_credential(
            principal_id=self._principal_id, method=METHOD_APP_USER, status="active",
            label="GitHub sign-in", account_id=account.account_id, account_login=account.login,
            selector=flow, app_ref=attempt["app_ref"], permissions={"scopes": account.scopes},
            expires_at=expires_at, refresh_expires_at=refresh_expires_at,
        )
        access_key, refresh_key = app_user_vault_keys(row["credential_id"])
        self._methods.vault_put(access_key, {"access_token": access}, expires_at)
        if tokens.get("refresh_token"):
            self._methods.vault_put(refresh_key, {"refresh_token": str(tokens["refresh_token"])}, refresh_expires_at)
        self._methods.select(row["credential_id"])
        self._store.close_github_auth_attempt(
            attempt["attempt_id"], "connected", credential_id=row["credential_id"]
        )
        self._methods.vault_delete(_attempt_key(attempt["attempt_id"]))
        return self._store.load_git_credential(row["credential_id"]) or row

    # ── device flow ─────────────────────────────────────────────────────
    def start_device(self, session_ref: str, app_ref: str = "official") -> dict[str, Any]:
        app = self._app(app_ref)
        try:
            response = self._http.post_json(
                DEVICE_CODE_URL, form={"client_id": app.client_id}, accept="application/json"
            )
        except GitHubHttpError as exc:
            raise SignInError(exc.reason, "Couldn't reach GitHub.") from None
        data = response.data if isinstance(response.data, dict) else {}
        if response.status != 200 or not data.get("device_code"):
            reason = str(data.get("error") or f"github_device_code_failed:{response.status}")
            raise SignInError(reason, "GitHub did not start a device sign-in.")
        attempt = self._store.create_github_auth_attempt(
            principal_id=self._principal_id, session_ref=session_ref, method="device",
            app_ref=app_ref, expires_at=_iso_in(int(data.get("expires_in") or 900)),
            user_code=str(data.get("user_code") or ""),
            verification_uri=str(data.get("verification_uri") or ""),
            poll_interval=int(data.get("interval") or 5),
        )
        self._methods.vault_put(_attempt_key(attempt["attempt_id"]), {"device_code": str(data["device_code"])})
        # The first poll waits a full interval too: GitHub counts one sooner as
        # polling too fast (P8).
        interval = int(data.get("interval") or 5)
        self._store.set_github_auth_poll(attempt["attempt_id"], interval=interval, next_poll_at=_iso_in(interval))
        return self._store.load_github_auth_attempt(attempt["attempt_id"]) or attempt

    def poll_device(self, attempt_id: str, session_ref: str) -> dict[str, Any]:
        """Advance a device sign-in at most once per GitHub's interval."""
        attempt = self._owned_attempt(attempt_id, session_ref)
        if attempt["outcome"] != "pending" or attempt["method"] != "device":
            return attempt
        now = utc_now()
        if now >= str(attempt["expires_at"]):
            self._store.close_github_auth_attempt(attempt_id, "expired", "expired_token")
            self._methods.vault_delete(_attempt_key(attempt_id))
            return self._store.load_github_auth_attempt(attempt_id) or attempt
        if attempt.get("next_poll_at") and now < str(attempt["next_poll_at"]):
            return attempt
        stored = self._methods.vault_get(_attempt_key(attempt_id)) or {}
        if not stored.get("device_code"):
            self._store.close_github_auth_attempt(attempt_id, "failed", "device_code_missing")
            return self._store.load_github_auth_attempt(attempt_id) or attempt
        app = self._app(str(attempt["app_ref"]))
        if not self._store.claim_github_auth_attempt(attempt_id):
            return self._store.load_github_auth_attempt(attempt_id) or attempt
        try:
            data = self._token_request({
                "client_id": app.client_id, "device_code": stored["device_code"],
                "grant_type": DEVICE_GRANT_TYPE,
            })
        except SignInError:
            self._store.release_github_auth_attempt(attempt_id)
            raise
        error = str(data.get("error") or "")
        interval = int(attempt.get("poll_interval") or 5)
        if error in ("authorization_pending", "slow_down"):
            if error == "slow_down":
                interval += 5
            self._store.release_github_auth_attempt(attempt_id)
            self._store.set_github_auth_poll(attempt_id, interval=interval, next_poll_at=_iso_in(interval))
            return self._store.load_github_auth_attempt(attempt_id) or attempt
        if error:
            outcome = {"access_denied": "denied", "expired_token": "expired", "token_expired": "expired"}.get(error, "failed")
            self._store.close_github_auth_attempt(attempt_id, outcome, error)
            self._methods.vault_delete(_attempt_key(attempt_id))
            return self._store.load_github_auth_attempt(attempt_id) or attempt
        try:
            self._connect(attempt, data, "device")
        except SignInError as exc:
            self._store.close_github_auth_attempt(attempt_id, "failed", exc.reason)
            self._methods.vault_delete(_attempt_key(attempt_id))
            raise
        return self._store.load_github_auth_attempt(attempt_id) or attempt

    # ── browser flow ────────────────────────────────────────────────────
    def start_browser(self, session_ref: str, app_ref: str = "byo") -> tuple[dict[str, Any], str]:
        """An attempt and the URL to open. Needs an App whose client secret this host holds."""
        app = self._app(app_ref)
        if not app.has_client_secret or not app.callback_url:
            raise SignInError(
                "github_browser_sign_in_unavailable",
                "Browser sign-in needs a GitHub App whose client secret and callback this host holds.",
            )
        state = secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        attempt = self._store.create_github_auth_attempt(
            principal_id=self._principal_id, session_ref=session_ref, method="browser",
            app_ref=app_ref, expires_at=_iso_in(BROWSER_ATTEMPT_SECONDS),
            state_hash=_hash(state), redirect_uri=app.callback_url,
        )
        self._methods.vault_put(_attempt_key(attempt["attempt_id"]), {"verifier": verifier})
        query = urllib.parse.urlencode({
            "client_id": app.client_id,
            "redirect_uri": app.callback_url,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return attempt, f"{AUTHORIZE_URL}?{query}"

    def complete_browser(
        self, session_ref: str, *, state: str, code: str | None, error: str | None = None
    ) -> dict[str, Any]:
        """Finish a browser sign-in from the client that started it."""
        attempt = self._store.find_github_auth_attempt_by_state(_hash(state or ""))
        if attempt is None or attempt["principal_id"] != self._principal_id or attempt["method"] != "browser":
            raise SignInError("github_sign_in_state_invalid", "This sign-in link is not one Raiker started.")
        if attempt["session_ref"] != session_ref:
            raise SignInError("github_sign_in_other_session", "This sign-in was started elsewhere.")
        if attempt["outcome"] != "pending":
            raise SignInError("github_sign_in_already_used", "This sign-in link was already used.")
        if utc_now() >= str(attempt["expires_at"]):
            self._store.close_github_auth_attempt(attempt["attempt_id"], "expired", "attempt_expired")
            self._methods.vault_delete(_attempt_key(attempt["attempt_id"]))
            raise SignInError("github_sign_in_expired", "That sign-in took too long. Start again.")
        if error:
            outcome = "denied" if error == "access_denied" else "failed"
            self._store.close_github_auth_attempt(attempt["attempt_id"], outcome, error[:80])
            self._methods.vault_delete(_attempt_key(attempt["attempt_id"]))
            return self._store.load_github_auth_attempt(attempt["attempt_id"]) or attempt
        if not code:
            raise SignInError("github_sign_in_code_missing", "GitHub returned no code.")
        if not self._store.claim_github_auth_attempt(attempt["attempt_id"]):
            raise SignInError("github_sign_in_already_used", "This sign-in link was already used.")
        stored = self._methods.vault_get(_attempt_key(attempt["attempt_id"])) or {}
        app = self._app(str(attempt["app_ref"]))
        try:
            secret = read_secret(self._store, (self._store.load_github_app(app.app_ref) or {}).get("client_secret_ref"))
        except AppConfigError as exc:
            self._store.close_github_auth_attempt(attempt["attempt_id"], "failed", exc.reason)
            raise SignInError(exc.reason, exc.message) from None
        data = self._token_request({
            "client_id": app.client_id, "client_secret": secret, "code": code,
            "redirect_uri": str(attempt["redirect_uri"] or ""),
            "code_verifier": stored.get("verifier", ""),
        })
        if data.get("error"):
            reason = str(data["error"])
            self._store.close_github_auth_attempt(attempt["attempt_id"], "failed", reason)
            self._methods.vault_delete(_attempt_key(attempt["attempt_id"]))
            raise SignInError(reason, "GitHub refused the sign-in.")
        try:
            self._connect(attempt, data, "browser")
        except SignInError as exc:
            self._store.close_github_auth_attempt(attempt["attempt_id"], "failed", exc.reason)
            raise
        return self._store.load_github_auth_attempt(attempt["attempt_id"]) or attempt

    def cancel(self, attempt_id: str, session_ref: str) -> dict[str, Any]:
        attempt = self._owned_attempt(attempt_id, session_ref)
        if attempt["outcome"] == "pending":
            self._store.close_github_auth_attempt(attempt_id, "cancelled", "cancelled_by_owner")
            self._methods.vault_delete(_attempt_key(attempt_id))
        return self._store.load_github_auth_attempt(attempt_id) or attempt

    # ── refresh ─────────────────────────────────────────────────────────
    def refresh(self, row: dict[str, Any]) -> str:
        """A new access token for an expired App sign-in, or *Sign in again*.

        A device-flow sign-in refreshes with the Client ID alone; a browser one
        needs the client secret, so it refreshes only where that is held. Both
        tokens are replaced together: GitHub retires the old pair on use.
        """
        credential_id = str(row["credential_id"])
        access_key, refresh_key = app_user_vault_keys(credential_id)
        stored = self._methods.vault_get(refresh_key) or {}
        refresh_token = stored.get("refresh_token", "")
        app = identity(self._store, str(row.get("app_ref") or "official"))
        if not refresh_token or app is None:
            self._store.update_git_credential(credential_id, status="expired", last_error="github_sign_in_expired")
            raise CredentialMethodError("github_sign_in_expired", "Your GitHub sign-in expired. Sign in again.")
        form = {"client_id": app.client_id, "grant_type": "refresh_token", "refresh_token": refresh_token}
        if row.get("selector") == "browser":
            try:
                form["client_secret"] = read_secret(
                    self._store, (self._store.load_github_app(app.app_ref) or {}).get("client_secret_ref")
                )
            except AppConfigError:
                self._store.update_git_credential(credential_id, status="expired", last_error="github_refresh_needs_secret")
                raise CredentialMethodError("github_sign_in_expired", "Your GitHub sign-in expired. Sign in again.") from None
        try:
            data = self._token_request(form)
        except SignInError as exc:
            raise CredentialMethodError(exc.reason, exc.message) from None
        if data.get("error") or not data.get("access_token"):
            self._store.update_git_credential(
                credential_id, status="expired", last_error=str(data.get("error") or "refresh_failed")
            )
            raise CredentialMethodError("github_sign_in_expired", "Your GitHub sign-in expired. Sign in again.")
        expires_at = _iso_in(int(data["expires_in"])) if data.get("expires_in") else None
        refresh_expires_at = (
            _iso_in(int(data["refresh_token_expires_in"])) if data.get("refresh_token_expires_in") else row.get("refresh_expires_at")
        )
        self._methods.vault_put(access_key, {"access_token": str(data["access_token"])}, expires_at)
        if data.get("refresh_token"):
            self._methods.vault_put(refresh_key, {"refresh_token": str(data["refresh_token"])}, refresh_expires_at)
        self._store.update_git_credential(
            credential_id, expires_at=expires_at, refresh_expires_at=refresh_expires_at,
            status="active", last_error=None,
        )
        return str(data["access_token"])

    # ── disconnect ──────────────────────────────────────────────────────
    def disconnect(self, credential_id: str) -> dict[str, Any]:
        """End Raiker's use of a credential at once, and say what GitHub confirmed.

        Local: grants withdrawn, secrets deleted, the row gone, journalled so a
        restore cannot bring it back. At GitHub: an App sign-in's token is
        revoked where this host holds the App's client secret; otherwise the
        answer is *could not confirm*, never a claim that it was revoked.
        """
        from raiker.storage.deletion_journal import GIT_CREDENTIAL_FORGET, record_deletion

        row = self._methods.get(credential_id)
        github_outcome = "not_applicable"
        if row["method"] == METHOD_APP_USER:
            github_outcome = self._revoke_at_github(row)
        elif row["method"] != METHOD_SSH:
            github_outcome = "not_supported"
        self._methods.remove(credential_id)
        record_deletion(self._store.paths.workspace_root, GIT_CREDENTIAL_FORGET, credential_id, self._principal_id)
        return {"credential_id": credential_id, "method": row["method"], "github": github_outcome}

    def _revoke_at_github(self, row: dict[str, Any]) -> str:
        app = identity(self._store, str(row.get("app_ref") or "official"))
        if app is None or not app.has_client_secret:
            return "could_not_confirm"
        access_key, _refresh_key = app_user_vault_keys(str(row["credential_id"]))
        token = (self._methods.vault_get(access_key) or {}).get("access_token", "")
        if not token:
            return "could_not_confirm"
        try:
            secret = read_secret(self._store, (self._store.load_github_app(app.app_ref) or {}).get("client_secret_ref"))
            response = self._http.request(
                "DELETE", f"{GITHUB_API_BASE}/applications/{app.client_id}/token",
                basic=(app.client_id, secret), json_body={"access_token": token},
            )
        except (AppConfigError, GitHubHttpError):
            return "could_not_confirm"
        return "revoked" if response.status in (204, 404) else "could_not_confirm"


# ── repositories ────────────────────────────────────────────────────────


def _repository_entry(repo: dict[str, Any], installation_id: str | None) -> dict[str, Any] | None:
    if not isinstance(repo, dict) or "id" not in repo or not repo.get("full_name"):
        return None
    return {
        "repository_id": str(repo["id"]),
        "full_name": str(repo["full_name"]),
        "private": bool(repo.get("private")),
        "permissions": _as_dict(repo.get("permissions")),
        "installation_id": installation_id,
    }


def discover_repositories(
    store: SQLiteStore, principal_id: str, credential_id: str, *, http: GitHubHttp | None = None,
    methods: CredentialMethods | None = None,
) -> dict[str, Any]:
    """Which repositories, by immutable id, the credential reaches — asked of GitHub now.

    An App sign-in reaches only repositories the App is installed on that the
    user can also reach (P11), so it lists them installation by installation. A
    token lists the repositories its owner can reach. A repository that is no
    longer reachable keeps its row, marked ``removed``.
    """
    client = http or GitHubHttp()
    helper = methods or CredentialMethods(store, principal_id, http=client)
    row = helper.get(credential_id)
    if row["method"] == METHOD_SSH:
        raise SignInError("github_repositories_need_api", "An SSH key cannot list repositories.")
    found: list[dict[str, Any]] = []
    token = ""

    def pages(url: str, key: str | None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, _MAX_REPOSITORY_PAGES + 1):
            separator = "&" if "?" in url else "?"
            try:
                response = client.get_json(f"{url}{separator}per_page=100&page={page}", token=token)
            except GitHubHttpError as exc:
                raise SignInError(exc.reason, "Couldn't reach GitHub.") from None
            if response.status == 401:
                store.update_git_credential(credential_id, status="revoked", last_error="github_credential_rejected")
                raise SignInError("github_credential_rejected", "GitHub no longer accepts this credential.")
            if response.status != 200:
                raise SignInError(f"github_repositories_failed:{response.status}", "GitHub did not list repositories.")
            batch = response.data.get(key, []) if key and isinstance(response.data, dict) else response.data
            if not isinstance(batch, list) or not batch:
                break
            items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                break
        return items

    if row["method"] == METHOD_APP_INSTALLATION:
        from raiker.github.app_service import AppServiceError, GitHubAppService

        installation_id = str(row.get("selector") or "")
        try:
            listed = GitHubAppService(
                store, str(row.get("app_ref") or "byo"), http=client
            ).installation_repositories(installation_id)  # type: ignore[attr-defined]
        except AppServiceError as exc:
            raise SignInError(exc.reason, exc.message) from None
        for repo in listed:
            entry = _repository_entry(repo, installation_id)
            if entry:
                found.append(entry)
        counts = store.replace_github_repositories(principal_id, credential_id, found)
        return {"credential_id": credential_id, **counts}
    try:
        token = helper.secret(row, verify=True)
    except CredentialMethodError as exc:
        raise SignInError(exc.reason, exc.message) from None
    if row["method"] == METHOD_APP_USER:
        for installation in pages(f"{GITHUB_API_BASE}/user/installations", "installations"):
            installation_id = str(installation.get("id", ""))
            if not installation_id:
                continue
            account = _as_dict(installation.get("account"))
            store.upsert_github_installation(
                installation_id, app_ref=str(row.get("app_ref") or "official"), status="active",
                principal_id=principal_id, account_id=str(account.get("id") or ""),
                account_login=str(account.get("login") or ""), account_type=str(account.get("type") or ""),
                repository_selection=str(installation.get("repository_selection") or ""),
                permissions=_as_dict(installation.get("permissions")),
            )
            for repo in pages(
                f"{GITHUB_API_BASE}/user/installations/{installation_id}/repositories", "repositories"
            ):
                entry = _repository_entry(repo, installation_id)
                if entry:
                    found.append(entry)
    else:
        for repo in pages(f"{GITHUB_API_BASE}/user/repos?affiliation=owner,collaborator,organization_member", None):
            entry = _repository_entry(repo, None)
            if entry:
                found.append(entry)
    counts = store.replace_github_repositories(principal_id, credential_id, found)
    return {"credential_id": credential_id, **counts}
