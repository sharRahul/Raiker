"""Where a remote MCP server may live, and what Raiker will say about it.

**RR-MCP-02.** Adding a remote MCP server was one scheme check — ``http`` or
``https``, and a non-empty host — and then the session went wherever the string
pointed. That left five different destinations indistinguishable from each
other: the owner's own machine, a box on their LAN, a public endpoint, a public
*name* that answers with a private address, and a cloud metadata service that
hands out credentials to anyone who asks. All five read as "Remote (HTTPS)" on
the card, and the owner's bearer token went to all five the same way.

This module is the distinction. It is deliberately **not** a hard block on the
owner's choices — Raiker is owner-authoritative and monitored, and a local MCP
server on ``http://127.0.0.1`` is the ordinary case, not a threat. What it
refuses is the narrow set where the destination is *not the thing the owner
typed*:

* a name that presents as public and answers with a private, loopback or
  link-local address — the standard shape of a server-side request forgery, and
  not a destination anybody chose;
* link-local, multicast, reserved and cloud-metadata addresses, which are how a
  request becomes a credential read rather than a tool call;
* a public endpoint over plain ``http``, because an owner typing a hostname did
  not choose to put their token on the wire in clear text;
* a URL carrying its own username and password, which is a credential in a
  string that gets logged, copied and shown.

Everything else is classified, named on the card, and allowed:

``loopback``
    The owner's own machine. ``http`` is fine here; there is no network to
    listen on, and requiring TLS on localhost would only mean nobody could run
    a local server.
``private_network``
    The owner's own LAN — an RFC 1918 or unique-local address, or a name under
    ``.internal``/``.lan``/``.local``/``.home.arpa``. Allowed, because a NAS or
    a workstation running a tool server is a thing owners legitimately have, and
    named as unencrypted when it is, so the choice is visible rather than
    assumed.
``public``
    Everything else. HTTPS, resolved, address-guarded, and pinned to an address
    that passed — so the destination cannot move between the check and the
    socket.

The pin matters as much as the check. Validating a *name* and then handing that
name to the HTTP client re-resolves it, and the second answer does not have to
match the first; that gap is DNS rebinding and it is the standard way past a
validate-then-connect guard. :func:`evaluate_endpoint` therefore returns the
address to dial, and the transport dials it while speaking TLS as the original
name.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

from raiker.runtime.web_policy import address_is_reachable, literal_address

__all__ = [
    "LOOPBACK",
    "PRIVATE_NETWORK",
    "PUBLIC",
    "EndpointTrust",
    "endpoint_refusal_message",
    "evaluate_endpoint",
    "network_class_label",
    "stated_network_class",
]

#: The owner's own machine.
LOOPBACK = "loopback"
#: The owner's own network.
PRIVATE_NETWORK = "private_network"
#: Anywhere else.
PUBLIC = "public"

#: Names that resolve inside a cloud or container host and answer with
#: credentials. The address guard already covers where they point; refusing the
#: name as well fails earlier, costs no lookup, and gives an audit line that
#: says what was recognised instead of "that resolved somewhere private".
_METADATA_NAMES: frozenset[str] = frozenset(
    {"metadata.google.internal", "metadata.goog", "instance-data", "metadata"}
)

#: Suffixes an owner uses for their own network. Kept in step with
#: :data:`raiker.runtime.web_policy.DEFAULT_BLOCKED_NAMES`, which refuses the
#: same names for agent web reads — a different question with a different
#: answer: the agent reading a page has no business on the owner's LAN, and the
#: owner adding their own tool server plainly does.
_PRIVATE_SUFFIXES: tuple[str, ...] = (".internal", ".lan", ".local", ".home.arpa")

_LOOPBACK_NAMES: frozenset[str] = frozenset({"localhost", "localhost.localdomain"})

#: How many times a remote endpoint may redirect before Raiker stops following.
#: Three is enough for the scheme/host normalisation a real deployment does and
#: short enough that a redirect loop ends as a refusal rather than a timeout.
MAX_REDIRECTS = 3


@dataclass(frozen=True)
class EndpointTrust:
    """One remote MCP endpoint, classified — and the address to actually dial."""

    allowed: bool
    network_class: str = PUBLIC
    reason: str = ""
    host: str = ""
    port: int = 0
    scheme: str = ""
    #: Every address the host resolved to, all of which passed the guard.
    addresses: tuple[str, ...] = ()
    #: The address the transport must connect to, for a destination where the
    #: name could otherwise be re-resolved between the check and the socket.
    #: ``None`` for loopback and private destinations, where the owner's own
    #: resolver is the authority and pinning would break split-horizon DNS.
    pin: str | None = None

    @property
    def encrypted(self) -> bool:
        return self.scheme == "https"

    @property
    def origin(self) -> str:
        """Scheme, host and port — what a redirect must keep to stay the same server."""
        return f"{self.scheme}://{self.host}:{self.port}"


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def stated_network_class(endpoint_url: str) -> str | None:
    """The class an endpoint *states*, from the URL alone and without a lookup.

    This is what a list of stored servers can render: it never blocks on DNS, it
    never changes while the page is open, and it is exactly as honest as the
    string the owner typed. ``None`` means the URL is not one Raiker would
    accept at all. A name that has to be resolved to be judged is reported as
    :data:`PUBLIC`, because that is what it claims to be; whether it *is* one is
    :func:`evaluate_endpoint`'s question, asked when a session is about to run.
    """
    parsed = urlsplit((endpoint_url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return None
    literal = literal_address(host)
    if literal is not None:
        mapped = getattr(literal, "ipv4_mapped", None) or literal
        if mapped.is_loopback or mapped.is_unspecified:
            return LOOPBACK
        if mapped.is_private:
            return PRIVATE_NETWORK
        return PUBLIC
    if host in _LOOPBACK_NAMES:
        return LOOPBACK
    if host in _METADATA_NAMES or host.endswith(_PRIVATE_SUFFIXES):
        return PRIVATE_NETWORK
    return PUBLIC


def network_class_label(network_class: str | None, *, encrypted: bool) -> str:
    """The phrase the owner reads on a server card.

    The page used to print "Remote (HTTPS)" for every ``http`` transport,
    including a plain-``http`` endpoint and including the owner's own laptop.
    Three different destinations under one reassuring label is the kind of
    quietly wrong sentence this surface exists to avoid.
    """
    suffix = "HTTPS" if encrypted else "unencrypted HTTP"
    if network_class == LOOPBACK:
        return f"This machine ({suffix})"
    if network_class == PRIVATE_NETWORK:
        return f"Your network ({suffix})"
    if network_class == PUBLIC:
        return f"Remote ({suffix})"
    return "Remote (unrecognised endpoint)"


def _classify_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> tuple[str, str | None]:
    """``(network_class, refusal)`` for one literal address."""
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    sixtofour = getattr(address, "sixtofour", None)
    if sixtofour is not None:
        address = sixtofour
    if address.is_loopback or address.is_unspecified:
        return LOOPBACK, None
    # Link-local is where a cloud instance keeps its credential service, and
    # multicast, reserved and unspecified destinations are not servers anybody
    # runs a tool endpoint on. None of these is an owner choice being refused.
    if address.is_link_local:
        return PRIVATE_NETWORK, "mcp_remote_link_local"
    if address.is_multicast or address.is_reserved:
        return PRIVATE_NETWORK, "mcp_remote_address_forbidden"
    if address.is_private:
        return PRIVATE_NETWORK, None
    if not address_is_reachable(address):
        return PUBLIC, "mcp_remote_address_forbidden"
    return PUBLIC, None


def evaluate_endpoint(
    endpoint_url: str,
    *,
    resolve: bool = True,
) -> EndpointTrust:
    """Classify one endpoint and decide whether a session may run against it.

    *resolve* exists for the add-time check, where refusing an endpoint because
    the machine happens to be offline would be a worse answer than accepting it
    and classifying it again when it is actually used.
    """
    parsed = urlsplit((endpoint_url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return EndpointTrust(False, reason="mcp_remote_invalid_endpoint")
    if parsed.username or parsed.password:
        # A credential in a URL is a credential in every log, every event
        # payload and every card that ever prints it. `auth_ref` exists so the
        # token can live in one place the owner controls.
        return EndpointTrust(False, reason="mcp_remote_endpoint_credentials")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return EndpointTrust(False, reason="mcp_remote_invalid_endpoint")
    try:
        port = parsed.port or _default_port(parsed.scheme)
    except ValueError:
        return EndpointTrust(False, reason="mcp_remote_invalid_endpoint")

    base = EndpointTrust(False, host=host, port=port, scheme=parsed.scheme)

    if host in _METADATA_NAMES:
        return _deny(base, PRIVATE_NETWORK, "mcp_remote_metadata_endpoint")

    literal = literal_address(host)
    if literal is not None:
        network_class, refusal = _classify_address(literal)
        if refusal is not None:
            return _deny(base, network_class, refusal)
        if network_class == PUBLIC and parsed.scheme != "https":
            return _deny(base, network_class, "mcp_remote_requires_https")
        return EndpointTrust(
            True,
            network_class=network_class,
            host=host,
            port=port,
            scheme=parsed.scheme,
            addresses=(str(literal),),
            pin=str(literal) if network_class == PUBLIC else None,
        )

    if host in _LOOPBACK_NAMES:
        return EndpointTrust(
            True, network_class=LOOPBACK, host=host, port=port, scheme=parsed.scheme
        )
    if host.endswith(_PRIVATE_SUFFIXES):
        return EndpointTrust(
            True, network_class=PRIVATE_NETWORK, host=host, port=port, scheme=parsed.scheme
        )

    # A name that claims to be public is held to what a public endpoint is:
    # TLS, and an answer that is actually public.
    if parsed.scheme != "https":
        return _deny(base, PUBLIC, "mcp_remote_requires_https")
    if not resolve:
        return EndpointTrust(
            True, network_class=PUBLIC, host=host, port=port, scheme=parsed.scheme
        )

    addresses = _resolve_public(host, port)
    if addresses is None:
        return _deny(base, PUBLIC, "mcp_remote_host_unresolved")
    if not addresses:
        return _deny(base, PUBLIC, "mcp_remote_host_not_public")
    return EndpointTrust(
        True,
        network_class=PUBLIC,
        host=host,
        port=port,
        scheme=parsed.scheme,
        addresses=tuple(addresses),
        pin=addresses[0],
    )


def _deny(base: EndpointTrust, network_class: str, reason: str) -> EndpointTrust:
    return EndpointTrust(
        False,
        network_class=network_class,
        reason=reason,
        host=base.host,
        port=base.port,
        scheme=base.scheme,
    )


def _resolve_public(host: str, port: int) -> list[str] | None:
    """Every address *host* resolves to, ``[]`` if any one of them is not public,
    or ``None`` when the name could not be resolved at all.

    All-or-nothing on the private answer, on purpose: a name that answers with
    one public address and one private address is a name being used to reach the
    private one, and picking the public answer out of the set is precisely what
    that arrangement is for. The unresolved case is told apart from the refused
    one because they are different things to read — one is a machine that is
    offline, the other is a destination Raiker will not go to.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError:
        return None
    addresses: list[str] = []
    for info in infos:
        try:
            parsed = ipaddress.ip_address(info[4][0])
        except ValueError:
            return []
        if not address_is_reachable(parsed):
            return []
        addresses.append(str(parsed))
    return addresses or None


def endpoint_refusal_message(reason_code: str) -> str:
    """What to tell the owner, in their terms, about an endpoint Raiker refused."""
    reason = reason_code.split(":", 1)[0]
    return {
        "mcp_remote_invalid_endpoint": (
            "That is not an MCP endpoint Raiker can reach. Use an http or https URL "
            "with a host, for example https://tools.example.com/mcp."
        ),
        "mcp_remote_endpoint_credentials": (
            "A URL carrying a username or password is never used. Put the token in an "
            "environment variable and name that variable instead — the token then stays "
            "in one place you control, rather than in every log that prints the URL."
        ),
        "mcp_remote_requires_https": (
            "A server outside this machine and your own network must use https. Over plain "
            "http the token and every tool call travel in clear text, and that is not "
            "something typing a hostname asked for."
        ),
        "mcp_remote_metadata_endpoint": (
            "That name belongs to a cloud metadata service, which answers with the "
            "credentials of the machine Raiker is running on. It is not a tool server."
        ),
        "mcp_remote_link_local": (
            "That address is link-local. It is where a cloud instance keeps its credential "
            "service, not where a tool server lives."
        ),
        "mcp_remote_address_forbidden": (
            "That address is not one a server can be reached at — it is multicast, "
            "reserved, or otherwise not a destination."
        ),
        "mcp_remote_host_not_public": (
            "That hostname resolves to an address on a private network. A public name "
            "answering with a private address is how a request to a tool server becomes a "
            "request to your router or a cloud metadata service. If the server really is "
            "on your own network, add it by its address or its .internal name."
        ),
        "mcp_remote_host_unresolved": (
            "That hostname could not be resolved. Check the spelling, and check that this "
            "machine has network access."
        ),
        "mcp_remote_redirect_untrusted": (
            "That server redirected the session to a destination Raiker will not follow. "
            "A redirect is re-checked exactly like the original endpoint, so a server "
            "cannot send a session somewhere the endpoint itself could not go."
        ),
        "mcp_remote_too_many_redirects": (
            "That server redirected the session more times than Raiker follows."
        ),
    }.get(reason, "That MCP endpoint was refused.")
