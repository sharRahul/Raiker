"""One way to talk to GitHub over HTTPS, for the control plane and the API.

Every request goes to a fixed GitHub host over HTTPS, follows no redirect, is
bounded in size and time, and comes back as a status, a few response headers
and parsed JSON. Credentials travel only in the request headers and are never
returned, logged or put in a reason code. Tests pass their own ``transport``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from raiker.github.hosts import control_plane_allowed

#: (method, url, headers, body) → (status, response headers, body bytes).
Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, Mapping[str, str], bytes]]

USER_AGENT = "Raiker"
API_VERSION = "2022-11-28"
MAX_BODY = 1_000_000
TIMEOUT = 15.0

#: Response headers a caller may need; everything else is dropped.
KEPT_HEADERS = ("x-oauth-scopes", "x-accepted-github-permissions", "x-github-request-id",
                "retry-after", "x-ratelimit-remaining", "x-ratelimit-reset", "github-authentication-token-expiration")


class GitHubHttpError(Exception):
    """A request that could not be made or did not succeed, with a reason safe to show."""

    def __init__(self, reason: str, status: int = 0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class GitHubResponse:
    status: int
    data: Any
    headers: dict[str, str] = field(default_factory=dict)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is refused, not followed: the next hop's host was never checked."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        return None


def urllib_transport(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None
) -> tuple[int, Mapping[str, str], bytes]:
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))  # noqa: S310 — https checked by the caller
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers.items()), response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read(MAX_BODY + 1) if exc.fp else b""
    except Exception as exc:  # noqa: BLE001 — every transport failure is one named reason
        raise GitHubHttpError(f"github_unreachable:{type(exc).__name__}") from None


class GitHubHttp:
    """Requests to github.com and api.github.com, and nowhere else."""

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport or urllib_transport

    def request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        basic: tuple[str, str] | None = None,
        json_body: Any = None,
        form: Mapping[str, str] | None = None,
        accept: str = "application/vnd.github+json",
        allowed: Callable[[str], bool] = control_plane_allowed,
    ) -> GitHubResponse:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise GitHubHttpError("github_url_invalid")
        if not allowed(parsed.hostname):
            raise GitHubHttpError(f"github_host_not_allowed:{parsed.hostname}")
        headers = {"Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": API_VERSION}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif basic:
            import base64

            pair = f"{basic[0]}:{basic[1]}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(pair).decode("ascii")
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form is not None:
            body = urllib.parse.urlencode(dict(form)).encode("ascii")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        status, raw_headers, raw = self._transport(method, url, headers, body)
        if 300 <= status < 400:
            raise GitHubHttpError("github_redirect_refused", status)
        if len(raw) > MAX_BODY:
            raise GitHubHttpError("github_response_too_large", status)
        kept = {
            name.lower(): str(value)
            for name, value in raw_headers.items()
            if name.lower() in KEPT_HEADERS
        }
        data: Any = None
        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = None
        return GitHubResponse(status=status, data=data, headers=kept)

    def get_json(self, url: str, **kwargs: Any) -> GitHubResponse:
        return self.request("GET", url, **kwargs)

    def post_json(self, url: str, **kwargs: Any) -> GitHubResponse:
        return self.request("POST", url, **kwargs)
