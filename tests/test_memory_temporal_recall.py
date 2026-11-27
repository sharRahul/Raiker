"""Hindsight's fourth leg: recall by when something was learned."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.memory.temporal import query_window
from raiker.storage.sqlite import SQLiteStore

NOW = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("query", "start", "end"),
    [
        ("what did I say yesterday", "2026-11-26", "2026-11-27"),
        ("anything from last week?", "2026-11-16", "2026-11-23"),
        ("notes from 2026-11-02", "2026-11-02", "2026-11-03"),
        ("what happened in March", "2026-03-01", "2026-04-01"),
        ("past 3 days", "2026-11-24", "2026-11-27"),
        ("last month", "2026-10-01", "2026-11-01"),
    ],
)
def test_time_phrases_become_windows(query: str, start: str, end: str) -> None:
    window = query_window(query, NOW)
    assert window is not None
    assert (window[0].date().isoformat(), window[1].date().isoformat()) == (start, end)


def test_a_query_without_a_time_has_no_window() -> None:
    assert query_window("which tea do I like", NOW) is None


def test_recall_finds_what_was_learned_today_with_no_shared_word(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    owner = "principal_owner"
    store = SQLiteStore(ws)
    write_memory(
        "The plumber comes Thursday", workspace_root=ws, scope="user", store=store,
        owner_principal_id=owner,
        governance=MemoryGovernance("e", "s", None, "human_correction", 1.0, 1.0, "until_forget", "approved", owner),
    )
    results = retrieve_hybrid_memory(store=store, query="what did I tell you today?", owner_principal_id=owner)
    assert [(item.text, "temporal" in item.sources) for item in results] == [("The plumber comes Thursday", True)]
