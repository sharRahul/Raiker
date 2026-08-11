"""Where the agent's own web reads may go, and where they may never.

Raiker used to gate web egress on ``RAIKER_WEB_EGRESS_ALLOWLIST``: empty by
default, so ``web_fetch`` reached nothing until the owner named every host in
advance. That is the safest possible default and it made the feature unusable —
an agent that cannot read a documentation page answers from training instead,
which is its own kind of unsafe. This module replaces it with the posture the
rest of Raiker already takes: **allow, monitor, and give the owner a precise
instrument for the things they want stopped.**

Two boundaries, and they are not the same kind of thing:

1. **The owner's blocklist** — ``RAIKER_WEB_EGRESS_BLACKLIST`` plus whatever the
   owner has stored in the app. Advisory in the sense that it is *their* policy:
   they add to it, they remove from it, and an empty one means "anywhere public".
2. **The address guard** — private, loopback, link-local, unique-local,
   reserved, and multicast destinations. This one is **not** owner-editable and
   has no allow path. It is what stops a page fetch becoming a request to the
   machine's own network, a cloud metadata service, or the router in the next
   room, and none of those become safe because somebody cleared a blocklist.

The guard is enforced against **every address a name resolves to**, and the
connection is then pinned to an address that passed, so a name that answers with
a public address and a private one — or answers differently the second time —
cannot slip through the gap between the check and the connect.
"""
from __future__ import annotations

import contextlib
import ipaddress
import os
import re
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

BLOCKLIST_ENV = "RAIKER_WEB_EGRESS_BLACKLIST"

RuleKind = Literal["domain", "wildcard", "regex", "address", "network"]

#: Names that resolve inside a cloud or container host and hand out credentials.
#: The address guard already refuses where these point, but a name is worth
#: refusing on its own: it fails earlier, it fails without a DNS lookup, and the
#: refusal says *what* was recognised rather than "that resolved somewhere
#: private", which is a much less useful thing to read in an audit log.
DEFAULT_BLOCKED_NAMES: tuple[str, ...] = (
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "*.internal",
    "*.local",
    "*.localdomain",
    "*.home.arpa",
    "localhost",
)

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
MAX_RULE_LENGTH = 253
MAX_REGEX_LENGTH = 200


class BlocklistRuleError(ValueError):
    """A rule the owner typed that cannot be turned into a matcher."""


@dataclass(frozen=True)
class BlocklistRule:
    """One owner rule: an exact host, a wildcard, a regex, an address, or a network."""

    raw: str
    kind: RuleKind
    _pattern: Any = None

    def matches_host(self, host: str) -> bool:
        target = host.strip().lower().rstrip(".")
        if not target:
            return False
        if self.kind == "domain":
            # An exact name also covers its subdomains: an owner who blocks
            # `ads.example.com` does not expect `eu.ads.example.com` to be a way
            # around it. Suffix matching is on a label boundary, so blocking
            # `example.com` never catches `notexample.com`.
            return target == self.raw or target.endswith("." + self.raw)
        if self.kind == "wildcard":
            return bool(self._pattern.fullmatch(target))
        if self.kind == "regex":
            return bool(self._pattern.search(target))
        return False

    def matches_address(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        if self.kind == "address":
            return address == self._pattern
        if self.kind == "network":
            return address.version == self._pattern.version and address in self._pattern
        return False


def parse_rule(raw: str) -> BlocklistRule:
    """Turn one owner-written line into a matcher, or say why it cannot be one.

    Accepted, in the order they are recognised:

    * ``/pattern/`` — a regular expression, matched against the hostname.
    * ``10.0.0.0/8``, ``fd00::/8`` — a network.
    * ``203.0.113.4`` — a single address.
    * ``*.ads.example.com`` — a wildcard over labels.
    * ``example.com`` — an exact name, which also covers its subdomains.
    """
    text = (raw or "").strip().lower().rstrip(".")
    if not text:
        raise BlocklistRuleError("blocklist_rule_empty")
    if len(text) > MAX_RULE_LENGTH:
        raise BlocklistRuleError("blocklist_rule_too_long")

    if text.startswith("/") and text.endswith("/") and len(text) > 2:
        body = text[1:-1]
        if len(body) > MAX_REGEX_LENGTH:
            raise BlocklistRuleError("blocklist_regex_too_long")
        try:
            # Compiled once, here, so a rule that cannot compile is refused when
            # the owner saves it rather than swallowed on the request path where
            # a broken pattern would silently stop blocking anything.
            compiled = re.compile(body, re.IGNORECASE)
        except re.error as exc:
            raise BlocklistRuleError(f"blocklist_regex_invalid:{exc.msg}") from None
        return BlocklistRule(text, "regex", compiled)

    if "/" in text:
        try:
            network = ipaddress.ip_network(text, strict=False)
        except ValueError:
            raise BlocklistRuleError("blocklist_network_invalid") from None
        return BlocklistRule(str(network), "network", network)

    try:
        return BlocklistRule(text, "address", ipaddress.ip_address(text))
    except ValueError:
        pass

    if "*" in text or "?" in text:
        if not all(_LABEL.match(part) for part in text.split(".") if part not in {"*", ""}):
            raise BlocklistRuleError("blocklist_wildcard_invalid")
        pattern = re.escape(text).replace(r"\*", "[^.]*").replace(r"\?", "[^.]")
        return BlocklistRule(text, "wildcard", re.compile(pattern, re.IGNORECASE))

    if not all(_LABEL.match(part) for part in text.split(".")):
        raise BlocklistRuleError("blocklist_domain_invalid")
    return BlocklistRule(text, "domain", None)


def parse_rules(values: object) -> tuple[BlocklistRule, ...]:
    """Parse many rules, skipping the ones that cannot compile.

    Used for the *env* source, where refusing to start over one bad line would
    be worse than dropping it. The stored source validates on write instead, so
    the owner is told at the point they can fix it.
    """
    if isinstance(values, str):
        values = re.split(r"[,\n]", values)
    rules: list[BlocklistRule] = []
    seen: set[str] = set()
    for value in values if isinstance(values, (list, tuple)) else []:
        try:
            rule = parse_rule(str(value))
        except BlocklistRuleError:
            continue
        if rule.raw not in seen:
            seen.add(rule.raw)
            rules.append(rule)
    return tuple(rules)


def env_blocklist() -> tuple[BlocklistRule, ...]:
    """The process-level blocklist. Comma- or newline-separated."""
    return parse_rules(os.environ.get(BLOCKLIST_ENV, ""))


def load_blocklist(
    store: SQLiteStore | None = None, principal_id: str | None = None
) -> tuple[BlocklistRule, ...]:
    """Every rule in force: the built-in names, the env var, and the owner's own.

    The three sources are a union and never a precedence chain — a blocklist that
    could be *shortened* by another source would be a way to unblock something,
    which is the one thing this list must not offer.
    """
    rules: list[BlocklistRule] = list(parse_rules(list(DEFAULT_BLOCKED_NAMES)))
    seen = {rule.raw for rule in rules}
    sources: list[BlocklistRule] = list(env_blocklist())
    if store is not None:
        # An unreadable store must never *shorten* the blocklist, so a failure
        # here leaves the built-in and env rules standing rather than raising.
        with contextlib.suppress(Exception):
            sources.extend(parse_rules(store.list_web_blocklist_rules(principal_id=principal_id)))
    for rule in sources:
        if rule.raw not in seen:
            seen.add(rule.raw)
            rules.append(rule)
    return tuple(rules)


# ── The address guard (not owner-editable) ───────────────────────────────────


def address_is_reachable(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """False for anything that is not a public, routable destination.

    ``is_global`` alone is not enough. An IPv4-mapped IPv6 address such as
    ``::ffff:127.0.0.1`` reports itself as a v6 address whose v4 payload is the
    loopback, and reading only the outer form is a documented way past this kind
    of check — so a mapped address is unwrapped and judged on what it really is.
    """
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    sixtofour = getattr(address, "sixtofour", None)
    if sixtofour is not None:
        address = sixtofour
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ) and address.is_global


def resolve_public_addresses(host: str, port: int = 443) -> list[str]:
    """Every address *host* resolves to, or ``[]`` if any one of them is private.

    All-or-nothing on purpose. A name that answers with one public address and
    one private address is a name being used to reach the private one, and
    picking the public answer out of the set would be doing exactly what the
    attack wants.
    """
    literal = _as_address(host)
    if literal is not None:
        return [str(literal)] if address_is_reachable(literal) else []
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError:
        return []
    addresses: list[str] = []
    for info in infos:
        try:
            parsed = ipaddress.ip_address(info[4][0])
        except ValueError:
            return []
        if not address_is_reachable(parsed):
            return []
        addresses.append(str(parsed))
    return addresses


def _as_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The address *host* literally is, including bracketed IPv6 and integer forms."""
    text = host.strip().strip("[]")
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        pass
    # `http://2130706433/` is a legal spelling of 127.0.0.1 that `ip_address`
    # rejects as a string but accepts as an integer. Left unhandled, the name
    # falls through to a DNS lookup that resolves it to the loopback anyway —
    # this just refuses it earlier and by its real value.
    if text.isdigit():
        try:
            return ipaddress.ip_address(int(text))
        except ValueError:
            return None
    return None


# ── The decision ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EgressDecision:
    """Whether one destination may be reached, and the addresses it resolved to."""

    allowed: bool
    reason: str = ""
    detail: str = ""
    addresses: tuple[str, ...] = ()

    @property
    def reason_code(self) -> str:
        return f"{self.reason}:{self.detail}" if self.detail else self.reason


def evaluate_host(
    host: str, rules: tuple[BlocklistRule, ...], *, port: int = 443
) -> EgressDecision:
    """Decide one hostname against the blocklist and then the address guard.

    Order matters: the blocklist is checked first so an owner's own rule is the
    reason given, and so a name they blocked costs no DNS lookup at all.
    """
    target = (host or "").strip().lower().rstrip(".")
    if not target:
        return EgressDecision(False, "web_url_invalid")

    for rule in rules:
        if rule.matches_host(target):
            return EgressDecision(False, "web_egress_blocked", target)

    literal = _as_address(target)
    if literal is not None:
        for rule in rules:
            if rule.matches_address(literal):
                return EgressDecision(False, "web_egress_blocked", target)

    addresses = resolve_public_addresses(target, port)
    if not addresses:
        return EgressDecision(False, "web_host_not_public", target)

    for address in addresses:
        parsed = ipaddress.ip_address(address)
        for rule in rules:
            if rule.matches_address(parsed):
                return EgressDecision(False, "web_egress_blocked", f"{target} ({address})")

    return EgressDecision(True, addresses=tuple(addresses))


def refusal_message(reason_code: str) -> str:
    """What to tell the owner, in their terms, about a refused destination."""
    reason = reason_code.split(":", 1)[0]
    return {
        "web_url_not_https": "Web access denied: only https URLs may be fetched.",
        "web_url_invalid": "Web access denied: that is not a fetchable URL.",
        "web_url_credentials": (
            "Web access denied: a URL carrying a username or password is never fetched."
        ),
        "web_egress_blocked": (
            "Web access denied: that destination is on your blocked list "
            "(Settings → Web access, or RAIKER_WEB_EGRESS_BLACKLIST)."
        ),
        "web_host_not_public": (
            "Web access denied: that host resolves to a private, loopback, or link-local "
            "address. Raiker never fetches from your own network, and this is not a "
            "setting — it is what stops a web read becoming a request to your router, "
            "your NAS, or a cloud metadata service."
        ),
    }.get(reason, "Web access denied.")


# ── Pinned transport ─────────────────────────────────────────────────────────
#
# Checking a name and then handing that *name* to the HTTP client re-resolves it,
# and the second answer does not have to match the first. That gap is DNS
# rebinding, and it is the standard way past a validate-then-fetch guard: the
# name answers publicly for the check and privately for the connection.
#
# So the connection is made to an address that already passed, while the TLS
# handshake and the Host header keep the original name — certificate validation
# is unchanged, and the destination cannot move between the check and the socket.


def pinned_https_opener(host: str, address: str) -> Any:
    """A urllib opener that dials *address* but speaks TLS as *host*."""
    import http.client
    import ssl
    import urllib.request

    context = ssl.create_default_context()

    class _PinnedConnection(http.client.HTTPSConnection):
        def __init__(self, target: str, **kwargs: Any) -> None:
            kwargs.pop("context", None)
            super().__init__(target, context=context, **kwargs)
            # `server_hostname` drives SNI and certificate matching; only the
            # dialled address changes, so a pinned request to a host whose
            # certificate does not match still fails exactly as it should.
            self.server_hostname = host
            self._pinned = address

        def connect(self) -> None:
            import socket as _socket

            self.sock = _socket.create_connection(
                (self._pinned, self.port or 443), self.timeout
            )
            # `_tunnel_host` is set by `set_tunnel()` for proxy CONNECT. Raiker
            # sets no proxy on this path, but honouring it keeps the subclass
            # behaving like the base connection rather than quietly dropping a
            # tunnel somebody configured.
            if getattr(self, "_tunnel_host", None):
                self._tunnel()  # type: ignore[attr-defined]
            self.sock = context.wrap_socket(self.sock, server_hostname=host)

    class _PinnedHandler(urllib.request.HTTPSHandler):
        def https_open(self, req: Any) -> Any:
            return self.do_open(_PinnedConnection, req)

    return urllib.request.build_opener(_PinnedHandler)
