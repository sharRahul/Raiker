from __future__ import annotations

import json
import os
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler

from raiker.runtime.authority.decision_modes import (
    DEFAULT_DECISION_MODE,
    DecisionMode,
    parse_decision_mode,
)
from raiker.runtime.executors.sandbox import SandboxError
from raiker.runtime.web_policy import (
    BlocklistRule,
    EgressDecision,
    evaluate_host,
    load_blocklist,
    pinned_https_opener,
    refusal_message,
)
from raiker.runtime.web_sanitize import as_model_content, sanitize_html, sanitize_text

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# ── Governed web access for the agent (GAP-BUILD B12 / GAP-CHAT C7) ───────────
#
# Until now nothing in the tool surface could read a page, so a model asked to
# use a library could not read that library's documentation — it could only
# guess from training. This is the read that closes that, and it is governed
# exactly like the service connectors next to it, for the same reason: it is
# network egress, and the destination is chosen by a *model*.
#
# Enforced here, in order, on every call:
#
#   1. the ``web_fetch`` capability gate (disabled ⇒ fail closed);
#   2. the per-capability decision mode (**default ``ask`` ⇒ withheld**;
#      ``deny`` ⇒ blocked; ``auto`` withholds too — reaching the open internet
#      on a model's say-so is never low-risk);
#   3. the owner blocklist ``RAIKER_WEB_EGRESS_BLACKLIST`` plus the rules stored
#      in the app — the owner's own policy about *public* destinations, which is
#      empty by default because a reachable web read is the point of the feature;
#   4. the address guard: HTTPS only, no embedded credentials, and every address
#      the name resolves to must be public. This one is **not** owner-editable
#      and has no allow path — it is what stops a page fetch reaching the
#      loopback interface, the home network, or a cloud metadata service;
#   5. every redirect hop re-checked against 3 and 4, because a redirect is a
#      second destination nobody decided on; and the connection pinned to an
#      address that already passed, so the name cannot change under the check.
#
# What comes back is *untrusted data, never instructions* — the same framing the
# connectors use — reduced to text, bounded, and labelled as such.

_CAP = "web_fetch"
_ENABLED_GATE_STATES = frozenset({"enabled_read_only", "enabled_policy_gated", "enabled_runtime"})

# Reaching the open internet carries the owner's IP and the request itself
# off-machine → not low-risk, exactly like the connector reads.
_READ_RISK = "medium"

MAX_FETCH_BYTES = 400_000
MAX_CONTENT_CHARS = 20_000
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 15.0

SEARCH_ENDPOINT_ENV = "RAIKER_WEB_SEARCH_ENDPOINT"
#: The endpoint used when the owner has configured none. It needs no account and
#: no key, which is the whole point: `web_search` reporting
#: `web_search_not_configured` on a fresh install made the tool advertised and
#: unusable. Setting `RAIKER_WEB_SEARCH_ENDPOINT` replaces it, and the result of
#: either is untrusted data that still answers to the blocklist and the address
#: guard.
DEFAULT_SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
SEARCH_KEY_ENV = "RAIKER_WEB_SEARCH_KEY"
SEARCH_KEY_HEADER_ENV = "RAIKER_WEB_SEARCH_KEY_HEADER"
MAX_SEARCH_RESULTS = 10


def _denied(
    reason: str, message: str, *, remediation_route: str | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"type": reason, "message": message}
    if remediation_route is not None:
        error["remediation_route"] = remediation_route
    return {"status": "denied", "error": error}


def _failed(reason: str, message: str) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": reason, "message": message}}


def _scoped_record(
    store: SQLiteStore, principal_id: str | None, capability: str
) -> dict[str, Any] | None:
    if principal_id and store.get_account(principal_id) is not None:
        return store.get_principal_capability_gate_state(principal_id, capability)
    return store.get_capability_gate_state(capability)


def _scoped_mode(store: SQLiteStore, principal_id: str | None, capability: str) -> str | None:
    if principal_id and store.get_account(principal_id) is not None:
        return store.get_principal_capability_decision_mode(principal_id, capability)
    return store.get_capability_decision_mode(capability)


class _TextExtractor(HTMLParser):
    """Reduce an HTML document to readable text.

    Script, style and template bodies are dropped rather than flattened: their
    contents are code, and a model reading a page should be given the page's
    prose, not the site's JavaScript. Block-level tags become line breaks so the
    result keeps the document's shape.
    """

    _DROP = frozenset({"script", "style", "template", "noscript", "svg"})
    _BREAK = frozenset({
        "p", "br", "div", "section", "article", "header", "footer", "li", "tr",
        "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._suppress = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._DROP:
            self._suppress += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BREAK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._DROP:
            self._suppress = max(0, self._suppress - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self._BREAK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._suppress:
            return
        if self._in_title:
            self.title += data.strip()
            return
        self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        lines = [" ".join(line.split()) for line in joined.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(body: str) -> tuple[str, str]:
    """``(title, text)`` for an HTML document.

    Kept as the name other modules already import; the work now happens in
    :mod:`raiker.runtime.web_sanitize`, so every caller gets the same hidden-text
    and invisible-character handling rather than the older tag-stripping.
    """
    page = sanitize_html(body)
    return page.title, page.text


def check_url(url: str, rules: tuple[BlocklistRule, ...]) -> EgressDecision:
    """Decide one URL: shape first, then the owner's rules, then the address guard."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return EgressDecision(False, "web_url_not_https")
    if parsed.username or parsed.password:
        return EgressDecision(False, "web_url_credentials")
    hostname = (parsed.hostname or "").strip()
    if not parsed.netloc or not hostname:
        return EgressDecision(False, "web_url_invalid")
    return evaluate_host(hostname, rules, port=parsed.port or 443)


def _fetch(
    url: str, rules: tuple[BlocklistRule, ...], headers: dict[str, str]
) -> dict[str, Any]:
    """One bounded HTTPS GET whose every redirect hop is re-governed.

    Redirects are followed by hand rather than by urllib's handler so each new
    destination goes back through :func:`check_url`. A redirect is a second
    destination, and nothing decided on that one.
    """
    import urllib.error
    import urllib.request
    from urllib.parse import urljoin

    current = url
    for _ in range(MAX_REDIRECTS + 1):
        decision = check_url(current, rules)
        if not decision.allowed:
            raise SandboxError(decision.reason_code)
        host = urlparse(current).hostname or ""
        # Dial an address that passed the guard, speak TLS as the name. Handing
        # urllib the *name* would re-resolve it, and the second answer does not
        # have to match the one that was checked.
        opener = pinned_https_opener(host, decision.addresses[0])
        opener.add_handler(_NoRedirect())
        request = urllib.request.Request(  # noqa: S310 — https verified in check_url
            current, method="GET", headers=headers
        )
        try:
            with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200) or 200)
                data = response.read(MAX_FETCH_BYTES + 1)
                charset = response.headers.get_content_charset() or "utf-8"
                content_type = (response.headers.get_content_type() or "").lower()
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location", "") if exc.headers else ""
                if not location:
                    raise SandboxError("web_redirect_without_location") from None
                current = urljoin(current, location)
                continue
            raise SandboxError(f"web_http_error:{exc.code}") from None
        except SandboxError:
            raise
        except Exception as exc:  # noqa: BLE001 — every transport failure fails closed
            raise SandboxError(f"web_fetch_failed:{type(exc).__name__}") from None
        truncated = len(data) > MAX_FETCH_BYTES
        body = data[:MAX_FETCH_BYTES].decode(charset, errors="replace")
        return {
            "final_url": current,
            "status": status,
            "content_type": content_type,
            "body": body,
            "truncated": truncated,
        }
    raise SandboxError("web_too_many_redirects")


class _NoRedirect(HTTPRedirectHandler):
    """Stop urllib following a redirect so each hop can be re-governed.

    Returning ``None`` from ``redirect_request`` makes urllib raise the 3xx as an
    ``HTTPError``, which :func:`_fetch` catches and re-checks. Without this, one
    checked URL could redirect the agent anywhere.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]  # noqa: ANN001
        return None


class WebAccessService:
    """Governed, **default-ask** web reads for the agent.

    ``fetch()`` returns one page as bounded text for the calling model.
    ``search()`` is the same capability pointed at a search endpoint: the
    owner's if they configured one, otherwise a keyless default, so the tool
    works on a fresh install instead of advertising itself and refusing.
    """

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        principal_id: str | None = None,
        fetch_fn: Any = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._principal_id = principal_id
        self._fetch_fn = fetch_fn

    def _blocklist(self) -> tuple[BlocklistRule, ...]:
        """Every rule in force for this caller: built-in, env, and stored."""
        return load_blocklist(self._store, self._principal_id)

    # ── governance layers ────────────────────────────────────────────────
    def _gate_enabled(self) -> bool:
        try:
            record = _scoped_record(self._store, self._principal_id, _CAP)
        except Exception:  # noqa: BLE001 — a broken read fails closed
            return False
        if not record:
            return False
        return str(record.get("state", "")) in _ENABLED_GATE_STATES

    def _mode(self) -> DecisionMode:
        persisted = _scoped_mode(self._store, self._principal_id, _CAP)
        mode = parse_decision_mode(persisted) if persisted else None
        return mode or DEFAULT_DECISION_MODE

    def _governance_refusal(self, what: str) -> dict[str, Any] | None:
        if not self._gate_enabled():
            return _denied(
                "web_gate_disabled",
                f"{what} denied: the web_fetch capability gate is disabled (fail closed). "
                "Enable it from Permissions.",
                remediation_route="capabilities",
            )
        mode = self._mode()
        if mode == DecisionMode.DENY:
            return _denied(
                "web_denied_by_decision_mode",
                f"{what} denied by the owner's decision mode for web_fetch.",
                remediation_route="capabilities",
            )
        # `ask` and `auto` no longer withhold. They did while egress was an
        # allowlist the owner had to fill in by hand: reaching *anywhere* was the
        # escalation, so withholding was the honest default. What a fetch can now
        # reach is bounded by a guard the owner cannot switch off — no private
        # address, no credential in the URL, no plaintext scheme, every redirect
        # re-checked — which puts it in the same band as the connector reads
        # beside it. `deny` still denies, and the blocklist still blocks.
        return None

    # ── fetch ────────────────────────────────────────────────────────────
    def fetch(self, url: str, *, enforce_modes: bool = True) -> dict[str, Any]:
        """Read one page and return it as bounded, untrusted text."""
        url = (url or "").strip()
        if not url:
            return _failed("missing_argument:url", "web_fetch needs a url.")
        if enforce_modes:
            refusal = self._governance_refusal("Web fetch")
            if refusal is not None:
                return refusal
        rules = self._blocklist()
        decision = check_url(url, rules)
        if not decision.allowed:
            return _denied(decision.reason_code, refusal_message(decision.reason_code))
        fetch_fn = self._fetch_fn or _fetch
        try:
            fetched = fetch_fn(url, rules, {"User-Agent": "raiker-web-fetch", "Accept": "text/html,text/plain"})
        except SandboxError as exc:
            return _denied(str(exc), "Web fetch failed closed.")
        except Exception:  # noqa: BLE001 — every transport failure fails closed
            return _denied("web_fetch_failed", "Web fetch failed closed.")

        body = str(fetched.get("body", ""))
        content_type = str(fetched.get("content_type", ""))
        final_url = str(fetched.get("final_url", url))
        # The page becomes text *here*, before it goes anywhere near a context
        # window: markup dropped, invisible characters removed, elements a
        # visitor could never see discarded, and anything shaped like a
        # conversation role marker defanged.
        if "html" in content_type or body.lstrip()[:1] == "<":
            page = sanitize_html(body, max_chars=MAX_CONTENT_CHARS)
        else:
            page = sanitize_text(body, max_chars=MAX_CONTENT_CHARS)
        return {
            "status": "success",
            "url": url,
            "final_url": final_url,
            "title": page.title,
            "untrusted": True,
            "content": as_model_content(page, source=final_url),
            "content_length": len(page.text),
            "content_truncated": bool(fetched.get("truncated")) or page.truncated,
            "sanitiser": {
                "hidden_blocks_removed": page.hidden_blocks_removed,
                "invisible_characters_removed": page.invisible_characters_removed,
                "role_markers_defanged": page.role_markers_defanged,
                "suspicious": page.suspicious,
                "notes": list(page.notes),
            },
        }

    # ── search ───────────────────────────────────────────────────────────
    @staticmethod
    def search_configured() -> bool:
        return bool(os.environ.get(SEARCH_ENDPOINT_ENV, "").strip())

    def search(
        self, query: str, *, max_results: int = 5, enforce_modes: bool = True
    ) -> dict[str, Any]:
        """Run one query against the owner-configured search endpoint."""
        query = (query or "").strip()
        if not query:
            return _failed("missing_argument:query", "web_search needs a query.")
        if enforce_modes:
            refusal = self._governance_refusal("Web search")
            if refusal is not None:
                return refusal
        endpoint = os.environ.get(SEARCH_ENDPOINT_ENV, "").strip() or DEFAULT_SEARCH_ENDPOINT
        rules = self._blocklist()
        target = f"{endpoint}{'&' if '?' in endpoint else '?'}q={quote(query)}"
        decision = check_url(target, rules)
        if not decision.allowed:
            return _denied(decision.reason_code, refusal_message(decision.reason_code))
        headers = {"User-Agent": "raiker-web-search", "Accept": "application/json"}
        key = os.environ.get(SEARCH_KEY_ENV, "").strip()
        if key:
            headers[os.environ.get(SEARCH_KEY_HEADER_ENV, "").strip() or "Authorization"] = (
                key if os.environ.get(SEARCH_KEY_HEADER_ENV, "").strip() else f"Bearer {key}"
            )
        fetch_fn = self._fetch_fn or _fetch
        try:
            fetched = fetch_fn(target, rules, headers)
        except SandboxError as exc:
            return _denied(str(exc), "Web search failed closed.")
        except Exception:  # noqa: BLE001
            return _denied("web_search_failed", "Web search failed closed.")
        body = str(fetched.get("body", ""))
        try:
            results = _search_results(json.loads(body))
        except ValueError:
            # The zero-configuration endpoint answers in HTML, not JSON. Falling
            # back rather than failing is what lets search work with nothing
            # configured, while a configured JSON endpoint still takes the path
            # above.
            results = _html_search_results(body)
        if not results:
            return _failed(
                "web_search_bad_response",
                "The search endpoint returned nothing this build could read as results.",
            )
        results = results[: max(1, min(int(max_results or 5), MAX_SEARCH_RESULTS))]
        return {
            "status": "success",
            "query": query,
            "untrusted": True,
            "result_count": len(results),
            "results": results,
            "endpoint_configured": bool(os.environ.get(SEARCH_ENDPOINT_ENV, "").strip()),
            "content": as_model_content(
                sanitize_text(
                    "\n".join(f"- {r['title']} — {r['url']}\n  {r['snippet']}" for r in results)
                ),
                source="a web search for " + query,
            ),
        }


def _url_refusal_message(reason: str) -> str:
    if reason == "web_url_not_https":
        return "Web access denied: only https URLs may be fetched."
    if reason == "web_url_invalid":
        return "Web access denied: that is not a fetchable URL."
    if reason.startswith("web_host_not_public"):
        return (
            "Web access denied: that host resolves to a private or loopback address, "
            "which the agent may never reach."
        )
    return "Web access denied."


def _html_search_results(body: str) -> list[dict[str, str]]:
    """Results from an HTML search page, when the endpoint speaks HTML not JSON.

    Deliberately small: anchors that carry a result URL, in document order, with
    the anchor text as the title. It is not a general scraper and does not try to
    be — a search page that changes shape yields fewer results rather than wrong
    ones, and everything it does yield is sanitised like any other page text.
    """
    import html as _html
    import re as _re
    from urllib.parse import parse_qs, unquote
    from urllib.parse import urlparse as _urlparse

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _re.finditer(
        r'<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>', body, _re.IGNORECASE | _re.DOTALL
    ):
        href = _html.unescape(match.group(1))
        # Result links on these pages are commonly wrapped in a redirector that
        # carries the real destination in a query parameter.
        if href.startswith("//"):
            href = "https:" + href
        parsed = _urlparse(href)
        if parsed.path.rstrip("/").endswith("/l") or "uddg" in (parsed.query or ""):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                href = unquote(target)
                parsed = _urlparse(href)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        title = sanitize_text(match.group(2), max_chars=200).text
        if not title or href in seen:
            continue
        seen.add(href)
        rows.append({"title": title[:200], "url": href[:500], "snippet": ""})
        if len(rows) >= MAX_SEARCH_RESULTS * 3:
            break
    return rows


def _search_results(payload: Any) -> list[dict[str, str]]:
    """Normalise the common search-response shapes into title/url/snippet rows."""
    rows: Any = None
    if isinstance(payload, dict):
        for key in ("results", "items", "data"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        if rows is None and isinstance(payload.get("web"), dict):
            candidate = payload["web"].get("results")
            if isinstance(candidate, list):
                rows = candidate
    elif isinstance(payload, list):
        rows = payload
    if not isinstance(rows, list):
        return []
    normalised: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or row.get("link") or "").strip()
        if not url:
            continue
        normalised.append({
            "title": str(row.get("title") or row.get("name") or url).strip()[:200],
            "url": url[:500],
            "snippet": str(
                row.get("snippet") or row.get("description") or row.get("content") or ""
            ).strip()[:500],
        })
    return normalised
