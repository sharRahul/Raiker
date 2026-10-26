"""Which sites a web read flags, and which it never does (owner's decision, 2026-10-26).

A flag is an alert on a web read, never a refusal (2026-10-25). Since the
owner's decision of 2026-10-26 it means one thing: the site, or the exact page,
is **registered on the internet as malicious** by a public threat feed. Two
things follow:

* **Known and authenticated sites are never flagged.** A site the owner signs
  in to so Raiker can act for them (GitHub, Google, Slack and the other
  connectors), a forge Raiker pushes to, a model provider, and a short list of
  widely used sites are *trusted*: no owner rule, environment rule or feed
  entry for the site as a whole raises an alert on them, and Settings refuses
  to flag one. A feed entry for one exact page on such a site (a phishing page
  hosted on a site-builder, say) still alerts, naming the page and not the site.
* **The feeds are the source.** `URLhaus` lists hosts that distribute malware
  and `OpenPhish` lists phishing pages. Both are free, keyless and public. They
  are downloaded to the workspace and refreshed when stale, and a read is
  matched locally: the URL never leaves the machine to be checked.

None of this is the SSRF guard. Reaching the owner's own network is refused by
the address guard in :mod:`raiker.runtime.web_policy` whatever any list says.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

#: Widely used sites, and the platforms people sign in to so Raiker can act for
#: them. A domain here covers its subdomains. Kept short and named on purpose:
#: this is "never flag the site as a whole", not "trust what is on it".
KNOWN_SITES: tuple[str, ...] = (
    "github.com", "githubusercontent.com", "github.io", "gitlab.com", "bitbucket.org",
    "google.com", "googleapis.com", "gmail.com", "youtube.com", "gstatic.com",
    "microsoft.com", "live.com", "office.com", "outlook.com", "azure.com", "bing.com",
    "apple.com", "icloud.com", "amazon.com", "amazonaws.com",
    "slack.com", "notion.so", "atlassian.com", "linear.app", "figma.com", "canva.com",
    "dropbox.com", "zoom.us", "linkedin.com", "salesforce.com", "hubspot.com",
    "stripe.com", "paypal.com", "anthropic.com", "claude.ai", "openai.com",
    "huggingface.co", "wikipedia.org", "stackoverflow.com", "python.org", "pypi.org",
    "npmjs.com", "mozilla.org", "cloudflare.com", "docker.com", "duckduckgo.com",
)


@dataclass(frozen=True)
class Feed:
    id: str
    name: str
    url: str
    #: ``hosts``: one malicious host per line (hosts-file form allowed);
    #: ``urls``: one malicious page per line.
    kind: str
    what: str


FEEDS: tuple[Feed, ...] = (
    Feed("urlhaus", "URLhaus (abuse.ch)", "https://urlhaus.abuse.ch/downloads/hostfile/", "hosts",
         "hosts that distribute malware"),
    Feed("openphish", "OpenPhish community feed", "https://openphish.com/feed.txt", "urls",
         "phishing pages"),
)

#: A feed older than this is refreshed the next time it is asked for.
STALE_AFTER_SECONDS = 24 * 3600
#: The most of one feed that is read or kept.
MAX_FEED_BYTES = 25_000_000
MAX_FEED_ENTRIES = 600_000
_DISABLE_ENV = "RAIKER_THREAT_FEEDS"


def _host_of(value: str) -> str:
    return (value or "").strip().lower().rstrip(".")


def _covers(domain: str, host: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _parent(host: str) -> str:
    labels = host.split(".")
    return ".".join(labels[1:]) if len(labels) > 2 else host


def authenticated_sites() -> tuple[str, ...]:
    """The hosts Raiker signs in to for the owner: its connectors and forges."""
    found: set[str] = set()
    try:
        from raiker.runtime.connector_ecosystem import ConnectorCatalog

        for definition in ConnectorCatalog().list():
            host = _host_of(definition.host)
            if host:
                found.update({host, _parent(host)})
    except Exception:  # noqa: BLE001 — a missing catalogue only shortens the list
        pass
    from raiker.github.hosts import SSH_TRANSPORT_HOSTS
    from raiker.runtime.git_credential import CREDENTIAL_HOSTS

    found.update(_host_of(host) for host in CREDENTIAL_HOSTS)
    found.update(_host_of(host) for host in SSH_TRANSPORT_HOSTS)
    found.update({"api.github.com", "github.com"})
    return tuple(sorted(item for item in found if "." in item))


def trusted_domain(host: str) -> str:
    """The known or authenticated domain covering *host*, or ``""``."""
    target = _host_of(host)
    if not target:
        return ""
    for domain in (*KNOWN_SITES, *authenticated_sites()):
        if _covers(domain, target):
            return domain
    return ""


def _normalise_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = _host_of(parsed.hostname or "")
    if not host:
        return ""
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{host}{path}{query}".rstrip("/")


def parse_feed(kind: str, text: str) -> list[str]:
    """One feed's entries: hosts, or normalised page addresses."""
    entries: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if kind == "hosts":
            parts = line.split()
            host = _host_of(parts[-1])
            if "." in host and host not in ("localhost", "localhost.localdomain"):
                entries.append(host)
        else:
            normalised = _normalise_url(line)
            if normalised:
                entries.append(normalised)
        if len(entries) >= MAX_FEED_ENTRIES:
            break
    return entries


class ThreatFeeds:
    """The downloaded feeds of one workspace, matched locally."""

    _cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _lock = threading.Lock()

    def __init__(self, workspace_root: str | Path) -> None:
        self.root = Path(workspace_root) / ".raiker" / "threat_feeds"

    def _path(self, feed: Feed) -> Path:
        return self.root / f"{feed.id}.json"

    def _load(self, feed: Feed) -> dict[str, Any]:
        path = self._path(feed)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {"entries": [], "fetched_at": None}
        key = str(path)
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] == mtime:
                return cached[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"entries": [], "fetched_at": None}
        data["_set"] = frozenset(data.get("entries") or [])
        with self._lock:
            self._cache[key] = (mtime, data)
        return data

    def save(self, feed: Feed, entries: list[str], *, error: str = "") -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        previous = self._load(feed)
        payload = {
            "feed": feed.id,
            "entries": entries if not error else list(previous.get("entries") or []),
            "fetched_at": time.time() if not error else previous.get("fetched_at"),
            "last_error": error,
            "checked_at": time.time(),
        }
        tmp = self._path(feed).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self._path(feed))

    def status(self) -> list[dict[str, Any]]:
        out = []
        for feed in FEEDS:
            data = self._load(feed)
            out.append({
                "id": feed.id, "name": feed.name, "what": feed.what, "url": feed.url,
                "entries": len(data.get("entries") or []),
                "fetched_at": data.get("fetched_at"),
                "last_error": str(data.get("last_error") or ""),
            })
        return out

    def stale(self) -> bool:
        now = time.time()
        return any(
            not item["fetched_at"] or now - float(item["fetched_at"]) > STALE_AFTER_SECONDS
            for item in self.status()
        )

    def refresh(self, fetch: Any = None) -> list[dict[str, Any]]:
        """Download every feed once; a feed that fails keeps what it had."""
        if fetch is None:
            from raiker.runtime.executors.sandbox import get_url

            def fetch(feed: Feed) -> str:
                host = urlparse(feed.url).netloc
                answer = get_url(feed.url, egress_allowlist=frozenset({host}),
                                 max_bytes=MAX_FEED_BYTES, timeout=30.0)
                return str(answer.get("body_text", ""))
        for feed in FEEDS:
            try:
                self.save(feed, parse_feed(feed.kind, fetch(feed)))
            except Exception as exc:  # noqa: BLE001 — a feed that cannot be read keeps what it had
                self.save(feed, [], error=str(exc)[:200] or type(exc).__name__)
        return self.status()

    def matches(self, url: str) -> list[dict[str, str]]:
        """The feeds that register *url*'s host or exact page as malicious."""
        parsed = urlparse(url)
        host = _host_of(parsed.hostname or "")
        if not host:
            return []
        page = _normalise_url(url)
        found: list[dict[str, str]] = []
        for feed in FEEDS:
            entries = self._load(feed).get("_set") or frozenset()
            if not entries:
                continue
            if feed.kind == "hosts" and host in entries:
                found.append({"feed": feed.name, "what": feed.what, "scope": "site"})
            elif feed.kind == "urls" and page in entries:
                found.append({"feed": feed.name, "what": feed.what, "scope": "page"})
        return found


def refresh_in_background(workspace_root: str | Path) -> threading.Thread | None:
    """Refresh stale feeds off the request path; ``None`` when there is nothing to do."""
    if os.environ.get(_DISABLE_ENV, "").strip().lower() in ("off", "0", "false"):
        return None
    feeds = ThreatFeeds(workspace_root)
    if not feeds.stale():
        return None
    thread = threading.Thread(target=feeds.refresh, name="raiker-threat-feeds", daemon=True)
    thread.start()
    return thread


@dataclass(frozen=True)
class SiteReputation:
    """What a web read consults: the trusted sites and the feeds."""

    workspace_root: str | Path

    def trusted(self, host: str) -> str:
        return trusted_domain(host)

    def malicious(self, url: str) -> list[dict[str, str]]:
        found = ThreatFeeds(self.workspace_root).matches(url)
        host = _host_of(urlparse(url).hostname or "")
        if trusted_domain(host):
            # A known site is never flagged as a whole; one registered page on it is.
            found = [item for item in found if item["scope"] == "page"]
        return found
