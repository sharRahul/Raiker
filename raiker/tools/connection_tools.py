"""TOOL-72 / TOOL-126 — the model suggests a connection; the owner makes it.

A turn that needs a service the owner has not connected used to say so in
prose. This tool names the service from Raiker's own catalogue and hands back
where the owner connects it, so the conversation can draw an **Add connection**
card. It connects nothing, stores nothing and reaches nothing: connecting is a
dialog the owner opens, and a connection still grants nothing until
Permissions allows it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

MAX_REASON_CHARS = 200


def _connected(store: SQLiteStore | None, principal_id: str | None, connector_id: str) -> bool:
    if store is None or not principal_id:
        return False
    with store.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM connector_credentials WHERE principal_id=? AND connector_id=?",
            (principal_id, connector_id),
        ).fetchone()
    return row is not None


def suggest_connection(
    service: str,
    reason: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """The catalogue entry for *service*, and where the owner connects it."""
    from raiker.runtime.connector_ecosystem import ConnectorCatalog

    wanted = " ".join((service or "").lower().split())
    why = " ".join((reason or "").split())
    if not wanted:
        return {"status": "failed", "error": {"type": "missing_argument:service"}}
    if not why:
        return {"status": "failed", "error": {"type": "missing_argument:reason"}}
    catalogue = list(ConnectorCatalog().list())
    match = next(
        (d for d in catalogue if wanted in (d.connector_id.lower(), d.name.lower())), None
    ) or next((d for d in catalogue if wanted in d.name.lower() or d.name.lower() in wanted), None)
    if match is None:
        return {
            "status": "failed",
            "error": {
                "type": "unknown_service",
                "services": sorted(d.name for d in catalogue),
                "hint": "An MCP server can connect a service this list does not name.",
            },
        }
    connected = _connected(store, principal_id, match.connector_id)
    return {
        "status": "success",
        "connector_id": match.connector_id,
        "service": match.name,
        "reason": why[:MAX_REASON_CHARS],
        "connected": connected,
        "href": f"#/connections?add={match.connector_id}",
        "content": (
            f"{match.name} is already connected."
            if connected
            else f"Offered the owner a card to connect {match.name}. Nothing is connected until they do it."
        ),
    }
