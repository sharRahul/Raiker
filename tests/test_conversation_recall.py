"""RAIKER-2020 — reading a past conversation back.

The question these cover is the one memory is actually asked: *what did we say,
and when*. Durable memory answers "what was I told to remember"; until this
change nothing answered the other half, so a conversation from years ago was
unreachable from a turn however exactly it held the answer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.context.gatherer import ContextGatherer
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.conversation_tools import conversation_search


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


def _exchange(
    store: SQLiteStore, session_id: str, turn_id: str, prompt: str, answer: str
) -> None:
    store.insert_turn(session_id, turn_id, prompt)
    store.complete_turn(turn_id, "completed", answer)


def _history(store: SQLiteStore) -> None:
    store.create_session("sess_old", "/w", title="Key rotation")
    _exchange(
        store,
        "sess_old",
        "turn_old",
        "How do we rotate the SQLCipher workspace key?",
        "Rotate it with raiker-app; the old key stays valid until the backup verifies.",
    )
    store.create_session("sess_new", "/w", title="Backups")
    _exchange(
        store, "sess_new", "turn_new", "Where should backups go?", "NAS targets are pending."
    )


def test_both_sides_of_an_exchange_are_searchable(store: SQLiteStore) -> None:
    """A hit is attributed, so an answer can be quoted rather than reconstructed."""
    _history(store)
    roles = {row["role"] for row in store.search_conversation_turns("rotate")}
    assert roles == {"prompt", "answer"}


def test_a_hit_carries_the_conversation_it_belongs_to(store: SQLiteStore) -> None:
    _history(store)
    hit = store.search_conversation_turns("SQLCipher")[0]
    assert hit["session_id"] == "sess_old"
    assert hit["session_title"] == "Key rotation"
    assert hit["turn_id"] == "turn_old"


def test_a_date_window_reaches_a_period_rather_than_the_recent_matches(
    store: SQLiteStore,
) -> None:
    """The argument that makes an old conversation reachable at all."""
    _history(store)
    assert store.search_conversation_turns("SQLCipher", after="2099-01-01") == []
    assert store.search_conversation_turns("SQLCipher", before="2099-01-01")


def test_one_conversation_can_be_searched_in_isolation(store: SQLiteStore) -> None:
    _history(store)
    assert store.search_conversation_turns("backups", session_id="sess_old") == []
    assert store.search_conversation_turns("backups", session_id="sess_new")


def test_a_term_below_the_index_floor_still_finds_its_turn(store: SQLiteStore) -> None:
    """`q3` is an identifier, not a stopword — a substring scan stands in for it."""
    store.create_session("sess_short", "/w")
    _exchange(store, "sess_short", "turn_short", "ship q3", "q3 is the target")
    assert store.search_conversation_turns("q3")


def test_the_fallback_scan_attributes_the_side_that_actually_matched(
    store: SQLiteStore,
) -> None:
    """Otherwise a hit in an answer is reported as a prompt and read back from
    the wrong column."""
    store.create_session("sess_side", "/w")
    _exchange(store, "sess_side", "turn_side", "what shipped?", "we shipped q3 targets")
    hit = store.search_conversation_turns("q3")[0]
    assert hit["role"] == "answer"
    assert "q3" in hit["snippet"]


def test_another_owner_never_sees_the_conversation(store: SQLiteStore) -> None:
    """The index narrows candidates; `sessions.user_id` still decides visibility."""
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at)"
            " VALUES ('user_a', 'A', 'a@example.invalid', 1, '2026-01-01', '2026-01-01')"
        )
    store.create_session("sess_owned", "/w", user_id="user_a")
    _exchange(store, "sess_owned", "turn_owned", "private planning", "private answer")
    assert store.search_conversation_turns("private", user_id="user_a")
    assert store.search_conversation_turns("private", user_id="user_b") == []


def test_the_index_is_backfilled_for_a_workspace_that_predates_it(
    tmp_path: Path,
) -> None:
    """A workspace carrying years of history is indexed once, not on every open."""
    store = SQLiteStore(tmp_path)
    store.create_session("sess_legacy", "/w")
    _exchange(store, "sess_legacy", "turn_legacy", "legacy prompt", "legacy answer")
    with store.connect() as connection:
        connection.execute("DELETE FROM conversation_fts")
    assert SQLiteStore(tmp_path).search_conversation_turns("legacy")


def test_rebuild_is_the_owner_started_repair(store: SQLiteStore) -> None:
    _history(store)
    with store.connect() as connection:
        connection.execute("DELETE FROM conversation_fts")
    assert store.rebuild_conversation_fts() == 4
    assert store.search_conversation_turns("rotate")


def test_chat_search_says_why_a_conversation_matched(store: SQLiteStore) -> None:
    """The difference between finding an old chat and recognising it."""
    _history(store)
    row = next(r for r in store.search_sessions("SQLCipher") if r["session_id"] == "sess_old")
    assert "SQLCipher" in row["match_snippet"]
    assert row["match_turn_id"] == "turn_old"


def test_chat_search_still_matches_a_title_alone(store: SQLiteStore) -> None:
    _history(store)
    assert [r["session_id"] for r in store.search_sessions("Backups")] == ["sess_new"]


def test_the_tool_returns_bounded_labelled_results(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _history(store)
    result = conversation_search(tmp_path, "rotate", store=store)
    assert result["status"] == "success"
    assert result["trust_label"] == "untrusted_conversation_data"
    assert result["results"][0]["title"] == "Key rotation"
    assert result["results"][0]["created_at"]


def test_a_result_carries_the_whole_message_not_only_the_matched_fragment(
    tmp_path: Path,
) -> None:
    """The live round handed the model "…rotate the SQLCipher key every…" and it
    could not answer the question it had just found the conversation for."""
    store = SQLiteStore(tmp_path)
    store.create_session("sess_long", "/w", title="Record")
    _exchange(
        store,
        "sess_long",
        "turn_long",
        "For the record: the destination is nas-alpha-7 and we rotate the key every 90 days.",
        "noted.",
    )
    hit = next(
        row for row in conversation_search(tmp_path, "destination", store=store)["results"]
        if row["role"] == "prompt"
    )
    assert "nas-alpha-7" in hit["text"]
    assert "90 days" in hit["text"]
    assert hit["matched"]


def test_the_tool_refuses_an_empty_query(tmp_path: Path) -> None:
    assert conversation_search(tmp_path, "   ")["error"]["type"] == "empty_query"


def test_the_tool_bounds_an_oversized_result_request(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _history(store)
    assert conversation_search(tmp_path, "rotate", max_results=9999, store=store)["count"] <= 25


def test_the_tool_is_offered_to_the_model_and_delegable(tmp_path: Path) -> None:
    from raiker.agents.orchestration import DELEGABLE_TOOLS
    from raiker.models.tool_call_validation import default_tool_specs

    spec = next(s for s in default_tool_specs() if s.name == "conversation_search")
    assert spec.parameters["required"] == ["query"]
    assert {"after", "before", "session_id"} <= set(spec.parameters["properties"])
    assert "conversation_search" in DELEGABLE_TOOLS


def test_ambient_recall_prefers_a_relevant_old_chat_over_a_recent_one(
    store: SQLiteStore,
) -> None:
    """MEM-02 — recall used to be the eight most recent chats, whatever was asked."""
    store.create_session("sess_ancient", "/w", title="The decision")
    _exchange(
        store, "sess_ancient", "turn_ancient", "which cipher did we choose?", "SQLCipher."
    )
    for index in range(12):
        store.create_session(f"sess_noise_{index}", "/w", title=f"Noise {index}")
        _exchange(store, f"sess_noise_{index}", f"turn_noise_{index}", "unrelated", "unrelated")
    recalled = ContextGatherer()._recalled_sessions(store, "which cipher", "sess_current", None)
    assert recalled[0]["session_id"] == "sess_ancient"
    assert "cipher" in str(recalled[0]["match_snippet"]).lower()


def test_ambient_recall_falls_back_to_recent_when_nothing_matches(
    store: SQLiteStore,
) -> None:
    _history(store)
    recalled = ContextGatherer()._recalled_sessions(store, "zzzzzzz", "sess_current", None)
    assert {str(row["session_id"]) for row in recalled} == {"sess_old", "sess_new"}


def test_ambient_recall_never_returns_the_current_conversation(store: SQLiteStore) -> None:
    _history(store)
    recalled = ContextGatherer()._recalled_sessions(store, "SQLCipher", "sess_old", None)
    assert all(str(row["session_id"]) != "sess_old" for row in recalled)
