"""MEM-HISTORY-03 — the session-history search boundary.

History search answers "we discussed this before". It must stay owner-scoped,
deterministic, bounded and sensitivity-filtered, and a hit must never promote
itself into durable memory or carry authority.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.conversation_tools import MAX_RESULTS, TEXT_CHARS, conversation_search
from raiker.tools.memory_tools import MAX_SEARCH_RESULTS, memory_search


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


def _exchange(store: SQLiteStore, session_id: str, turn_id: str, prompt: str, answer: str) -> None:
    store.insert_turn(session_id, turn_id, prompt)
    store.complete_turn(turn_id, "completed", answer)


def _durable_counts(store: SQLiteStore) -> tuple[int, int]:
    with store.connect() as connection:
        memories = connection.execute("SELECT COUNT(*) FROM approved_memory").fetchone()[0]
        candidates = connection.execute("SELECT COUNT(*) FROM memory_candidates").fetchone()[0]
    return int(memories), int(candidates)


def test_tied_hits_come_back_in_the_same_order_every_time(store: SQLiteStore) -> None:
    store.create_session("sess_a", "/w", title="Ties")
    for turn_id in ("turn_c", "turn_a", "turn_b"):
        _exchange(store, "sess_a", turn_id, "the heron nests by the weir", "noted")
    with store.connect() as connection:
        connection.execute("UPDATE turns SET created_at = '2026-01-01T00:00:00Z'")

    first = [row["turn_id"] for row in store.search_conversation_turns("heron weir")]
    second = [row["turn_id"] for row in store.search_conversation_turns("heron weir")]

    assert first == second == sorted(first)


def test_a_credential_in_an_old_exchange_is_masked(store: SQLiteStore, tmp_path: Path) -> None:
    store.create_session("sess_k", "/w", title="Keys")
    _exchange(
        store,
        "sess_k",
        "turn_k",
        "the deploy token is api_key=fixture0token0abcdefghijklmnop for the heron service",
        "stored",
    )

    result = conversation_search(tmp_path, "heron service", store=store)

    (hit,) = result["results"]
    assert "fixture0token0abcdefghijklmnop" not in hit["text"]
    assert "fixture0token0abcdefghijklmnop" not in hit["matched"]
    assert hit["redacted"] is True
    assert result["trust_label"] == "untrusted_conversation_data"


def test_results_are_bounded_in_count_and_length(store: SQLiteStore, tmp_path: Path) -> None:
    store.create_session("sess_b", "/w", title="Bulk")
    for index in range(MAX_RESULTS + 5):
        _exchange(store, "sess_b", f"turn_{index:03d}", "kestrel " + "word " * 600, "ok")

    result = conversation_search(tmp_path, "kestrel", store=store, max_results=10_000)

    assert result["count"] == MAX_RESULTS
    assert all(len(hit["text"]) <= TEXT_CHARS + 1 for hit in result["results"])


def test_incognito_withholds_history_search(store: SQLiteStore, tmp_path: Path, seed_account) -> None:  # type: ignore[no-untyped-def]
    owner, _token = seed_account(tmp_path, "owner")
    user_id = store.principal_user_id(owner)
    store.create_session("sess_i", "/w", title="Private", user_id=user_id)
    _exchange(store, "sess_i", "turn_i", "the osprey plan", "kept")
    store.set_memory_incognito(True, owner)

    result = conversation_search(
        tmp_path, "osprey", store=store, user_id=user_id, owner_principal_id=owner
    )

    assert result["status"] == "withheld"
    assert result["reason"] == "incognito"
    assert result["results"] == []


def test_another_owner_never_sees_the_exchange(store: SQLiteStore, tmp_path: Path, seed_account) -> None:  # type: ignore[no-untyped-def]
    owner, _ = seed_account(tmp_path, "owner")
    stranger, _ = seed_account(tmp_path, "stranger")
    store.create_session("sess_o", "/w", title="Mine", user_id=store.principal_user_id(owner))
    _exchange(store, "sess_o", "turn_o", "the plover survey", "done")

    theirs = conversation_search(
        tmp_path,
        "plover",
        store=store,
        user_id=store.principal_user_id(stranger),
        owner_principal_id=stranger,
    )

    assert theirs["results"] == []


def test_a_history_hit_is_never_promoted_to_memory(store: SQLiteStore, tmp_path: Path) -> None:
    store.create_session("sess_p", "/w", title="Prefs")
    _exchange(store, "sess_p", "turn_p", "remember that I always want tabs", "I will")
    before = _durable_counts(store)

    conversation_search(tmp_path, "tabs", store=store)
    conversation_search(tmp_path, "always want", store=store)

    assert _durable_counts(store) == before


def test_memory_search_clamps_the_requested_count(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    governance = MemoryGovernance(
        "evt_c", "sess_c", None, "test", 1.0, 1.0, "until_forget", "approved", "test"
    )
    for index in range(MAX_SEARCH_RESULTS + 5):
        write_memory(
            f"Kestrel note number {index}.", workspace_root=tmp_path, scope="user",
            store=store, governance=governance,
        )

    result = memory_search(tmp_path, "kestrel note", max_results=1_000_000)
    fallback = memory_search(tmp_path, "kestrel note", max_results="many")

    assert result["status"] == "success"
    assert 0 < len(result["results"]) <= MAX_SEARCH_RESULTS
    assert fallback["status"] == "success"


def test_memory_search_is_withheld_under_incognito(tmp_path: Path, seed_account) -> None:  # type: ignore[no-untyped-def]
    owner, _ = seed_account(tmp_path, "owner")
    store = SQLiteStore(tmp_path)
    governance = MemoryGovernance(
        "evt_i", "sess_i", None, "test", 1.0, 1.0, "until_forget", "approved", "test"
    )
    write_memory(
        "The osprey nests by the lake.", workspace_root=tmp_path, scope="user",
        store=store, governance=governance, owner_principal_id=owner,
    )
    assert memory_search(tmp_path, "osprey", owner_principal_id=owner)["results"]
    store.set_memory_incognito(True, owner)

    result = memory_search(tmp_path, "osprey", owner_principal_id=owner)

    assert result == {"status": "withheld", "reason": "incognito", "count": 0, "results": []}
