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
#: TOOL-119 — how much of a conversation's opening request names what it was about.
ABOUT_CHARS = 200


def _text(row: dict[str, Any]) -> str:
    source = "summary" if str(row.get("role")) == "answer" else "prompt_text"
    body = str(row.get(source) or "") or str(row.get("snippet") or "")
    collapsed = " ".join(body.split())
    return collapsed[:TEXT_CHARS] + ("…" if len(collapsed) > TEXT_CHARS else "")


def _result(row: dict[str, Any]) -> dict[str, Any]:
    """One bounded, sensitivity-filtered result.

    MEM-HISTORY-03 — an old exchange can hold a pasted credential. The window
    and the match are passed through the same redaction every context item
    gets, so a history hit never carries a secret back into a turn, and the
    result says when something was masked.
    """
    from raiker.context.redaction import redact_text

    text, text_redacted = redact_text(_text(row))
    matched, match_redacted = redact_text(
        " ".join(str(row.get("snippet") or "").split())[:MATCH_CHARS]
    )
    return {
        "session_id": str(row.get("session_id") or ""),
        "turn_id": str(row.get("turn_id") or ""),
        "title": str(row.get("session_title") or "Untitled conversation"),
        "origin": str(row.get("origin") or "chat"),
        "role": str(row.get("role") or "prompt"),
        "created_at": str(row.get("created_at") or ""),
        "text": text,
        "matched": matched,
        "redacted": text_redacted or match_redacted,
    }


def _conversations(store: Any, session_ids: list[str]) -> dict[str, dict[str, Any]]:
    """TOOL-119 — one line per conversation a hit came from: what it was about.

    A hit is one exchange; the model asked *which conversation* it is in, and
    an exchange from the middle of a long chat ("yes, the second one") says
    nothing about that. So each result names its conversation's opening
    request, how many exchanges it has and when it started — read from the
    transcript, redacted like the hit, with no model call.
    """
    from raiker.context.redaction import redact_text

    unique = sorted({sid for sid in session_ids if sid})
    if not unique:
        return {}
    rows: list[Any] = []
    try:
        for session_id in unique:  # at most MAX_RESULTS conversations
            rows.extend(store._rows(  # noqa: SLF001 - one bounded read beside the store's own search
                "SELECT t.session_id AS session_id, COUNT(*) AS turns, MIN(t.created_at) AS started_at, "
                "(SELECT f.prompt_text FROM turns f WHERE f.session_id = t.session_id "
                "AND f.prompt_text IS NOT NULL ORDER BY f.created_at ASC LIMIT 1) AS first_prompt "
                "FROM turns t WHERE t.session_id = ? GROUP BY t.session_id",
                (session_id,),
            ))
    except Exception:  # noqa: BLE001 - the hits still answer without the summary
        return {}
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        about = " ".join(str(row["first_prompt"] or "").split())
        about = about[:ABOUT_CHARS] + ("…" if len(about) > ABOUT_CHARS else "")
        cleaned, _redacted = redact_text(about)
        found[str(row["session_id"])] = {
            "about": cleaned,
            "turns": int(row["turns"] or 0),
            "started_at": str(row["started_at"] or ""),
        }
    return found


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
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    """Find past exchanges matching *query*, best match first.

    ``after``/``before`` are ISO-8601 dates or timestamps. They are what makes an
    old conversation reachable: any bounded result set is otherwise the recent
    one, so a question about last year has to be able to say so.

    MEM-HISTORY-03 — the boundary: owner-scoped, at most :data:`MAX_RESULTS`
    results of at most :data:`TEXT_CHARS` each, redacted, withheld entirely
    while the owner's Incognito is on, and read-only — a hit is never promoted
    into durable memory and is labelled untrusted, never authority.
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
    resolved = store or _Store(workspace_root)
    if owner_principal_id and resolved.is_memory_incognito(owner_principal_id):
        # Incognito withholds cross-conversation recall; the model is told why
        # rather than handed an empty list it would read as "never discussed".
        return {
            "status": "withheld",
            "reason": "incognito",
            "count": 0,
            "trust_label": "untrusted_conversation_data",
            "results": [],
        }
    rows = resolved.search_conversation_turns(
        query,
        user_id=user_id,
        limit=limit,
        session_id=session_id,
        after=after,
        before=before,
    )
    results = [_result(row) for row in rows]
    conversations = _conversations(resolved, [result["session_id"] for result in results])
    for result in results:
        summary = conversations.get(result["session_id"])
        if summary is not None:
            result["conversation"] = summary
    return {
        "status": "success",
        "count": len(rows),
        "trust_label": "untrusted_conversation_data",
        "results": results,
    }
