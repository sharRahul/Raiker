"""The trusted side of a GitHub App: its private key, its JWT, its installation tokens.

ADD-27 GH-40…GH-42. Everything here runs in the Raiker host process, never in an
agent's sandbox, and nothing it holds reaches a model, a transcript or a client:

* The **private key** is read from its reference when a JWT is signed and
  dropped again. It is never written anywhere by this module.
* A **JWT** is RS256, ``iat`` 60 seconds back for clock drift, ``exp`` nine
  minutes ahead (GitHub allows ten), ``iss`` the Client ID (P2).
* An **installation token** is minted for one operation, narrowed to the
  repository ids and permissions that operation needs (P3), kept in memory only
  until shortly before GitHub's hour is up, and never stored.

Validation answers whether an operator's App is usable as configured: the key
signs, GitHub knows the App, the Client ID matches, its permissions are no wider
than Raiker needs, and each installation answers.
"""

from __future__ import annotations

import base64
import contextlib
import json
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.github.apps import AppConfigError, read_secret
from raiker.github.hosts import GITHUB_API_BASE
from raiker.github.http import GitHubHttp, GitHubHttpError

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The most an App needs for what Raiker does (spec §8.1). Anything beyond it is
#: reported as excess when an operator's App is validated.
PERMISSION_CEILING: dict[str, str] = {
    "metadata": "read",
    "contents": "write",
    "pull_requests": "write",
    "issues": "write",
    "checks": "read",
    "actions": "read",
}
#: What each operation's installation token is narrowed to.
OPERATION_PERMISSIONS: dict[str, dict[str, str]] = {
    "fetch": {"contents": "read", "metadata": "read"},
    "push": {"contents": "write", "metadata": "read"},
    "pull_request": {"pull_requests": "write", "contents": "read", "metadata": "read"},
    "read_issue": {"issues": "read", "metadata": "read"},
    "read_pull_request": {"pull_requests": "read", "metadata": "read"},
    "issue_comment": {"issues": "write", "metadata": "read"},
    # TOOL-20/22 — CI status and workflow runs, read-only.
    "read_checks": {"checks": "read", "actions": "read", "metadata": "read"},
}
_LEVEL = {"read": 1, "write": 2, "admin": 3}

_cache: dict[tuple[str, str, tuple[str, ...], tuple[tuple[str, str], ...]], tuple[float, str, str]] = {}
_cache_lock = threading.Lock()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class AppServiceError(Exception):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message or reason


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sign_jwt(private_key_pem: str, issuer: str, *, now: float | None = None) -> str:
    """An App JWT, signed RS256 with *private_key_pem*."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    try:
        key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    except (ValueError, TypeError):
        raise AppServiceError("github_app_private_key_invalid", "That is not an App private key.") from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise AppServiceError("github_app_private_key_invalid", "A GitHub App key is an RSA key.")
    moment = int(now if now is not None else time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(
        json.dumps({"iat": moment - 60, "exp": moment + 540, "iss": issuer}, separators=(",", ":")).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


class GitHubAppService:
    """JWTs, validation and installation tokens for one configured App."""

    def __init__(self, store: SQLiteStore, app_ref: str = "byo", *, http: GitHubHttp | None = None) -> None:
        self._store = store
        self._app_ref = app_ref
        self._http = http or GitHubHttp()

    def _config(self) -> dict[str, Any]:
        row = self._store.load_github_app(self._app_ref)
        if row is None or not row.get("client_id") or not row.get("private_key_ref"):
            raise AppServiceError(
                "github_app_not_configured",
                "This GitHub App has no private key configured on this host.",
            )
        return row

    def _jwt(self, config: dict[str, Any]) -> str:
        try:
            key = read_secret(self._store, config.get("private_key_ref"))
        except AppConfigError as exc:
            raise AppServiceError(exc.reason, exc.message) from None
        return sign_jwt(key, str(config.get("client_id") or config.get("app_id")))

    def _app_request(self, method: str, path: str, *, json_body: Any = None) -> Any:
        config = self._config()
        try:
            response = self._http.request(
                method, f"{GITHUB_API_BASE}{path}", token=self._jwt(config), json_body=json_body
            )
        except GitHubHttpError as exc:
            raise AppServiceError(exc.reason, "Couldn't reach GitHub.") from None
        return response

    # ── validation (GH-41) ──────────────────────────────────────────────
    def validate(self) -> dict[str, Any]:
        """Check the App as configured; record and return what was found."""
        checks: list[dict[str, str]] = []
        warnings: list[str] = []
        try:
            config = self._config()
        except AppServiceError as exc:
            return self._save({"ok": False, "checks": [{"check": "configured", "result": exc.reason}]})
        try:
            response = self._app_request("GET", "/app")
        except AppServiceError as exc:
            checks.append({"check": "private_key", "result": exc.reason})
            return self._save({"ok": False, "checks": checks})
        if response.status == 401:
            checks.append({"check": "private_key", "result": "github_app_jwt_rejected"})
            return self._save({"ok": False, "checks": checks})
        data = response.data if isinstance(response.data, dict) else {}
        checks.append({"check": "private_key", "result": "ok"})
        if str(data.get("client_id") or "") != str(config.get("client_id") or ""):
            checks.append({"check": "client_id", "result": "github_app_client_id_mismatch"})
        else:
            checks.append({"check": "client_id", "result": "ok"})
        if config.get("app_id") and str(data.get("id") or "") != str(config["app_id"]):
            checks.append({"check": "app_id", "result": "github_app_id_mismatch"})
        granted = _as_dict(data.get("permissions"))
        for name, level in sorted(granted.items()):
            ceiling = PERMISSION_CEILING.get(str(name))
            if ceiling is None or _LEVEL.get(str(level), 0) > _LEVEL.get(ceiling, 0):
                warnings.append(f"{name}:{level}")
        if warnings:
            checks.append({"check": "permissions", "result": "wider_than_needed"})
        else:
            checks.append({"check": "permissions", "result": "ok"})
        if config.get("webhooks_enabled") and not config.get("webhook_secret_ref"):
            checks.append({"check": "webhook_secret", "result": "github_webhook_secret_missing"})
        installations = self.sync_installations()
        checks.append({"check": "installations", "result": f"{len(installations)} found"})
        # Excess permissions are a warning; every other check has to pass.
        ok = all(
            item["result"] == "ok"
            for item in checks
            if item["check"] not in ("permissions", "installations")
        )
        return self._save({
            "ok": ok, "checks": checks, "excess_permissions": warnings,
            "app_slug": data.get("slug"), "app_name": data.get("name"),
        })

    def _save(self, result: dict[str, Any]) -> dict[str, Any]:
        result["validated_at"] = utc_now()
        self._store.upsert_github_app(
            self._app_ref, updated_by=None, validated_at=result["validated_at"],
            validation_json=result,
            **({"slug": result["app_slug"]} if result.get("app_slug") else {}),
        )
        return result

    # ── installations (GH-42) ───────────────────────────────────────────
    def installation_repositories(self, installation_id: str) -> list[dict[str, Any]]:
        return _installation_repositories(self, installation_id)

    def sync_installations(self, *, strict: bool = False) -> list[dict[str, Any]]:
        """What GitHub says this App is installed on now.

        An installation GitHub no longer lists is marked removed. With *strict*
        a GitHub that cannot be asked is an error rather than an empty answer.
        """
        try:
            response = self._app_request("GET", "/app/installations?per_page=100")
        except AppServiceError:
            if strict:
                raise
            return []
        if response.status != 200 or not isinstance(response.data, list):
            if strict:
                raise AppServiceError(f"github_installations_failed:{response.status}", "GitHub did not answer.")
            return []
        seen: list[dict[str, Any]] = []
        for item in response.data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            account = _as_dict(item.get("account"))
            status = "suspended" if item.get("suspended_at") else "active"
            self._store.upsert_github_installation(
                str(item["id"]), app_ref=self._app_ref, status=status,
                account_id=str(account.get("id") or ""), account_login=str(account.get("login") or ""),
                account_type=str(account.get("type") or ""),
                repository_selection=str(item.get("repository_selection") or ""),
                permissions=_as_dict(item.get("permissions")),
            )
            seen.append(item)
        listed = {str(item["id"]) for item in seen}
        for known in self._store.list_github_installations():
            if known.get("app_ref") == self._app_ref and str(known["installation_id"]) not in listed:
                self._store.upsert_github_installation(
                    str(known["installation_id"]), app_ref=self._app_ref, status="removed"
                )
        return seen

    # ── installation tokens (GH-40) ─────────────────────────────────────
    def installation_token(
        self, installation_id: str, *, repository_ids: list[str], operation: str
    ) -> tuple[str, str]:
        """A token for one installation, narrowed to *repository_ids* and *operation*.

        Cached in memory, never stored, until five minutes before it expires.
        """
        permissions = OPERATION_PERMISSIONS.get(operation)
        if permissions is None:
            raise AppServiceError("github_operation_unknown", f"No installation scope for {operation}.")
        if not repository_ids:
            raise AppServiceError("github_repository_required", "An installation token names its repository.")
        installation = self._store.load_github_installation(installation_id)
        if installation is not None and installation.get("status") != "active":
            raise AppServiceError(
                f"github_installation_{installation.get('status')}",
                "The Raiker app is not active on this account.",
            )
        key = (
            self._app_ref, installation_id, tuple(sorted(repository_ids)),
            tuple(sorted(permissions.items())),
        )
        now = time.time()
        with _cache_lock:
            cached = _cache.get(key)
            if cached and cached[0] - 300 > now:
                return cached[1], cached[2]
        try:
            ids = [int(value) for value in repository_ids]
        except ValueError:
            raise AppServiceError("github_repository_id_invalid") from None
        response = self._app_request(
            "POST", f"/app/installations/{installation_id}/access_tokens",
            json_body={"repository_ids": ids, "permissions": permissions},
        )
        data = response.data if isinstance(response.data, dict) else {}
        if response.status == 404:
            self._store.upsert_github_installation(installation_id, app_ref=self._app_ref, status="removed")
            raise AppServiceError("github_installation_removed", "The Raiker app was removed from this account.")
        if response.status == 403:
            raise AppServiceError("github_installation_forbidden", "GitHub refused a token for that scope.")
        if response.status == 422:
            raise AppServiceError(
                "github_repository_not_in_installation", "That repository is not one the app is installed on."
            )
        token, expires_at = str(data.get("token") or ""), str(data.get("expires_at") or "")
        if response.status != 201 or not token:
            raise AppServiceError(f"github_installation_token_failed:{response.status}")
        expiry = now + 3600
        if expires_at:
            with contextlib.suppress(ValueError):
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).astimezone(UTC).timestamp()
        with _cache_lock:
            _cache[key] = (expiry, token, expires_at)
        return token, expires_at


def _installation_repositories(service: GitHubAppService, installation_id: str) -> list[dict[str, Any]]:
    """Every repository one installation covers, read with a metadata-only token."""
    response = service._app_request(  # noqa: SLF001 — the service's own signed request
        "POST", f"/app/installations/{installation_id}/access_tokens",
        json_body={"permissions": {"metadata": "read"}},
    )
    data = response.data if isinstance(response.data, dict) else {}
    token = str(data.get("token") or "")
    if response.status != 201 or not token:
        raise AppServiceError(f"github_installation_token_failed:{response.status}")
    found: list[dict[str, Any]] = []
    for page in range(1, 11):
        try:
            listing = service._http.get_json(  # noqa: SLF001
                f"{GITHUB_API_BASE}/installation/repositories?per_page=100&page={page}", token=token
            )
        except GitHubHttpError as exc:
            raise AppServiceError(exc.reason) from None
        batch = listing.data.get("repositories", []) if isinstance(listing.data, dict) else []
        found.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            break
    return found



def forget_installation_tokens() -> None:
    with _cache_lock:
        _cache.clear()
