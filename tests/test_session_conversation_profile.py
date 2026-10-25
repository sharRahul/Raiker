"""QUI-P02 — a conversation's profile is kept on the conversation.

Decided 2026-10-25: Careful or Standard belongs to the conversation, not to the
browser it was chosen in, so another device opening the same conversation sees
the same choice. It is a label the composer sends as a narrowing override; the
store accepts only the two profiles and grants nothing.
"""

from __future__ import annotations

from pathlib import Path

from raiker.storage.sqlite import SQLiteStore


def _store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_a", "ws")
    return store


def test_a_conversation_starts_standard(tmp_path: Path) -> None:
    assert _store(tmp_path).session_profile("sess_a") == "standard"


def test_careful_is_kept_and_read_back(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.set_session_profile("sess_a", "careful")
    assert store.session_profile("sess_a") == "careful"
    # Read by a second store on the same workspace: the choice is the
    # conversation's, not one process's.
    assert SQLiteStore(tmp_path).session_profile("sess_a") == "careful"
    assert store.set_session_profile("sess_a", "standard")
    assert store.session_profile("sess_a") == "standard"


def test_anything_but_the_two_profiles_is_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert not store.set_session_profile("sess_a", "automatic")
    assert store.session_profile("sess_a") == "standard"


def test_an_unknown_conversation_is_refused(tmp_path: Path) -> None:
    assert not _store(tmp_path).set_session_profile("sess_missing", "careful")


def test_another_accounts_conversation_is_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for user_id in ("user_someone_else", "user_owner"):
        store._execute(
            "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, NULL, 1, '2026-10-25T00:00:00Z', '2026-10-25T00:00:00Z')",
            (user_id, user_id),
        )
    store._execute("UPDATE sessions SET user_id = ? WHERE session_id = ?", ("user_someone_else", "sess_a"))
    assert not store.set_session_profile("sess_a", "careful", user_id="user_owner")
    assert store.session_profile("sess_a") == "standard"
