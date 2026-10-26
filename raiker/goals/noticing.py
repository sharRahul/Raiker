"""QUI-F03 — goals noticed in conversation.

When the same aim comes up in more than one conversation, Chat offers *This
looks like an ongoing goal. Track it?* This module decides whether to offer, and
remembers a *Not now*.

It is deliberately plain: no model call, nothing leaves the computer, and
nothing is created. An aim is the set of content words in what the owner asked;
two requests share an aim when they share at least :data:`MIN_SHARED` of those
words and at least :data:`MIN_OVERLAP` of the smaller set. The offer only fills
the Goals intake form; a goal exists only once the owner saves it there, and
runs only once they accept and start it (PA-D01).

An aim is offered once. *Not now* is stored as the aim's keywords, and a later
aim that overlaps a dismissed one as much as two requests must overlap to
match is the same aim and is not offered again. An aim that already has a goal
(a draft included) is not offered either.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

#: Two requests share an aim when they share this many content words…
MIN_SHARED = 3
#: …and that is at least this share of the shorter request's content words.
MIN_OVERLAP = 0.5
#: How far back other conversations are read.
LOOKBACK_DAYS = 30
#: The most other conversations read per check: enough for a month of use.
MAX_SESSIONS = 200

_WORD = re.compile(r"[a-zà-ÿ0-9][a-zà-ÿ0-9'-]+")

#: Words that carry no aim. Short words (three letters or fewer) are dropped
#: before this list is consulted, so it holds only longer ones.
_STOP = frozenset(
    ["about", "above", "after", "again", "against", "also", "always", "another", "anything", "because", "been", "before", "being", "below", "between", "both", "brief", "briefly", "could", "does", "doing", "done", "down", "during", "each", "every", "from", "further", "give", "have", "having", "help", "here", "into", "just", "know", "like", "make", "more", "most", "much", "need", "only", "other", "ought", "ours", "over", "please", "quick", "quickly", "really", "same", "should", "some", "such", "tell", "than", "that", "their", "them", "then", "there", "these", "they", "thing", "things", "this", "those", "through", "today", "under", "until", "very", "want", "week", "what", "when", "where", "which", "while", "will", "with", "would", "your", "yours", "ready", "write", "raiker", "summary", "summarise", "summarize"]
)


@dataclass(frozen=True)
class GoalSuggestion:
    aim_key: str
    keywords: tuple[str, ...]
    #: A short outcome for the form's title, taken from the request itself.
    title: str
    #: The request as the owner wrote it, for *What a good result looks like*.
    objective: str
    #: The other conversations the aim came up in, newest first.
    session_ids: tuple[str, ...]
    session_titles: tuple[str, ...]


def keywords(text: str) -> frozenset[str]:
    """The content words of one request."""
    return frozenset(
        word.strip("'-")
        for word in _WORD.findall(text.lower())
        if len(word) > 3 and word not in _STOP
    )


def same_aim(left: frozenset[str], right: frozenset[str]) -> bool:
    shared = left & right
    smaller = min(len(left), len(right))
    return smaller > 0 and len(shared) >= MIN_SHARED and len(shared) / smaller >= MIN_OVERLAP


def aim_key(words: frozenset[str]) -> str:
    return hashlib.sha256(" ".join(sorted(words)).encode("utf-8")).hexdigest()[:24]


def _title(text: str) -> str:
    line = " ".join(text.split())
    line = line[0].upper() + line[1:] if line else line
    return line if len(line) <= 80 else line[:79].rstrip() + "…"


def _dismissed(store: SQLiteStore, owner: str) -> list[frozenset[str]]:
    rows = store._rows(
        "SELECT keywords_json FROM goal_suggestion_dismissals WHERE owner_principal_id = ?",
        (owner,),
    )
    found: list[frozenset[str]] = []
    for row in rows:
        try:
            words = json.loads(str(row["keywords_json"]))
        except ValueError:
            continue
        if isinstance(words, list):
            found.append(frozenset(str(word) for word in words))
    return found


def _goal_aims(store: SQLiteStore, owner: str) -> list[frozenset[str]]:
    rows = store._rows(
        "SELECT title, objective FROM goals WHERE owner_principal_id = ?",
        (owner,),
    )
    return [keywords(f"{row['title']} {row['objective']}") for row in rows]


def suggestion_for(
    store: SQLiteStore, *, owner_principal_id: str, user_id: str | None, session_id: str
) -> GoalSuggestion | None:
    """The goal to offer under this conversation's latest request, or ``None``."""
    session = store.load_session(session_id)
    if session is None or (user_id and session.get("user_id") not in (None, user_id)):
        return None
    if str(session.get("origin") or "chat") == "task":
        # A routine's own conversation repeats its aim by design.
        return None
    turns = [turn for turn in store.list_turns(session_id, limit=50) if (turn.get("prompt_text") or "").strip()]
    if not turns:
        return None
    latest = max(turns, key=lambda turn: (str(turn.get("created_at") or ""), str(turn["turn_id"])))
    request = str(latest["prompt_text"]).strip()
    words = keywords(request)
    if len(words) < MIN_SHARED:
        return None

    since = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    others = store._rows(
        "SELECT t.session_id, t.prompt_text, s.title, s.updated_at FROM turns t "
        "JOIN sessions s ON s.session_id = t.session_id "
        "WHERE t.session_id <> ? AND t.prompt_text IS NOT NULL AND t.created_at >= ? "
        "AND COALESCE(s.origin, 'chat') <> 'task' "
        "AND (? IS NULL OR s.user_id = ? OR s.user_id IS NULL) "
        "ORDER BY t.created_at DESC LIMIT ?",
        (session_id, since, user_id, user_id, MAX_SESSIONS * 5),
    )
    matched: dict[str, str] = {}
    shared: frozenset[str] = words
    for row in others:
        other_id = str(row["session_id"])
        if other_id in matched:
            continue
        theirs = keywords(str(row["prompt_text"] or ""))
        if same_aim(words, theirs):
            if not matched:
                # The aim is what the first match shares with this request.
                shared = words & theirs
            matched[other_id] = str(row["title"] or "Untitled chat")
        if len(matched) >= MAX_SESSIONS:
            break
    if not matched:
        return None

    owner = owner_principal_id
    if any(same_aim(words, dismissed) or same_aim(shared, dismissed) for dismissed in _dismissed(store, owner)):
        return None
    if any(same_aim(words, goal) for goal in _goal_aims(store, owner)):
        return None
    ordered = sorted(shared)
    return GoalSuggestion(
        aim_key=aim_key(frozenset(ordered)),
        keywords=tuple(ordered),
        title=_title(request),
        objective=request[:4000],
        session_ids=tuple(matched),
        session_titles=tuple(matched.values()),
    )


def dismiss(store: SQLiteStore, *, owner_principal_id: str, words: list[str]) -> str:
    """*Not now*: remember the aim so it is never offered again."""
    clean = sorted({word.strip().lower() for word in words if isinstance(word, str) and word.strip()})[:24]
    key = aim_key(frozenset(clean))
    store._execute(
        "INSERT OR IGNORE INTO goal_suggestion_dismissals (owner_principal_id, aim_key, keywords_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (owner_principal_id, key, json.dumps(clean), utc_now()),
    )
    return key


def view(suggestion: GoalSuggestion | None) -> dict[str, Any] | None:
    if suggestion is None:
        return None
    return {
        "aim_key": suggestion.aim_key,
        "keywords": list(suggestion.keywords),
        "title": suggestion.title,
        "objective": suggestion.objective,
        "session_ids": list(suggestion.session_ids),
        "session_titles": list(suggestion.session_titles),
    }
