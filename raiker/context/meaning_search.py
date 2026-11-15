"""Conversation search by meaning, beside search by words.

FIXED-1425 left "thread and Library search by meaning" as a separate change.
Search by words (`conversation_fts`) finds a chat that used the same words; an
owner who remembers *what it was about* — "the Japan holiday" for a chat about
"Kyoto flights" — finds nothing. This adds the meaning half, on exactly the
terms goal noticing already uses (FIXED-1481):

* It runs only where the owner's embedding model may run: the embedder is the
  governed one memory recall uses, and it is ``None`` otherwise, so a hosted
  backend the owner has not allowed for recall is never reached from here.
* It is bounded: the most recent :data:`CANDIDATES` conversations are compared,
  each by its title and first request, once per search.
* It only adds: a conversation the words already found keeps its word match,
  and meaning results are marked ``match_kind: "meaning"`` so the list can say
  why a chat is there.
"""

from __future__ import annotations

import hashlib
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import Any

#: How many recent conversations one search compares by meaning.
CANDIDATES = 40
#: The cosine a conversation must reach. Lower than goal noticing (0.85),
#: because a search names a topic and the conversation states a request.
THRESHOLD = 0.6
#: Meaning results added to one search.
MAX_RESULTS = 8

Embed = Callable[[str], list[float] | None]

#: How many candidate vectors are kept between searches, per process. A
#: conversation's title and first request rarely change, and without this a
#: second search embedded the same forty texts again — forty governed model
#: calls for a list that was already ranked once.
DOCUMENT_CACHE_SIZE = 2048
_DOCUMENTS: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
_DOCUMENTS_LOCK = threading.Lock()


def _document_vector(embed: Embed, text: str) -> list[float] | None:
    """``embed(text)``, remembered per embedding space when ``embed`` names one.

    The space is the backend's model label (``embed.space``); an embedder that
    does not name one is never cached, so vectors from two models are never
    compared. Only successful vectors are kept, keyed by the text's SHA-256.
    """
    space = getattr(embed, "space", None)
    if not isinstance(space, str) or not space:
        return embed(text)
    key = (space, hashlib.sha256(text.encode("utf-8")).hexdigest())
    with _DOCUMENTS_LOCK:
        held = _DOCUMENTS.get(key)
        if held is not None:
            _DOCUMENTS.move_to_end(key)
            return held
    vector = embed(text)
    if vector:
        with _DOCUMENTS_LOCK:
            _DOCUMENTS[key] = vector
            while len(_DOCUMENTS) > DOCUMENT_CACHE_SIZE:
                _DOCUMENTS.popitem(last=False)
    return vector


def clear_document_cache() -> None:
    with _DOCUMENTS_LOCK:
        _DOCUMENTS.clear()


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def meaning_matches(
    store: Any,
    query: str,
    embed: Embed,
    *,
    user_id: str | None,
    exclude: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Recent conversations that are about ``query`` in other words, best first."""
    vector = embed(query.strip())
    if not vector:
        return []
    skip = set(exclude)
    rows = store._rows(  # noqa: SLF001 - one bounded read beside the store's own search
        "SELECT s.*, (SELECT t.prompt_text FROM turns t WHERE t.session_id = s.session_id "
        "AND t.prompt_text IS NOT NULL ORDER BY t.created_at ASC LIMIT 1) AS first_prompt "
        "FROM sessions s WHERE COALESCE(s.origin, 'chat') <> 'task' "
        "AND (? IS NULL OR s.user_id = ? OR s.user_id IS NULL) "
        "ORDER BY s.updated_at DESC LIMIT ?",
        (user_id, user_id, CANDIDATES + len(skip)),
    )
    scored: list[tuple[float, dict[str, Any]]] = []
    compared = 0
    for row in rows:
        record = dict(row)
        session_id = str(record.get("session_id") or "")
        if not session_id or session_id in skip:
            continue
        compared += 1
        if compared > CANDIDATES:
            break
        prompt = " ".join(str(record.pop("first_prompt", "") or "").split())
        text = f"{record.get('title') or ''}. {prompt}".strip(". ")
        if len(text) < 8:
            continue
        other = _document_vector(embed, text[:2000])
        if not other:
            continue
        score = _cosine(vector, other)
        if score >= THRESHOLD:
            record["match_snippet"] = prompt[:300]
            record["match_turn_id"] = ""
            record["match_kind"] = "meaning"
            scored.append((score, record))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [record for _score, record in scored[:MAX_RESULTS]]


def rank_by_meaning(
    query: str,
    candidates: Iterable[tuple[str, str]],
    embed: Embed,
    *,
    threshold: float = THRESHOLD,
    limit: int = MAX_RESULTS,
    bound: int = CANDIDATES,
) -> list[str]:
    """The keys of ``candidates`` (``(key, text)`` pairs) about ``query``, best first.

    The same bounds as conversation search: at most ``bound`` candidates are
    embedded per call, a short text is never compared, and nothing is returned
    when the query itself cannot be embedded.
    """
    vector = embed(query.strip())
    if not vector:
        return []
    scored: list[tuple[float, str]] = []
    for index, (key, text) in enumerate(candidates):
        if index >= bound:
            break
        cleaned = " ".join(text.split())
        if len(cleaned) < 8:
            continue
        other = _document_vector(embed, cleaned[:2000])
        if not other:
            continue
        score = _cosine(vector, other)
        if score >= threshold:
            scored.append((score, key))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [key for _score, key in scored[:limit]]
