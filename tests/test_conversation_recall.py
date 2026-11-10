"""RAIKER-2020 — reading a past conversation back.

The question these cover is the one memory is actually asked: *what did we say,
and when*. Durable memory answers "what was I told to remember"; until this
change nothing answered the other half, so a conversation from years ago was
unreachable from a turn however exactly it held the answer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

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

@pytest.mark.parametrize("change", ["forgotten", "corrected", "archived", "expired", "search_disabled", "superseded"])
def test_ambient_history_cannot_reintroduce_stale_recalled_memory(store: SQLiteStore, tmp_path: Path, change: str) -> None:
    from dataclasses import replace

    from raiker.memory.store import MemoryGovernance, write_memory

    entry = write_memory(
        "My trial tea is jasmine green tea.", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    store.create_session("sess_memory", "/w", title="Trial tea")
    _exchange(store, "sess_memory", "turn_memory", "What is my trial tea?", "Your trial tea is jasmine green tea.")
    store.record_turn_recall(session_id="sess_memory", turn_id="turn_memory", principal_id="principal_owner", memory_ids=[entry.memory_id])
    assert any(row["session_id"] == "sess_memory" for row in ContextGatherer()._recalled_sessions(store, "trial tea", "current", None))
    changes: dict[str, dict[str, Any]] = {
        "forgotten": {"deleted_at": "2100-01-01T00:00:00Z", "approval_state": "forgotten"},
        "corrected": {"text": "My trial tea is roasted barley tea.", "updated_at": "2100-01-01T00:00:00Z"},
        "archived": {"archived_at": "2100-01-01T00:00:00Z"},
        "expired": {"expires_at": "2000-01-01T00:00:00Z"},
        "search_disabled": {"search_enabled": False},
        "superseded": {"superseded_at": "2100-01-01T00:00:00Z"},
    }
    if change == "forgotten":
        store.mark_approved_memory_forgotten(entry.memory_id, deleted_at="2100-01-01T00:00:00Z", updated_at="2100-01-01T00:00:00Z")
    elif change == "archived":
        store.set_approved_memory_archived(entry.memory_id, archived_at="2100-01-01T00:00:00Z", updated_at="2100-01-01T00:00:00Z")
    else:
        store.update_approved_memory(replace(entry, **changes[change]))
    recalled = ContextGatherer()._recalled_sessions(store, "trial tea", "current", None)
    assert all(row["session_id"] != "sess_memory" for row in recalled)
    # Forgetting memory does not silently delete an owner's historical transcript.
    assert store.search_conversation_turns("trial tea")


def test_ambient_history_omits_the_source_of_a_forgotten_memory(store: SQLiteStore, tmp_path: Path) -> None:
    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("source", "/w", title="My trial tea is jasmine green tea")
    _exchange(store, "source", "source_turn", "Remember my trial tea is jasmine green tea", "Noted")
    entry = write_memory(
        "My trial tea is jasmine green tea.", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "source", "source_turn", "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    store.mark_approved_memory_forgotten(entry.memory_id, deleted_at="2100-01-01T00:00:00Z", updated_at="2100-01-01T00:00:00Z")
    assert ContextGatherer()._recalled_sessions(store, "trial tea", "current", None) == []


def test_stale_memory_filter_does_not_use_another_owners_provenance(store: SQLiteStore, tmp_path: Path) -> None:
    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("owner_chat", "/w", title="Trial tea")
    _exchange(store, "owner_chat", "owner_turn", "trial tea", "A discussion about tea")
    entry = write_memory(
        "Other account's tea", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "owner_chat", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "other_owner"),
        owner_principal_id="other_owner",
    )
    store.mark_approved_memory_forgotten(entry.memory_id, deleted_at="2100-01-01T00:00:00Z", updated_at="2100-01-01T00:00:00Z")
    recalled = ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner")
    assert [row["session_id"] for row in recalled] == ["owner_chat"]


@pytest.mark.parametrize("source", [False, True])
def test_ambient_history_respects_an_edit_within_the_same_clock_second(store: SQLiteStore, tmp_path: Path, source: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace

    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("tea", "/w", title="Trial tea")
    _exchange(store, "tea", "tea_turn", "trial tea", "Jasmine green tea")
    entry = write_memory(
        "Jasmine green tea", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "tea" if source else "", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    monkeypatch.setattr("raiker.storage.stores.memory.utc_now", lambda: entry.created_at)
    monkeypatch.setattr("raiker.storage.stores.conversations.utc_now", lambda: entry.created_at)
    if not source:
        store.record_turn_recall(session_id="tea", turn_id="tea_turn", principal_id="principal_owner", memory_ids=[entry.memory_id])
    # The public edit route records an immutable lifecycle event. Timestamps
    # have second precision, so neither updated_at comparison can order this.
    store.update_approved_memory(replace(entry, text="Roasted barley tea", updated_at=entry.created_at))
    store.record_memory_lifecycle_event(entry.memory_id, "edit", "principal_owner")
    assert ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner") == []


@pytest.mark.parametrize("linked_by", ["source", "recall"])
@pytest.mark.parametrize("change", ["forgotten", "corrected", "archived", "expired", "purged"])
def test_ambient_history_tracks_memory_across_two_indirect_copies(
    store: SQLiteStore, tmp_path: Path, linked_by: str, change: str,
) -> None:
    from dataclasses import replace

    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("original", "/w", title="Trial tea")
    _exchange(store, "original", "original_turn", "trial tea", "Jasmine green tea")
    entry = write_memory(
        "My trial tea is jasmine green tea.", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "original" if linked_by == "source" else "", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    if linked_by == "recall":
        store.record_turn_recall(session_id="original", turn_id="original_turn", principal_id="principal_owner", memory_ids=[entry.memory_id])
    for index, parent in enumerate(["original", "copy_0"]):
        child = f"copy_{index}"
        store.create_session(child, "/w", title="Trial tea")
        _exchange(store, child, f"turn_{index}", "trial tea", "Jasmine green tea")
        item = ContextGatherer()._memory_recall(store, "trial tea", child, "principal_owner")
        assert item is not None
        # Isolate ambient history: the direct memory search can miss this fact.
        item.metadata["memory_ids"] = []
        bundle = ContextGatherer()._apply_budget([item], session_id=child, turn_id=f"turn_{index}", max_items=20, max_chars=12000)
        recalled_sessions = bundle.event_payload()["recalled_session_ids"]
        assert isinstance(recalled_sessions, list)
        assert parent in recalled_sessions
        assert entry.memory_id in bundle.recalled_memory_ids()
        store.record_turn_recall(session_id=child, turn_id=f"turn_{index}", principal_id="principal_owner", memory_ids=bundle.recalled_memory_ids())
        if index == 0:
            store.delete_session("original")
    if change == "forgotten":
        store.mark_approved_memory_forgotten(entry.memory_id, deleted_at=entry.created_at, updated_at=entry.created_at)
    elif change == "corrected":
        store.record_memory_lifecycle_event(entry.memory_id, "edit", "principal_owner")
    elif change == "archived":
        store.set_approved_memory_archived(entry.memory_id, archived_at=entry.created_at, updated_at=entry.created_at)
    elif change == "expired":
        store.update_approved_memory(replace(entry, expires_at="2000-01-01T00:00:00Z"))
    else:
        store.delete_approved_memory(entry.memory_id, owner_principal_id="principal_owner")
    assert ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner") == []
    assert store.search_conversation_turns("jasmine")


def test_indirect_memory_provenance_is_owner_scoped(store: SQLiteStore, tmp_path: Path) -> None:
    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("chat", "/w", title="Trial tea")
    _exchange(store, "chat", "turn", "trial tea", "A discussion about tea")
    entry = write_memory(
        "Other account's tea", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "chat", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "other_owner"),
        owner_principal_id="other_owner",
    )
    store.record_turn_recall(session_id="chat", turn_id="turn", principal_id="other_owner", memory_ids=[entry.memory_id])
    assert store.memory_context_ids_for_sessions(["chat"], owner_principal_id="principal_owner") == []


def _context_event(store: SQLiteStore, session: str, payload: dict[str, Any]) -> None:
    from raiker.contracts.ids import new_id, utc_now
    from raiker.contracts.models import AgentEvent
    from raiker.events.writer import EventLogWriter

    EventLogWriter(store).append(AgentEvent(new_id("evt_"), utc_now(), session, session + "_turn", "context_gathered", "runtime", payload))


@pytest.mark.parametrize("change", ["forgotten", "corrected", "archived", "expired", "purged"])
def test_legacy_unknown_memory_context_is_withheld_but_clean_history_survives(
    store: SQLiteStore, tmp_path: Path, change: str,
) -> None:
    from dataclasses import replace

    from raiker.memory.store import MemoryGovernance, write_memory

    for session in ["legacy_copy", "clean", "tracked_clean"]:
        store.create_session(session, "/w", title="Trial tea")
        _exchange(store, session, session + "_turn", "trial tea", "Jasmine green tea" if session == "legacy_copy" else "An unrelated discussion")
    _context_event(store, "legacy_copy", {"source_types": ["current_prompt", "memory_recall"], "recalled_memory_ids": []})
    _context_event(store, "clean", {"source_types": ["current_prompt"]})
    _context_event(store, "tracked_clean", {"source_types": ["memory_recall"], "recalled_memory_ids": [], "recalled_session_ids": [], "memory_provenance_version": 1, "memory_provenance_complete": True})
    entry = write_memory(
        "My trial tea is jasmine green tea.", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    assert len(ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner")) == 3
    if change == "forgotten":
        store.mark_approved_memory_forgotten(entry.memory_id, deleted_at=entry.created_at, updated_at=entry.created_at, owner_principal_id="principal_owner")
    elif change == "corrected":
        store.record_memory_lifecycle_event(entry.memory_id, "edit", "principal_owner")
    elif change == "purged":
        store.delete_approved_memory(entry.memory_id, owner_principal_id="principal_owner")
    elif change == "archived":
        store.set_approved_memory_archived(entry.memory_id, archived_at=entry.created_at, updated_at=entry.created_at)
    else:
        store.update_approved_memory(replace(entry, expires_at="2000-01-01T00:00:00Z"))
    recalled = ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner")
    assert {row["session_id"] for row in recalled} == {"clean", "tracked_clean"}
    item = ContextGatherer()._memory_recall(store, "trial tea", "current", "principal_owner")
    assert item is not None
    assert item.metadata["history_withheld_count"] == 1
    assert store.search_conversation_turns("jasmine")
    # This account's uncertain past never narrows another account's history.
    assert len(ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="other_owner")) == 3


def test_legacy_unknown_provenance_survives_copying_before_forget(store: SQLiteStore) -> None:
    store.create_session("legacy", "/w", title="Trial tea")
    _exchange(store, "legacy", "legacy_turn", "trial tea", "Jasmine green tea")
    _context_event(store, "legacy", {"source_types": ["memory_recall"], "recalled_memory_ids": []})
    item = ContextGatherer()._memory_recall(store, "trial tea", "copy", "principal_owner")
    assert item is not None
    bundle = ContextGatherer()._apply_budget([item], session_id="copy", turn_id="copy_turn", max_items=20, max_chars=12000)
    assert bundle.event_payload()["memory_provenance_complete"] is False
    store.create_session("copy", "/w")
    _context_event(store, "copy", bundle.event_payload())
    store.delete_session("legacy")
    assert store.sessions_with_untracked_memory_context(["copy"]) == {"copy"}


@pytest.mark.parametrize("damage", ["path", "offset", "hash", "missing_ledger", "limit", "size"])
def test_indeterminate_context_provenance_fails_closed(store: SQLiteStore, tmp_path: Path, damage: str) -> None:
    store.create_session("chat", "/w")
    payload = {"source_types": ["memory_recall"], "recalled_memory_ids": [], "recalled_session_ids": [], "memory_provenance_version": 1, "memory_provenance_complete": True}
    if damage == "missing_ledger":
        payload["recalled_memory_ids"] = ["purged_memory"]
    elif damage == "size":
        payload["oversize"] = "x" * 65536
    _context_event(store, "chat", payload)
    if damage in {"path", "offset", "hash"}:
        column, value = {"path": ("jsonl_path", str(tmp_path / "outside.jsonl")), "offset": ("jsonl_offset", -1), "hash": ("payload_sha256", "bad")}[damage]
        with store.connect() as connection:
            connection.execute(f"UPDATE events_index SET {column} = ? WHERE session_id = ?", (value, "chat"))
    elif damage == "limit":
        for _ in range(64):
            _context_event(store, "chat", payload)
    assert store.sessions_with_untracked_memory_context(["chat"]) == {"chat"}


def test_indirect_provenance_only_follows_sessions_inside_the_build_project(store: SQLiteStore, tmp_path: Path) -> None:
    from raiker.context.gatherer import RetrievalScope
    from raiker.memory.store import MemoryGovernance, write_memory

    for project in ["alpha", "beta"]:
        store.create_project(project, project, project)
        store.create_session(project + "_chat", "/w", title="Trial tea")
        assert store.set_session_project(project + "_chat", project)
        _exchange(store, project + "_chat", project + "_turn", "trial tea", "An unrelated discussion")
    entry = write_memory(
        "A beta project preference", workspace_root=tmp_path, scope="project:beta", store=store,
        governance=MemoryGovernance("event", "beta_chat", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    item = ContextGatherer()._memory_recall(store, "trial tea", "current", "principal_owner", RetrievalScope("build", "alpha"))
    assert item is not None
    assert item.metadata["session_ids"] == ["alpha_chat"]
    inherited = item.metadata["inherited_memory_ids"]
    assert isinstance(inherited, list)
    assert entry.memory_id not in inherited


@pytest.mark.parametrize("change", ["forgotten", "corrected", "purged"])
@pytest.mark.parametrize("depth", [1, 3])
def test_known_session_edges_reach_memory_created_only_after_copying(
    store: SQLiteStore, tmp_path: Path, change: str, depth: int,
) -> None:
    from raiker.memory.store import MemoryGovernance, write_memory

    store.create_session("source_late", "/w", title="Trial tea")
    _exchange(store, "source_late", "source_turn", "trial tea", "Jasmine green tea")
    parent = "source_late"
    for index in range(depth):
        child = f"child_late_{index}"
        store.create_session(child, "/w", title="Trial tea")
        _exchange(store, child, child + "_turn", "trial tea", "Jasmine green tea")
        _context_event(store, child, {"source_types": ["memory_recall"], "recalled_memory_ids": [], "recalled_session_ids": [parent], "memory_provenance_version": 1, "memory_provenance_complete": True, "recalled_session_scope": {"surface": "chat", "project_id": ""}})
        parent = child
    store.create_session("unrelated_late", "/w", title="Trial tea")
    _exchange(store, "unrelated_late", "unrelated_late_turn", "trial tea", "An unrelated discussion")
    entry = write_memory(
        "My trial tea is jasmine green tea.", workspace_root=tmp_path, scope="account", store=store,
        governance=MemoryGovernance("event", "source_late", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"),
        owner_principal_id="principal_owner",
    )
    if change == "forgotten":
        store.mark_approved_memory_forgotten(entry.memory_id, deleted_at=entry.created_at, updated_at=entry.created_at, owner_principal_id="principal_owner")
    elif change == "corrected":
        store.record_memory_lifecycle_event(entry.memory_id, "edit", "principal_owner")
    else:
        store.delete_approved_memory(entry.memory_id, owner_principal_id="principal_owner")
    # Restrict candidates to the final child: source sessions need not match
    # the current search/recent budget for their dependency to remain binding.
    assert store.sessions_with_stale_memory_context([parent], owner_principal_id="principal_owner") == {parent}
    recalled = ContextGatherer()._recalled_sessions(store, "trial tea", "current", None, owner_principal_id="principal_owner")
    assert {row["session_id"] for row in recalled} == {"unrelated_late"}
    assert store.search_conversation_turns("jasmine")
