"""Which *address* a model request may reach, decided when the socket is opened.

BUG-349. ADR-0004 binds every off-machine model request to the origin of the
owner's saved connection, and :func:`~raiker.models.endpoint_policy.classify_endpoint`
labels that origin from its text. That decides which *name* a request may go
to. It said nothing about where the name led: the HTTP client resolved it when
it opened a connection and dialled whatever came back, so a hosted name whose
DNS answer became ``10.0.0.5`` or ``127.0.0.1`` was sent the owner's key, and a
second lookup could answer differently from any first one (DNS rebinding).

This module closes that gap for both model transports (the transport
hardening plan's D1–D4, recorded as FIXED-1021 to FIXED-1030 in
``docs/plans/FIXED_ITEMS.md``):

* :func:`resolve_for_dial` resolves the host **once** and classifies **every**
  answer against the connection's declared class. One answer the class does not
  allow refuses the whole dial — picking the acceptable answer out of a mixed
  set is exactly what a rebinding name wants.
* :class:`GuardedNetworkBackend` is the httpcore network backend that uses it:
  it dials the address that passed, while httpcore keeps the original name for
  TLS SNI, certificate verification and the ``Host`` header. Every new
  connection is resolved and checked; a kept-alive one was checked when it was
  opened, so a pooled request pays for no lookup.
* :func:`proxy_for` makes the proxy decision explicit: a hosted origin honours
  the owner's ``HTTPS_PROXY``/``HTTP_PROXY``/``ALL_PROXY``/``NO_PROXY``; a
  loopback or private-network origin never uses a proxy. Behind a proxy the
  proxy resolves the name, so pinning cannot apply there — that is the owner's
  own route, and HTTPS through it is an end-to-end tunnel.

The address classifier is :mod:`raiker.runtime.web_policy`'s, not a second one.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import urlsplit

# Public in CPython since 3.x, absent from typeshed's stub.
from urllib.request import proxy_bypass_environment  # type: ignore[attr-defined]

import anyio
import httpcore

from raiker.models.exceptions import ProviderDialRefusedError
from raiker.runtime.web_policy import address_is_reachable, literal_address, unwrap_address

__all__ = [
    "METADATA_ADDRESSES",
    "METADATA_NAMES",
    "GuardedNetworkBackend",
    "Resolver",
    "dial_refusal",
    "proxy_for",
    "proxy_route",
    "refuse_metadata_destination",
    "resolve_for_dial",
]

Address = ipaddress.IPv4Address | ipaddress.IPv6Address
#: ``getaddrinfo``'s shape, so a test can answer differently on each call.
Resolver = Callable[..., list[tuple[Any, ...]]]

#: Cloud instance-metadata services (D3). Never a model destination, for any
#: class and with no opt-in: they hand out the machine's own cloud credentials.
METADATA_ADDRESSES: frozenset[Address] = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS, GCP, Azure, OpenStack, ...
        ipaddress.ip_address("fd00:ec2::254"),  # AWS over IPv6
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
    }
)
METADATA_NAMES: frozenset[str] = frozenset({"metadata.google.internal", "metadata.azure.com"})

#: Shared address space (RFC 6598). Not ``is_private`` to Python, and it is
#: where Tailscale and carrier-grade NAT put a home-lab machine.
_SHARED_ADDRESS_SPACE = ipaddress.ip_network("100.64.0.0/10")


def dial_refusal(detail: str) -> ProviderDialRefusedError:
    """The refusal for one reason, as ``model_dial_refused:<detail>``."""
    return ProviderDialRefusedError(f"model_dial_refused:{detail}")


def _host_of(endpoint: str) -> str:
    return (urlsplit(endpoint).hostname or "").rstrip(".").lower()


def refuse_metadata_destination(endpoint: str) -> None:
    """Refuse a metadata service named by its URL, before anything is resolved.

    Text-level, so a saved connection that names one is refused when it is
    validated — on the provider card — rather than only when it is dialled.
    """
    host = _host_of(endpoint)
    if host in METADATA_NAMES:
        raise dial_refusal("metadata_address")
    literal = literal_address(host)
    if literal is not None and unwrap_address(literal) in METADATA_ADDRESSES:
        raise dial_refusal("metadata_address")


def _answer_refusal(address: Address, declared_kind: str, *, allow_link_local: bool) -> str:
    """Why one resolved answer may not be dialled for this class, or ``""``."""
    real = unwrap_address(address)
    if real in METADATA_ADDRESSES:
        return "metadata_address"
    if declared_kind == "local_machine":
        return "" if real.is_loopback or real.is_unspecified else "non_loopback_for_local"
    if declared_kind == "remote_hosted":
        return "" if address_is_reachable(real) else "non_public_address"
    if declared_kind == "private_network":
        # A loopback answer for a private-network name is the owner's own
        # machine reached by another name; it says so rather than being
        # treated as the home-lab server the connection was saved for.
        if real.is_loopback:
            return "loopback_for_private"
        if real.is_link_local:
            return "" if allow_link_local else "link_local_address"
        if real.is_multicast or real.is_unspecified or real.is_reserved:
            return "non_private_address"
        if real.is_private or (real.version == 4 and real in _SHARED_ADDRESS_SPACE):
            return ""
        if address_is_reachable(real):
            # A home-lab name that starts resolving to the internet is noticed.
            return "public_address_for_private"
        return "non_private_address"
    return "unclassified_endpoint"


def resolve_for_dial(
    host: str,
    port: int,
    declared_kind: str,
    *,
    allow_link_local: bool = False,
    resolver: Resolver | None = None,
) -> list[str]:
    """Every address *host* resolves to, in order, when all of them are allowed.

    Raises :class:`ProviderDialRefusedError` naming the first answer's reason
    when any answer is not allowed for *declared_kind*, and
    :class:`httpcore.ConnectError` when the name does not resolve at all — that
    one is a connection failure, not a policy answer.
    """
    target = (host or "").strip().strip("[]").rstrip(".").lower()
    if target in METADATA_NAMES:
        raise dial_refusal("metadata_address")
    literal = literal_address(target)
    if literal is not None:
        answers: list[Address] = [literal]
    else:
        lookup = resolver or socket.getaddrinfo
        try:
            infos = lookup(target, port, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise httpcore.ConnectError(f"name_unresolved:{type(exc).__name__}") from None
        answers = []
        for info in infos:
            try:
                answers.append(ipaddress.ip_address(str(info[4][0]).split("%", 1)[0]))
            except ValueError:
                raise dial_refusal("unreadable_address") from None
        if not answers:
            raise httpcore.ConnectError("name_unresolved:empty")
    ordered: list[str] = []
    for answer in answers:
        reason = _answer_refusal(answer, declared_kind, allow_link_local=allow_link_local)
        if reason:
            raise dial_refusal(reason)
        text = str(answer)
        if text not in ordered:
            ordered.append(text)
    return ordered


class GuardedNetworkBackend(httpcore.AsyncNetworkBackend):
    """An httpcore backend that dials only addresses that passed the guard.

    httpcore asks for ``connect_tcp(host=<the URL's name>)`` and then starts TLS
    with ``server_hostname=<the URL's name>``, so replacing only the address
    here leaves SNI, certificate matching and the ``Host`` header on the name.

    Answers are tried in resolver order (IPv6 and IPv4 as the system prefers
    them) and only ever among the ones that passed — never a fallback to an
    address the guard refused, because a refused answer refuses the dial.
    """

    def __init__(
        self,
        declared_kind: str,
        *,
        allow_link_local: bool = False,
        resolver: Resolver | None = None,
        inner: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.declared_kind = declared_kind
        self.allow_link_local = allow_link_local
        self._resolver = resolver
        self._inner = inner or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await anyio.to_thread.run_sync(
            lambda: resolve_for_dial(
                host,
                port,
                self.declared_kind,
                allow_link_local=self.allow_link_local,
                resolver=self._resolver,
            )
        )
        failure: Exception | None = None
        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                failure = exc
        assert failure is not None  # resolve_for_dial never returns an empty list
        raise failure

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        # A model origin is always host and port; a socket path is not one.
        raise dial_refusal("unix_socket_not_a_model_destination")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def proxy_for(endpoint: str, declared_kind: str) -> str | None:
    """The proxy URL a request to *endpoint* goes through, or ``None`` for direct.

    D4. Only a hosted origin is ever proxied, and only by the owner's own
    environment (``HTTPS_PROXY``/``HTTP_PROXY``/``ALL_PROXY``, minus
    ``NO_PROXY``). A loopback or private-network origin is dialled directly:
    a home-lab server is on the owner's network, and handing its traffic — and
    over plain HTTP, its key — to a proxy is not where the owner meant it to go.
    """
    if declared_kind != "remote_hosted":
        return None
    split = urlsplit(endpoint)
    scheme = (split.scheme or "https").lower()
    host = (split.hostname or "").rstrip(".").lower()
    proxies = urllib.request.getproxies_environment()
    chosen = proxies.get(scheme) or proxies.get("all")
    if not chosen or not host:
        return None
    netloc = f"{host}:{split.port}" if split.port else host
    if proxy_bypass_environment(netloc, proxies):
        return None
    return chosen


def proxy_route(endpoint: str, declared_kind: str) -> str:
    """``host:port`` of the proxy *endpoint* goes through, or ``""`` for direct.

    What the Models page states. Never the proxy URL itself: a proxy URL can
    carry a user name and password, and the page is not the place for either.
    """
    chosen = proxy_for(endpoint, declared_kind)
    if not chosen:
        return ""
    split = urlsplit(chosen if "//" in chosen else f"//{chosen}")
    host = split.hostname or ""
    try:
        port = split.port
    except ValueError:
        port = None
    return f"{host}:{port}" if port else host
