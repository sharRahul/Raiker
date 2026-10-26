"""Where the agent's own web reads may go, and where they may never.

The posture is the one the rest of Raiker takes: **allow, monitor, and give
the owner a precise instrument for the things they want stopped** (RAIKER-2021).
An agent that cannot read a documentation page answers from training instead,
which is its own kind of unsafe, so an empty owner blocklist means "anywhere
public" — never "anywhere".

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
import urllib.request
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


def unwrap_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """The address a mapped or 6to4 IPv6 form really carries.

    An IPv4-mapped IPv6 address such as ``::ffff:127.0.0.1`` reports itself as a
    v6 address whose v4 payload is the loopback, and reading only the outer form
    is a documented way past an address check — so every classifier judges the
    unwrapped address instead.
    """
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        return mapped
    sixtofour = getattr(address, "sixtofour", None)
    if sixtofour is not None:
        return sixtofour
    return address


def address_is_reachable(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """False for anything that is not a public, routable destination.

    ``is_global`` alone is not enough: a mapped address is unwrapped first
    (:func:`unwrap_address`) and judged on what it really is.
    """
    address = unwrap_address(address)
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
    literal = literal_address(host)
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


def resolves_at_all(host: str, port: int = 443) -> bool:
    """Whether *host* has any address at all from this machine, public or not."""
    try:
        return bool(socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP))
    except OSError:
        return False


def literal_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
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
    #: DEC-21 (Web access) — the blocklist rule that refused it, as written.
    rule: str = ""
    #: TOOL-91 (2026-10-25, owner's decision) — the owner's own rules a web read
    #: matched. A web read is never refused for them; it is fetched and alerted.
    flagged: tuple[str, ...] = ()
    #: ``direct`` (dialled at a checked address) or ``proxy`` (BUG-353: this
    #: machine cannot resolve names itself and the owner's proxy carries it).
    route: str = "direct"
    proxy: str = ""

    @property
    def reason_code(self) -> str:
        return f"{self.reason}:{self.detail}" if self.detail else self.reason


_DEFAULT_RULES = frozenset(DEFAULT_BLOCKED_NAMES)


def web_proxy_for(scheme: str, host: str, port: int | None = None) -> str:
    """The owner's proxy for *scheme*://*host*, or ``""`` (BUG-353).

    Read from the process environment (``HTTPS_PROXY``, ``HTTP_PROXY``,
    ``ALL_PROXY`` minus ``NO_PROXY``), exactly as the model transport does.
    """
    import urllib.request
    from urllib.request import proxy_bypass_environment  # type: ignore[attr-defined]

    proxies = urllib.request.getproxies_environment()
    chosen = proxies.get(scheme) or proxies.get("all") or ""
    if not chosen or not host:
        return ""
    netloc = f"{host}:{port}" if port else host
    if proxy_bypass_environment(netloc, proxies):
        return ""
    return chosen


#: Top-level labels that name a private network rather than the internet:
#: RFC 6761/6762/8375 special-use names and the suffixes networks commonly use
#: for themselves. A name ending in one is never handed to a proxy (SSRF).
_INTERNAL_SUFFIXES = frozenset({
    "local", "localhost", "localdomain", "internal", "intranet", "corp", "home",
    "lan", "private", "priv", "test", "invalid", "example", "arpa", "onion",
    "domain", "workgroup", "home-network", "intra", "office", "cluster",
})
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def public_shaped_name(host: str) -> bool:
    """Whether *host* looks like an internet name, judged without resolving it.

    The proxy route exists for a machine that cannot resolve public names
    itself. The owner's proxy can often resolve *internal* names too, so a name
    this machine cannot check is sent to it only when it has the shape of a
    public one: at least two valid labels and an alphabetic top-level label that
    is not a private-network suffix. A single-label name (``intranet``), a
    literal address, or ``wiki.corp`` is refused instead.
    """
    labels = (host or "").strip().lower().rstrip(".").split(".")
    if len(labels) < 2 or not all(_LABEL.match(label) for label in labels):
        return False
    top = labels[-1]
    if not (top.isalpha() or top.startswith("xn--")) or len(top) < 2:
        return False
    return top not in _INTERNAL_SUFFIXES


#: SSRF — where a proxied name is looked up before the proxy is asked to reach
#: it (DNS over HTTPS, JSON form). The owner may point it at their own resolver.
DOH_ENDPOINT_ENV = "RAIKER_WEB_DOH_ENDPOINT"
DEFAULT_DOH_ENDPOINT = "https://cloudflare-dns.com/dns-query"
_DOH_TIMEOUT_SECONDS = 5.0


def resolve_via_proxy(host: str, proxy: str) -> list[str] | None:
    """Every A and AAAA answer for *host*, looked up over HTTPS through *proxy*.

    ``[]`` when the name has no address, ``None`` when the lookup could not be
    made or read: the caller refuses the read either way, since an answer it
    cannot check is not one it may act on. A DoH answer is not a pin (the proxy
    resolves again when it connects), so a name re-pointed between the two
    lookups is the residual; a name that simply points inside a network is not.
    """
    import json
    from urllib.parse import quote
    from urllib.request import ProxyHandler, Request, build_opener

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args: object, **kwargs: object) -> None:
            return None

    endpoint = os.environ.get(DOH_ENDPOINT_ENV, "").strip() or DEFAULT_DOH_ENDPOINT
    if not endpoint.startswith("https://"):
        return None
    opener = build_opener(ProxyHandler({"https": proxy}), _NoRedirect())
    found: list[str] = []
    for record_type, code in (("A", 1), ("AAAA", 28)):
        url = f"{endpoint}{'&' if '?' in endpoint else '?'}name={quote(host)}&type={record_type}"
        request = Request(url, headers={"Accept": "application/dns-json"})  # noqa: S310 - https only
        try:
            with opener.open(request, timeout=_DOH_TIMEOUT_SECONDS) as response:  # noqa: S310
                answer = json.loads(response.read(65_536).decode("utf-8"))
        except Exception:  # noqa: BLE001 — an unreadable lookup is no answer
            return None
        if not isinstance(answer, dict) or answer.get("Status") not in (0, 3):
            return None
        for record in answer.get("Answer") or []:
            if isinstance(record, dict) and record.get("type") == code:
                try:
                    found.append(str(ipaddress.ip_address(str(record.get("data", "")))))
                except ValueError:
                    return None
    return found


def evaluate_host(
    host: str,
    rules: tuple[BlocklistRule, ...],
    *,
    port: int = 443,
    flag_owner_rules: bool = False,
    allow_proxy: bool = False,
    scheme: str = "https",
) -> EgressDecision:
    """Decide one hostname against the blocklist and then the address guard.

    Order matters: the blocklist is checked first so an owner's own rule is the
    reason given, and so a name they blocked costs no DNS lookup at all.

    ``flag_owner_rules`` (web reads, owner's decision of 2026-10-25): a rule the
    owner or the environment added does not refuse; the decision is allowed and
    names the rule in ``flagged``. The built-in names — the local network and
    cloud metadata services — still refuse, as the address guard does, because
    neither is a page on the internet.

    ``allow_proxy`` (BUG-353): when this machine cannot resolve the name at all
    and the owner's environment names a proxy for the scheme, the read goes
    through that proxy. A name that resolves here to a private address is still
    refused; only an unresolvable one takes the proxy route, and only when it has
    the shape of a public name (:func:`public_shaped_name`), so the proxy is not
    used to reach the owner's internal names (SSRF). It is then looked up
    through the proxy (:func:`resolve_via_proxy`) and every answer must pass the
    address guard; a lookup that cannot be made refuses the read.
    """
    target = (host or "").strip().lower().rstrip(".")
    if not target:
        return EgressDecision(False, "web_url_invalid")

    flagged: list[str] = []

    def hit(rule: BlocklistRule, detail: str) -> EgressDecision | None:
        if flag_owner_rules and rule.raw not in _DEFAULT_RULES:
            if rule.raw not in flagged:
                flagged.append(rule.raw)
            return None
        return EgressDecision(False, "web_egress_blocked", detail, rule=rule.raw)

    for rule in rules:
        if rule.matches_host(target):
            refused = hit(rule, target)
            if refused is not None:
                return refused

    literal = literal_address(target)
    if literal is not None:
        for rule in rules:
            if rule.matches_address(literal):
                refused = hit(rule, target)
                if refused is not None:
                    return refused

    addresses = resolve_public_addresses(target, port)
    if not addresses:
        # DEC-21 — "resolves to a private address" was said of a name that
        # does not resolve at all, sending the owner to look for a network
        # they do not have. Both are refused; only the reason differs.
        if literal is None and not resolves_at_all(target, port):
            proxy = (
                web_proxy_for(scheme, target, None if port in (80, 443) else port)
                if allow_proxy and public_shaped_name(target)
                else ""
            )
            if proxy:
                # SSRF (owner's decision, 2026-10-26): the proxy would resolve
                # the name itself, out of Raiker's sight. The name is looked up
                # through the proxy first and the address guard applied to every
                # answer; a lookup that cannot be made refuses the read.
                looked_up = resolve_via_proxy(target, proxy)
                if looked_up is None:
                    return EgressDecision(False, "web_host_unverified", target, flagged=tuple(flagged))
                if not looked_up:
                    return EgressDecision(False, "web_host_unresolved", target, flagged=tuple(flagged))
                if not all(address_is_reachable(ipaddress.ip_address(item)) for item in looked_up):
                    return EgressDecision(False, "web_host_not_public", target, flagged=tuple(flagged))
                return EgressDecision(
                    True, addresses=tuple(looked_up), flagged=tuple(flagged), route="proxy", proxy=proxy
                )
            return EgressDecision(False, "web_host_unresolved", target, flagged=tuple(flagged))
        return EgressDecision(False, "web_host_not_public", target, flagged=tuple(flagged))

    for address in addresses:
        parsed = ipaddress.ip_address(address)
        for rule in rules:
            if rule.matches_address(parsed):
                refused = hit(rule, f"{target} ({address})")
                if refused is not None:
                    return refused

    return EgressDecision(True, addresses=tuple(addresses), flagged=tuple(flagged))


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
        "web_host_unverified": (
            "Web access denied: this machine reaches the web through a proxy, and the "
            "name could not be looked up through it to check where it leads. Raiker "
            "does not read a page it cannot check (RAIKER_WEB_DOH_ENDPOINT sets the lookup)."
        ),
        "web_host_unresolved": (
            "Web access denied: that name does not resolve to any address from this "
            "machine. Check the spelling, or whether this machine can look names up."
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


def pinned_http_opener(address: str) -> Any:
    """A urllib opener that dials *address* for a plain-http read (TOOL-91).

    The Host header keeps the name; only the dialled address is pinned, for the
    same rebinding reason as :func:`pinned_https_opener`. Plain http is read
    only because the owner decided web reads should not refuse a URL; the read
    carries an alert that it was not encrypted.
    """
    import http.client
    import urllib.request

    class _PinnedHTTPConnection(http.client.HTTPConnection):
        def connect(self) -> None:
            import socket as _socket

            self.sock = _socket.create_connection((address, self.port or 80), self.timeout)

    class _PinnedHTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req: Any) -> Any:
            return self.do_open(_PinnedHTTPConnection, req)

    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _PinnedHTTPHandler())


def pinned_https_opener(host: str, address: str, *, direct: bool = False) -> Any:
    """A urllib opener that dials *address* but speaks TLS as *host*.

    ``direct`` leaves the process's proxy settings out of the opener. A pinned
    connection dials the destination itself, so a proxy handler beside it would
    ask the destination to tunnel to itself; a caller that has already decided
    no proxy applies says so here.
    """
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

    if direct:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), _PinnedHandler)
    return urllib.request.build_opener(_PinnedHandler)
