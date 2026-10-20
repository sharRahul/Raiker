from __future__ import annotations

import ipaddress
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse, urlsplit

from raiker.models.exceptions import ProviderPolicyError

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
PRIVATE_DNS_SUFFIXES = (".internal", ".lan", ".local", ".home.arpa")

# Retired. Off-machine model destinations used to need their host on this
# process-wide list as well as a saved connection; the connection alone now
# authorizes its own origin (see ``authorize_model_destination``). The name is
# kept only so an installation that still sets it is told, once, that it no
# longer does anything.
_LEGACY_ALLOWLIST_ENV = "RAIKER_MODEL_EGRESS_ALLOWLIST"
_legacy_notice_given = False

_log = logging.getLogger(__name__)

OFF_MACHINE_KINDS = frozenset({"remote_hosted", "private_network"})

_DEFAULT_PORTS = {"http": 80, "https": 443}
_NUMERIC_LABEL = re.compile(r"^(?:0x[0-9a-f]*|[0-9]+)$")


def note_legacy_model_egress_allowlist() -> None:
    """Say once per process that the retired allowlist is ignored.

    Only whether it is set is reported, never its value: the hosts an owner
    once listed are their business, and the log is not the place for them.
    """
    global _legacy_notice_given
    if _legacy_notice_given or not os.environ.get(_LEGACY_ALLOWLIST_ENV, "").strip():
        return
    _legacy_notice_given = True
    _log.warning(
        "%s is set but no longer used: a saved model connection authorizes its own "
        "endpoint. Remove the variable; see docs/guide/connecting-a-model.md.",
        _LEGACY_ALLOWLIST_ENV,
    )


def canonical_origin(endpoint: str) -> str:
    """``scheme://host:port`` for *endpoint*, or a refusal when it is not one origin.

    The unit a model destination is authorized at. The path is deliberately
    not part of it: a provider adapter reaches several routes under one base
    URL, and those routes are the adapter's, not the request's.

    Normalised so that equal origins compare equal — host case, a trailing dot,
    an explicit default port, and the textual form of an IP address do not make
    two origins different — and refused when the text could be read as more
    than one destination: embedded credentials, whitespace or backslashes, an
    invalid port, or a numeric host that is not a plain dotted-quad IPv4
    address (``127.1``, ``0x7f.0.0.1``, ``2130706433``).
    """
    text = (endpoint or "").strip()
    if not text or any(ch.isspace() or ord(ch) < 0x20 or ch == "\\" for ch in text):
        raise ProviderPolicyError("endpoint_invalid")
    parsed = urlsplit(text)
    scheme = parsed.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise ProviderPolicyError("endpoint_invalid")
    if "@" in parsed.netloc:
        raise ProviderPolicyError("endpoint_userinfo_rejected")
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise ProviderPolicyError("endpoint_invalid")
    try:
        port = parsed.port or _DEFAULT_PORTS[scheme]
    except ValueError as exc:
        raise ProviderPolicyError("endpoint_invalid") from exc
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if all(_NUMERIC_LABEL.match(label) for label in host.split(".")):
            raise ProviderPolicyError("endpoint_ambiguous_host") from None
        return f"{scheme}://{host}:{port}"
    rendered = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    return f"{scheme}://{rendered}:{port}"


def authorize_model_destination(
    endpoint: str,
    *,
    kind: str,
    connection: Mapping[str, str] | None,
    default_endpoint: str = "",
) -> None:
    """Refuse an off-machine model destination the owner's connection does not name.

    The rule the retired environment allowlist was standing in for, stated
    where the owner's decision actually lives:

    * a ``local_machine`` endpoint needs no connection — nothing leaves the host;
    * an off-machine endpoint needs a saved connection for *this* profile
      (``model_connection_required``);
    * and it must be the origin that connection is bound to — the endpoint the
      owner saved, or, for a connection that saved only a key, the profile's own
      shipped endpoint (``model_connection_origin_mismatch``). An environment
      override or a profile edit cannot move a saved connection somewhere else.

    The connection is the owner's act, made while authenticated, and an agent
    has no path to create or change one; that is what makes it the authority.
    """
    if kind not in OFF_MACHINE_KINDS:
        return
    if not connection:
        raise ProviderPolicyError("model_connection_required")
    bound = str(connection.get("endpoint", "") or "").strip() or (default_endpoint or "").strip()
    if not bound:
        raise ProviderPolicyError("model_connection_origin_unbound")
    if canonical_origin(bound) != canonical_origin(endpoint):
        raise ProviderPolicyError("model_connection_origin_mismatch")


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
    """Classify *endpoint* and refuse it when the profile's own declaration rules it out.

    This is the profile's shape, not the owner's authorization: a ``local_only``
    profile may never leave the machine, a hosted endpoint needs HTTPS unless the
    profile allows plain HTTP, and OpenRouter must declare its egress and budget
    policy. Whether an off-machine destination may be reached at all is decided
    per owner by :func:`authorize_model_destination` and the hosted/private gates.
    """
    kind = "remote_hosted" if policy.provider.lower() == "openrouter" else classify_endpoint(endpoint)
    if kind in {"invalid", "unknown"}:
        raise ProviderPolicyError(f"endpoint_{kind}")
    if policy.local_only and kind != "local_machine":
        raise ProviderPolicyError(f"local_only_rejects_{kind}")
    if kind == "remote_hosted":
        if policy.requires_budget_policy is False and policy.provider.lower() == "openrouter":
            raise ProviderPolicyError("openrouter_requires_budget_policy")
        if endpoint and urlparse(endpoint).scheme == "http" and not policy.allow_remote_http:
            raise ProviderPolicyError("hosted_http_endpoint_rejected")
    if policy.provider.lower() == "openrouter" and not (
        policy.requires_egress_policy and policy.requires_budget_policy
    ):
        raise ProviderPolicyError("openrouter_requires_egress_and_budget_policy")
    return kind
