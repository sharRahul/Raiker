"""A stand-in for github.com and api.github.com, for the GitHub connection tests.

It implements just enough of GitHub's documented behaviour — the device flow,
the authorisation-code exchange with PKCE, refresh with rotation, ``/user``,
installations and their repositories, App JWT checks and installation-token
minting — to drive Raiker's code paths. It is not evidence that GitHub itself
behaves this way; live evidence is RR-38…RR-41.
"""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CLIENT_ID = "Iv23liRaikerTest"
CLIENT_SECRET = "client-secret-for-tests"


def _b64decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


@dataclass
class FakeGitHub:
    """Requests in, GitHub-shaped answers out; every request is recorded."""

    users: dict[str, tuple[int, str]] = field(default_factory=dict)
    device_answers: list[dict[str, Any]] = field(default_factory=list)
    code_verifiers: dict[str, str] = field(default_factory=dict)
    refresh_tokens: dict[str, tuple[int, str]] = field(default_factory=dict)
    installations: list[dict[str, Any]] = field(default_factory=list)
    installation_repositories: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    app: dict[str, Any] = field(default_factory=lambda: {
        "id": 4242, "client_id": CLIENT_ID, "slug": "raiker-test",
        "permissions": {"metadata": "read", "contents": "write", "pull_requests": "write"},
    })
    public_key: Any = None
    removed_installations: set[int] = field(default_factory=set)
    user_repositories: list[dict[str, Any]] = field(default_factory=list)
    revoked: list[str] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    _counter: int = 0

    def issue(self, account: tuple[int, str], *, refresh: bool = True) -> dict[str, Any]:
        self._counter += 1
        access = f"ghu_access{self._counter:032d}"
        self.users[access] = account
        answer: dict[str, Any] = {"access_token": access, "token_type": "bearer", "expires_in": 28800}
        if refresh:
            refresh_token = f"ghr_refresh{self._counter:031d}"
            self.refresh_tokens[refresh_token] = account
            answer.update(refresh_token=refresh_token, refresh_token_expires_in=15897600)
        return answer

    def _check_jwt(self, token: str) -> bool:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        try:
            header, payload, signature = token.split(".")
            self.public_key.verify(
                _b64decode(signature), f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()
            )
        except Exception:  # noqa: BLE001 — any failure is a rejected JWT
            return False
        claims = json.loads(_b64decode(payload))
        return claims.get("iss") == CLIENT_ID and claims["exp"] - claims["iat"] <= 600

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, Mapping[str, str], bytes]:
        parsed = urllib.parse.urlsplit(url)
        form = dict(urllib.parse.parse_qsl(body.decode())) if body and headers.get("Content-Type", "").startswith("application/x-www") else {}
        payload = json.loads(body) if body and headers.get("Content-Type") == "application/json" else None
        auth = headers.get("Authorization", "")
        self.requests.append({"method": method, "url": url, "form": form, "json": payload, "auth": auth})

        def answer(status: int, data: Any, extra: Mapping[str, str] | None = None) -> tuple[int, Mapping[str, str], bytes]:
            return status, dict(extra or {}), json.dumps(data).encode()

        host, path = parsed.hostname, parsed.path
        if host == "github.com" and path == "/login/device/code":
            if form.get("client_id") != CLIENT_ID:
                return answer(200, {"error": "incorrect_client_credentials"})
            return answer(200, {
                "device_code": "device-code-secret", "user_code": "WDJB-MJHT",
                "verification_uri": "https://github.com/login/device", "expires_in": 900, "interval": 5,
            })
        if host == "github.com" and path == "/login/oauth/access_token":
            grant = form.get("grant_type", "")
            if grant.endswith("device_code"):
                assert "client_secret" not in form, "the device flow sends no secret"
                return answer(200, self.device_answers.pop(0) if self.device_answers else {"error": "authorization_pending"})
            if grant == "refresh_token":
                account = self.refresh_tokens.pop(form.get("refresh_token", ""), None)
                if account is None:
                    return answer(200, {"error": "bad_refresh_token"})
                return answer(200, self.issue(account))
            code = form.get("code", "")
            if form.get("client_secret") != CLIENT_SECRET:
                return answer(200, {"error": "incorrect_client_credentials"})
            expected = self.code_verifiers.pop(code, None)
            if expected is None:
                return answer(200, {"error": "bad_verification_code"})
            challenge = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).decode().rstrip("=")
            if challenge != expected:
                return answer(200, {"error": "bad_verification_code"})
            return answer(200, self.issue((101, "octo")))
        if host != "api.github.com":
            return answer(404, {})
        bearer = auth.removeprefix("Bearer ")
        if path == "/user":
            if bearer not in self.users:
                return answer(401, {"message": "Bad credentials"})
            account_id, login = self.users[bearer]
            return answer(200, {"id": account_id, "login": login})
        if path == "/user/repos":
            if bearer not in self.users:
                return answer(401, {"message": "Bad credentials"})
            return answer(200, self.user_repositories if "page=1" in parsed.query else [])
        if path == "/user/installations":
            return answer(200, {"installations": self.installations})
        if path.startswith("/user/installations/") and path.endswith("/repositories"):
            installation_id = int(path.split("/")[3])
            return answer(200, {"repositories": self.installation_repositories.get(installation_id, [])})
        if path.startswith("/applications/") and method == "DELETE":
            if auth != "Basic " + base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode():
                return answer(401, {})
            self.revoked.append(str((payload or {}).get("access_token")))
            return 204, {}, b""
        if path == "/app":
            return answer(200, self.app) if self._check_jwt(bearer) else answer(401, {})
        if path == "/app/installations":
            return answer(200, self.installations) if self._check_jwt(bearer) else answer(401, {})
        if path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            if not self._check_jwt(bearer):
                return answer(401, {})
            installation_id = int(path.split("/")[3])
            if installation_id in self.removed_installations:
                return answer(404, {"message": "Not Found"})
            self._counter += 1
            token = f"ghs_install{self._counter:031d}"
            return answer(201, {"token": token, "expires_at": "2099-01-01T00:00:00Z"})
        if path == "/installation/repositories":
            repositories = [repo for repos in self.installation_repositories.values() for repo in repos]
            return answer(200, {"repositories": repositories})
        return answer(404, {})
