"""Recall of the owner's own past conversations (RAIKER-2020).

Durable memory answers "what was I told to remember". This answers the other
half of recall: "what did we actually say, and when" — the question a chat from
three years ago is asked. It is a **read of the owner's own transcript**, scoped
to the acting principal's user and bounded by a result limit, so it grants no
authority the owner did not already have over their own conversation list.

What comes back is transcript text the model itself once wrote and the owner once
typed. It is returned as *data*: the caller labels it untrusted exactly like a
fetched page, because an old conversation can carry an instruction that was never
meant to apply to this turn.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

MAX_RESULTS = 25
#: How much of the matched side of an exchange a result carries. The index's own
#: `snippet()` is ~18 tokens around the hit — enough for a person scanning a
#: result list, and *not* enough for the model, which was handed
#: "we rotate the SQLCipher key every…" and could not answer the question it had
#: just found the conversation for. A result therefore carries the message,
#: bounded, and the short snippet separately as the reason it matched.
TEXT_CHARS = 1200
MATCH_CHARS = 400


def _text(row: dict[str, Any]) -> str:
    source = "summary" if str(row.get("role")) == "answer" else "prompt_text"
    body = str(row.get(source) or "") or str(row.get("snippet") or "")
    collapsed = " ".join(body.split())
    return collapsed[:TEXT_CHARS] + ("…" if len(collapsed) > TEXT_CHARS else "")


def conversation_search(
    workspace_root: str | Path,
    query: str,
    *,
    max_results: Any = 10,
    session_id: str | None = None,
    after: str | None = None,
    before: str | None = None,
    store: SQLiteStore | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Find past exchanges matching *query*, newest first.

    ``after``/``before`` are ISO-8601 dates or timestamps. They are what makes an
    old conversation reachable: any bounded result set is otherwise the recent
    one, so a question about last year has to be able to say so.
    """
    from raiker.storage.sqlite import SQLiteStore as _Store

    if not query.strip():
        return {
            "status": "failed",
            "error": {"type": "empty_query", "message": "Search query cannot be empty."},
        }
    try:
        limit = max(1, min(int(max_results), MAX_RESULTS))
    except (TypeError, ValueError):
        limit = 10
    rows = (store or _Store(workspace_root)).search_conversation_turns(
        query,
        user_id=user_id,
        limit=limit,
        session_id=session_id,
        after=after,
        before=before,
    )
    return {
        "status": "success",
        "count": len(rows),
        "trust_label": "untrusted_conversation_data",
        "results": [
            {
                "session_id": str(row.get("session_id") or ""),
                "turn_id": str(row.get("turn_id") or ""),
                "title": str(row.get("session_title") or "Untitled conversation"),
                "origin": str(row.get("origin") or "chat"),
                "role": str(row.get("role") or "prompt"),
                "created_at": str(row.get("created_at") or ""),
                "text": _text(row),
                "matched": " ".join(str(row.get("snippet") or "").split())[:MATCH_CHARS],
            }
            for row in rows
        ],
    }
