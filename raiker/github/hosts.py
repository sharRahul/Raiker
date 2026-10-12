"""Which GitHub hosts each kind of traffic may reach (ADD-27 GH-25).

Three kinds of traffic, kept apart so allowing one never allows another:

* **Git transport** — clone, fetch and push to ``github.com`` (HTTPS) or
  ``github.com`` / ``ssh.github.com`` (SSH). The agent starts it, so it answers
  to the owner's connector egress allowlist, matched exactly.
* **API** — ``api.github.com``, for the connector's reads and writes. The agent
  starts it too, so it answers to the same allowlist, matched as the
  connector always has (a host glob).
* **Control plane** — signing in, checking which account a credential belongs
  to, listing repositories, refreshing and revoking tokens. The owner starts
  it, by pressing a button on the GitHub connection page, and it goes only to
  the fixed endpoints below; it is not agent egress and does not need the
  allowlist. It never carries repository content.
"""

from __future__ import annotations

import fnmatch

#: GitHub.com only (DEC-21b): enterprise and other forges are separate adapters.
GITHUB_WEB_HOST = "github.com"
GITHUB_API_HOST = "api.github.com"
GITHUB_API_BASE = f"https://{GITHUB_API_HOST}"
GITHUB_WEB_BASE = f"https://{GITHUB_WEB_HOST}"

#: Hosts git may be given the credential for over HTTPS.
HTTPS_TRANSPORT_HOSTS: tuple[str, ...] = ("github.com", "www.github.com")
#: Hosts git may reach over SSH, and the port each answers on.
SSH_TRANSPORT_HOSTS: dict[str, int] = {"github.com": 22, "ssh.github.com": 443}

#: The fixed sign-in endpoints. Never read from configuration a model or a
#: repository can influence.
AUTHORIZE_URL = f"{GITHUB_WEB_BASE}/login/oauth/authorize"
ACCESS_TOKEN_URL = f"{GITHUB_WEB_BASE}/login/oauth/access_token"
DEVICE_CODE_URL = f"{GITHUB_WEB_BASE}/login/device/code"
DEVICE_VERIFICATION_URL = f"{GITHUB_WEB_BASE}/login/device"

#: Every host a control-plane request may go to.
CONTROL_PLANE_HOSTS: frozenset[str] = frozenset({GITHUB_WEB_HOST, GITHUB_API_HOST})


def transport_allowed(host: str, allowlist: frozenset[str]) -> bool:
    """Git transport: an exact allowlist entry for a host the credential belongs to."""
    name = (host or "").lower()
    return (name in HTTPS_TRANSPORT_HOSTS or name in SSH_TRANSPORT_HOSTS) and name in allowlist


def api_allowed(host: str, allowlist: frozenset[str]) -> bool:
    """The API: ``api.github.com`` and nothing else, matched as the connector does."""
    name = (host or "").lower()
    return name == GITHUB_API_HOST and any(fnmatch.fnmatch(name, pattern) for pattern in allowlist)


def control_plane_allowed(host: str) -> bool:
    return (host or "").lower() in CONTROL_PLANE_HOSTS
