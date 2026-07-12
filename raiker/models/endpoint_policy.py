from __future__ import annotations

import fnmatch
import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from raiker.models.exceptions import ProviderPolicyError

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
PRIVATE_DNS_SUFFIXES = (".internal", ".lan", ".local", ".home.arpa")

MODEL_EGRESS_ALLOWLIST_ENV = "RAIKER_MODEL_EGRESS_ALLOWLIST"


def model_egress_allowlist() -> frozenset[str]:
    """Owner-controlled host allowlist for off-machine model endpoints.

    Read from ``RAIKER_MODEL_EGRESS_ALLOWLIST`` (comma-separated hostname globs,
    e.g. ``api.openai.com,openrouter.ai,192.168.1.*``). Defaults to **empty**
    so no hosted/private-network model endpoint is reachable until the owner
    explicitly allowlists its host — fail-closed even when the capability gate
    is on. Local-machine endpoints are never subject to this allowlist.
    """
    raw = os.environ.get(MODEL_EGRESS_ALLOWLIST_ENV, "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def enforce_model_egress(endpoint: str, *, kind: str) -> None:
    """Fail closed unless *endpoint*'s hostname is on the model egress allowlist.

    Applies only to off-machine endpoint kinds (``remote_hosted`` /
    ``private_network``); local endpoints pass through untouched. Matching is
    intentionally against ``hostname`` rather than ``netloc`` so an explicitly
    allowlisted host continues to match when the endpoint uses a non-default
    port.
    """
    if kind not in {"remote_hosted", "private_network"}:
        return
    allowlist = model_egress_allowlist()
    if not allowlist:
        raise ProviderPolicyError("model_egress_denied:no_allowlist")
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ProviderPolicyError("model_egress_denied:missing_host")
    if not any(fnmatch.fnmatch(host, pattern) for pattern in allowlist):
        raise ProviderPolicyError(f"model_egress_denied:{host}")


@dataclass(frozen=True)
class EndpointPolicy:
    local_only: bool
    requires_network: bool
    requires_egress_policy: bool = False
    requires_budget_policy: bool = False
    provider: str = ""
    allow_remote_http: bool = False


def classify_endpoint(endpoint: str | None) -> str:
    if not endpoint:
        return "unknown"
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "invalid"
    host = parsed.hostname.strip("[]").lower()
    if host in LOCAL_HOSTS or host.endswith(".localhost"):
        return "local_machine"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Private/home-lab model servers commonly use a single-label mDNS/DNS
        # name or a private suffix. Treat those as private network endpoints;
        # ordinary fully-qualified names remain hosted and still require HTTPS.
        if "." not in host or host.endswith(PRIVATE_DNS_SUFFIXES):
            return "private_network"
        return "remote_hosted"
    if ip.is_loopback or str(ip) == "0.0.0.0":
        return "local_machine"
    if ip.is_private:
        return "private_network"
    return "remote_hosted"


def validate_endpoint_policy(endpoint: str | None, policy: EndpointPolicy) -> str:
    kind = "remote_hosted" if policy.provider.lower() == "openrouter" else classify_endpoint(endpoint)
    if kind in {"invalid", "unknown"}:
        raise ProviderPolicyError(f"endpoint_{kind}")
    if policy.local_only and kind != "local_machine":
        raise ProviderPolicyError(f"local_only_rejects_{kind}")
    if kind == "private_network" and (
        policy.local_only or not policy.requires_network or not policy.requires_egress_policy
    ):
        raise ProviderPolicyError("private_network_requires_network_and_egress_policy")
    if kind == "remote_hosted":
        if policy.local_only or not policy.requires_network or not policy.requires_egress_policy:
            raise ProviderPolicyError("hosted_endpoint_requires_egress_policy")
        if policy.requires_budget_policy is False and policy.provider.lower() == "openrouter":
            raise ProviderPolicyError("openrouter_requires_budget_policy")
        if endpoint and urlparse(endpoint).scheme == "http" and not policy.allow_remote_http:
            raise ProviderPolicyError("hosted_http_endpoint_rejected")
    if policy.provider.lower() == "openrouter" and not (
        policy.requires_egress_policy and policy.requires_budget_policy
    ):
        raise ProviderPolicyError("openrouter_requires_egress_and_budget_policy")
    return kind
