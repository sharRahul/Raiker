"""QUI-F15 — everything Raiker has made, in one owner-scoped read.

The Library is a read over records that already exist, plus the pins an owner
made from an answer's block toolbar:

* **document** — a file a Chat turn generated (``session_attachment_refs`` with
  ``source = 'generated'``), downloadable from its conversation;
* **image** — a picture Design made, not deleted;
* **design** — a Design document, not deleted;
* **block** — a pinned answer block (a chart, a comparison, key figures…);
* **pull_request** — a pull request Build opened.

Nothing is copied into a second store except the pinned blocks, so an item
deleted where it lives is gone from the Library too. Every item names where it
came from (``href``), and a conversation another account owns is never read:
each query is bounded by the owner, and a session row is only joined when it is
this account's or unattributed, the same rule the conversation list applies.
"""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

from raiker.storage.sqlite import SQLiteStore

LibraryKind = Literal["document", "image", "design", "block", "pull_request"]
LIBRARY_KINDS: tuple[str, ...] = ("document", "image", "design", "block", "pull_request")

#: The most items one read returns. The page filters and pages within it.
MAX_ITEMS = 300

_BLOCK_NAMES = {
    "table": "Table",
    "chart": "Chart",
    "figures": "Key figures",
    "compare": "Comparison",
    "measure": "Measure",
    "callout": "Callout",
    "proscons": "Pros and cons",
    "steps": "Steps",
}

_DOCUMENT_NAMES = {
    "application/pdf": "PDF",
    "text/markdown": "Markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Spreadsheet",
}


class LibraryItem(TypedDict):
    item_id: str
    kind: LibraryKind
    title: str
    #: One short line under the title: the type of file or block.
    detail: str
    created_at: str
    project_id: str | None
    project_name: str | None
    #: The conversation it came from, when it came from one.
    session_id: str | None
    session_title: str | None
    turn_id: str | None
    #: Where it opens: its conversation, Design, or the pull request's page.
    href: str
    #: True when ``href`` leaves Raiker (a pull request on GitHub).
    external: bool
    download_url: str | None
    #: A pinned block's validated data, so the page can draw it; empty otherwise.
    block: dict[str, Any] | None
    pin_id: str | None


def block_title(part_type: str, data: dict[str, Any]) -> str:
    """The name a pinned block goes by: its caption, else what it is about.

    A block with no caption is named from its own contents ("Revenue, Costs,
    Profit") rather than by its kind, which the row already says beside it.
    """
    for key in ("caption", "label", "title"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    names: list[str] = []
    if part_type == "figures":
        names = [str(item.get("label", "")) for item in data.get("items") or [] if isinstance(item, dict)]
    elif part_type == "compare":
        names = [str(item) for item in data.get("items") or []]
    elif part_type == "table":
        names = [str(column) for column in data.get("columns") or []]
    elif part_type == "chart":
        names = [str(series.get("name", "")) for series in data.get("series") or [] if isinstance(series, dict)]
    elif part_type == "proscons":
        names = [str(option.get("name", "")) for option in data.get("options") or [] if isinstance(option, dict)]
    elif part_type == "steps":
        names = [str(step.get("label", "")) for step in data.get("steps") or [] if isinstance(step, dict)]
    elif part_type == "callout":
        text = " ".join(str(data.get("text") or "").split())
        names = [text[:80] + ("…" if len(text) > 80 else "")] if text else []
    joined = ", ".join(name.strip() for name in names if name.strip())
    if joined:
        return joined if len(joined) <= 120 else joined[:119].rstrip() + "…"
    return _BLOCK_NAMES.get(part_type, "Answer block")


def _conversation_link(session_id: str, turn_id: str | None = None) -> str:
    link = f"#/new-chat?session={session_id}"
    return f"{link}&turn={turn_id}" if turn_id else link


def _size(byte_size: int) -> str:
    if byte_size < 1024:
        return f"{byte_size} B"
    if byte_size < 1024 * 1024:
        return f"{round(byte_size / 1024)} KB"
    return f"{byte_size / (1024 * 1024):.1f} MB"


def library_items(
    store: SQLiteStore,
    *,
    owner_principal_id: str,
    user_id: str | None,
    project_id: str | None = None,
    kind: str | None = None,
) -> list[LibraryItem]:
    """The owner's Library, newest first, optionally one project's or one kind's."""
    if not owner_principal_id:
        return []
    projects = {
        str(row["project_id"]): str(row["name"])
        for row in store._rows(
            # A NULL account (the unattributed single-owner workspace) reads them all.
            "SELECT project_id, name FROM projects WHERE ? IS NULL OR owner_user_id = ? OR owner_user_id IS NULL",
            (user_id, user_id),
        )
    }
    sessions = _sessions(store, user_id)
    items: list[LibraryItem] = []
    wanted = {kind} if kind in LIBRARY_KINDS else set(LIBRARY_KINDS)

    def project_of(value: Any) -> tuple[str | None, str | None]:
        pid = str(value) if value else None
        return (pid, projects[pid]) if pid in projects else (None, None)

    if "document" in wanted:
        for row in store._rows(
            """
            SELECT r.attachment_id, r.session_id, r.turn_id, r.created_at,
                   a.filename, a.media_type, a.byte_size
            FROM session_attachment_refs r JOIN attachments a ON a.attachment_id = r.attachment_id
            WHERE r.owner_principal_id = ? AND r.source = 'generated'
            ORDER BY r.created_at DESC LIMIT ?
            """,
            (owner_principal_id, MAX_ITEMS),
        ):
            session = sessions.get(str(row["session_id"]))
            if session is None:
                continue
            pid, pname = project_of(session["project_id"])
            items.append({
                "item_id": f"document:{row['attachment_id']}",
                "kind": "document",
                "title": str(row["filename"]),
                "detail": f"{_DOCUMENT_NAMES.get(str(row['media_type']), 'Document')} · {_size(int(row['byte_size'] or 0))}",
                "created_at": str(row["created_at"]),
                "project_id": pid,
                "project_name": pname,
                "session_id": str(row["session_id"]),
                "session_title": session["title"],
                "turn_id": str(row["turn_id"]) if row["turn_id"] else None,
                "href": _conversation_link(str(row["session_id"]), str(row["turn_id"] or "") or None),
                "external": False,
                "download_url": f"/api/sessions/{row['session_id']}/attachments/{row['attachment_id']}/download",
                "block": None,
                "pin_id": None,
            })

    if "image" in wanted:
        for row in store._rows(
            """
            SELECT generation_id, prompt, project_id, created_at, kind FROM image_generations
            WHERE owner_principal_id = ? AND status = 'ok' AND attachment_id IS NOT NULL
              AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT ?
            """,
            (owner_principal_id, MAX_ITEMS),
        ):
            pid, pname = project_of(row["project_id"])
            prompt = " ".join(str(row["prompt"] or "").split())
            items.append({
                "item_id": f"image:{row['generation_id']}",
                "kind": "image",
                "title": (prompt[:117] + "…") if len(prompt) > 120 else (prompt or "Image"),
                "detail": "Edited image" if row["kind"] == "edit" else "Image",
                "created_at": str(row["created_at"]),
                "project_id": pid,
                "project_name": pname,
                "session_id": None,
                "session_title": None,
                "turn_id": None,
                "href": f"#/design?asset={row['generation_id']}" + (f"&project={pid}" if pid else ""),
                "external": False,
                "download_url": f"/api/images/{row['generation_id']}/bytes",
                "block": None,
                "pin_id": None,
            })

    if "design" in wanted:
        for row in store._rows(
            """
            SELECT document_id, title, project_id, updated_at FROM design_documents
            WHERE owner_principal_id = ? AND deleted_at IS NULL
            ORDER BY updated_at DESC LIMIT ?
            """,
            (owner_principal_id, MAX_ITEMS),
        ):
            pid, pname = project_of(row["project_id"])
            items.append({
                "item_id": f"design:{row['document_id']}",
                "kind": "design",
                "title": str(row["title"]),
                "detail": "Design",
                "created_at": str(row["updated_at"]),
                "project_id": pid,
                "project_name": pname,
                "session_id": None,
                "session_title": None,
                "turn_id": None,
                "href": f"#/design?view=documents&record={row['document_id']}",
                "external": False,
                "download_url": None,
                "block": None,
                "pin_id": None,
            })

    if "block" in wanted:
        for pin in store.list_library_pins(owner_principal_id=owner_principal_id, limit=MAX_ITEMS):
            session = sessions.get(str(pin["session_id"]))
            pid, pname = project_of(pin["project_id"])
            items.append({
                "item_id": f"block:{pin['pin_id']}",
                "kind": "block",
                "title": str(pin["title"]),
                "detail": _BLOCK_NAMES.get(str(pin["part_type"]), "Answer block"),
                "created_at": str(pin["created_at"]),
                "project_id": pid,
                "project_name": pname,
                "session_id": str(pin["session_id"]) if session else None,
                "session_title": session["title"] if session else None,
                "turn_id": str(pin["turn_id"]) if session else None,
                "href": _conversation_link(str(pin["session_id"]), str(pin["turn_id"])) if session else "#/work?tab=library",
                "external": False,
                "download_url": None,
                "block": {"type": str(pin["part_type"]), "data": pin["data"]},
                "pin_id": str(pin["pin_id"]),
            })

    if "pull_request" in wanted:
        for row in store._rows(
            """
            SELECT receipt_id, repository, number, url, state, session_id, turn_id, created_at
            FROM pull_request_receipts WHERE owner_principal_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (owner_principal_id, MAX_ITEMS),
        ):
            session = sessions.get(str(row["session_id"] or ""))
            pid, pname = project_of(session["project_id"] if session else None)
            url = str(row["url"])
            items.append({
                "item_id": f"pull_request:{row['receipt_id']}",
                "kind": "pull_request",
                "title": f"{row['repository']} #{row['number']}",
                "detail": f"Pull request · {str(row['state']).capitalize()}",
                "created_at": str(row["created_at"]),
                "project_id": pid,
                "project_name": pname,
                "session_id": str(row["session_id"]) if session else None,
                "session_title": session["title"] if session else None,
                "turn_id": str(row["turn_id"]) if session and row["turn_id"] else None,
                "href": url if url.startswith("https://") else "#/build",
                "external": url.startswith("https://"),
                "download_url": None,
                "block": None,
                "pin_id": None,
            })

    if project_id is not None:
        items = [item for item in items if item["project_id"] == project_id]
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:MAX_ITEMS]


def _sessions(store: SQLiteStore, user_id: str | None) -> dict[str, dict[str, Any]]:
    """This account's conversations (and unattributed ones), by id."""
    rows = store._rows(
        "SELECT session_id, title, project_id FROM sessions WHERE ? IS NULL OR user_id = ? OR user_id IS NULL",
        (user_id, user_id),
    )
    return {
        str(row["session_id"]): {
            "title": (str(row["title"]) if row["title"] else None),
            "project_id": row["project_id"],
        }
        for row in rows
    }
