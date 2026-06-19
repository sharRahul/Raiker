from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

from raiker.models.exceptions import ProviderPolicyError

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


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
    if host in LOCAL_HOSTS:
        return "local_machine"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
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
