"""Chat search by meaning, beside search by words (FIXED-1425 follow-up)."""

from __future__ import annotations

from pathlib import Path

from raiker.context.meaning_search import meaning_matches
from raiker.storage.sqlite import SQLiteStore

_TOPICS = {"japan": [1.0, 0.0, 0.0], "kyoto": [0.95, 0.1, 0.0], "tax": [0.0, 1.0, 0.0]}


def _embed(text: str) -> list[float] | None:
    lowered = text.lower()
    for word, vector in _TOPICS.items():
        if word in lowered:
            return vector
    return [0.0, 0.0, 1.0]


def _chat(store: SQLiteStore, session_id: str, title: str, prompt: str) -> None:
    store.create_session(session_id, "/w", title=title)
    store.insert_turn(session_id, f"{session_id}_t", prompt)
    store.complete_turn(f"{session_id}_t", "completed", "ok")


def test_a_chat_about_the_same_thing_in_other_words_is_found(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _chat(store, "kyoto", "Flights", "Book Kyoto flights for April")
    _chat(store, "tax", "Paperwork", "File the tax return")
    found = meaning_matches(store, "the Japan holiday", _embed, user_id=None)
    assert [row["session_id"] for row in found] == ["kyoto"]
    assert found[0]["match_kind"] == "meaning"
    assert "Kyoto flights" in found[0]["match_snippet"]


def test_meaning_never_repeats_a_word_match_and_needs_an_embedding(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _chat(store, "kyoto", "Flights", "Book Kyoto flights for April")
    assert meaning_matches(store, "Japan", _embed, user_id=None, exclude=["kyoto"]) == []
    assert meaning_matches(store, "Japan", lambda _text: None, user_id=None) == []


def test_another_accounts_chats_are_not_compared(tmp_path: Path) -> None:
    from raiker.contracts.ids import utc_now
    from raiker.contracts.models import User

    store = SQLiteStore(tmp_path)
    store.insert_user(User(user_id="someone_else", display_name="someone", email=None, is_active=True,
                           created_at=utc_now(), updated_at=utc_now()))
    store.create_session("kyoto", "/w", title="Flights", user_id="someone_else")
    store.insert_turn("kyoto", "kyoto_t", "Book Kyoto flights for April")
    assert meaning_matches(store, "Japan", _embed, user_id="me") == []
    assert [row["session_id"] for row in meaning_matches(store, "Japan", _embed, user_id="someone_else")] == ["kyoto"]
