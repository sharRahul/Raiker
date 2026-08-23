from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def web_fetch(
    workspace_root: str | Path,
    url: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Read one web page, brokered as the ``web_fetch`` tool (B12 / C7).

    Everything is enforced inside :class:`WebAccessService`: the ``web_fetch``
    capability gate (fail closed), the decision mode (default ``ask``
    withholds), the owner blocklist (``RAIKER_WEB_EGRESS_BLACKLIST`` plus the
    rules stored in Settings → Web access), HTTPS-only model-supplied URLs, a
    public-address check, and a re-governed check on every redirect hop. The
    page comes back as an untrusted-data block; broker events drop the content.

    The blocklist replaced an allowlist (``RAIKER_WEB_EGRESS_ALLOWLIST``) that
    shipped empty; see :mod:`raiker.runtime.web_policy` for why. The
    address guard is not part of that trade — it is not optional and emptying
    the blocklist does not open it.
    """
    # Imported at call time for the same reason the connector tools are: the
    # runtime.authority package this pulls in transitively imports the broker.
    from raiker.runtime.web_access import WebAccessService
    from raiker.storage.sqlite import SQLiteStore

    service = WebAccessService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.fetch(url)


def web_search(
    workspace_root: str | Path,
    query: str,
    max_results: Any = 5,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Search the web through the owner-configured endpoint (B12 / C7).

    Same gate, decision mode and egress allowlist as :func:`web_fetch`, and
    **off unless the owner configures a provider**: Raiker ships no search
    endpoint, so an unconfigured host refuses with that exact reason rather
    than reaching somebody's API on the owner's behalf.
    """
    from raiker.runtime.web_access import WebAccessService
    from raiker.storage.sqlite import SQLiteStore

    try:
        limit = int(max_results)
    except (TypeError, ValueError):
        limit = 5
    service = WebAccessService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.search(query, max_results=limit)
