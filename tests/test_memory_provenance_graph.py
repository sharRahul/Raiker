from __future__ import annotations

from pathlib import Path

import pytest

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.deletion_journal import (
    MEMORY_PURGE,
    journal_path,
    read_deletions,
    record_deletion,
)
from raiker.storage.sqlite import SQLiteStore
from tests.test_conversation_recall import _context_event, _exchange


def _complete(store: SQLiteStore, session: str, dependencies: list[str], *, scope: dict | None = None, padding: str = "") -> None:
    _context_event(store, session, {"source_types": ["memory_recall"], "recalled_memory_ids": [], "recalled_session_ids": dependencies, "memory_provenance_version": 1, "memory_provenance_complete": True, "recalled_session_scope": scope or {"surface": "chat", "project_id": ""}, "padding": padding})


def test_old_untraceable_purge_withholds_pre_purge_history_and_keeps_new_history(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    for session in ["old_source", "old_child", "new_clean"]:
        store.create_session(session, "/w")
        _exchange(store, session, session + "_turn", "trial tea", "Jasmine green tea")
        with store.connect() as connection:
            connection.execute("UPDATE sessions SET created_at = ? WHERE session_id = ?", ("2100-01-01T00:00:00Z" if session == "new_clean" else "2000-01-01T00:00:00Z", session))
    _complete(store, "old_child", ["old_source"])
    record_deletion(tmp_path, MEMORY_PURGE, "legacy_purge", "principal_owner")
    diagnostics: dict[str, object] = {}
    assert store.sessions_with_stale_memory_context(["old_source", "old_child", "new_clean"], owner_principal_id="principal_owner", diagnostics=diagnostics) == {"old_source", "old_child"}
    assert diagnostics["history_withheld_reason"] == "untraceable_legacy_memory_purge"
    assert store.sessions_with_stale_memory_context(["old_source", "old_child", "new_clean"], owner_principal_id="other_owner") == set()
    assert store.search_conversation_turns("jasmine")


@pytest.mark.parametrize("operation", ["forget", "purge"])
def test_future_memory_tombstone_preserves_only_owner_and_source_identity(tmp_path: Path, operation: str) -> None:
    store = SQLiteStore(tmp_path)
    entry = write_memory("PRIVATE_SENTINEL", workspace_root=tmp_path, scope="account", store=store, governance=MemoryGovernance("event", "source_session", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"), owner_principal_id="principal_owner")
    if operation == "forget":
        store.mark_approved_memory_forgotten(entry.memory_id, deleted_at=entry.created_at, updated_at=entry.created_at)
    else:
        store.delete_approved_memory(entry.memory_id)
    [deletion] = read_deletions(tmp_path)
    assert deletion.owner == "principal_owner"
    assert deletion.source_session_id == "source_session"
    assert "PRIVATE_SENTINEL" not in journal_path(tmp_path).read_text(encoding="utf-8")


def test_future_purge_source_provenance_survives_failed_journal_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteStore(tmp_path)
    for session in ["source", "child", "unrelated"]:
        store.create_session(session, "/w")
    _complete(store, "child", ["source"])
    entry = write_memory("PRIVATE_SENTINEL", workspace_root=tmp_path, scope="account", store=store, governance=MemoryGovernance("event", "source", None, "user_ui", 1.0, 1.0, "until_forget", "approved", "principal_owner"), owner_principal_id="principal_owner")
    monkeypatch.setattr("raiker.storage.stores.memory.record_deletion", lambda *_args, **_kwargs: None)
    store.delete_approved_memory(entry.memory_id)
    assert not journal_path(tmp_path).exists()
    assert store.sessions_with_stale_memory_context(["source", "child", "unrelated"], owner_principal_id="principal_owner") == {"source", "child"}
    assert store.sessions_with_stale_memory_context(["source", "child", "unrelated"], owner_principal_id="other_owner") == set()


@pytest.mark.parametrize("invalid", ["cycle", "deleted", "foreign", "project"])
def test_context_graph_treats_invalid_dependencies_as_indeterminate(tmp_path: Path, invalid: str) -> None:
    store = SQLiteStore(tmp_path)
    for session in ["child", "source", "unrelated"]:
        store.create_session(session, "/w")
    if invalid == "cycle":
        _complete(store, "source", ["child"])
    elif invalid == "deleted":
        store.delete_session("source")
    elif invalid == "foreign":
        with store.connect() as connection:
            connection.execute("INSERT INTO users (user_id,display_name,email,is_active,created_at,updated_at) VALUES ('foreign','Foreign','foreign@example.invalid',1,'2026-01-01','2026-01-01')")
            connection.execute("UPDATE sessions SET user_id='foreign' WHERE session_id='source'")
    else:
        store.create_project("alpha", "alpha", "alpha")
        store.create_project("beta", "beta", "beta")
        store.set_session_project("child", "alpha")
        store.set_session_project("source", "beta")
    _complete(store, "child", ["source"], scope={"surface": "build", "project_id": "alpha"} if invalid == "project" else None)
    assert store.sessions_with_untracked_memory_context(["child", "unrelated"]) == {"child"}


def test_context_graph_reads_shared_source_only_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("shared", "/w")
    _context_event(store, "shared", {"source_types": ["current_prompt"]})
    roots = [f"child_{index}" for index in range(20)]
    for session in roots:
        store.create_session(session, "/w")
        _complete(store, session, ["shared"])
    original_open = Path.open
    reads = 0

    def counted_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal reads
        if path == store.paths.events_dir / "shared.jsonl":
            reads += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    assert store.sessions_with_untracked_memory_context(roots) == set()
    assert reads == 1


@pytest.mark.parametrize("limit", ["nodes", "bytes"])
def test_context_graph_has_one_global_node_and_byte_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str) -> None:
    store = SQLiteStore(tmp_path)
    count = 130 if limit == "nodes" else 72
    for index in range(count):
        session = f"node_{index}"
        store.create_session(session, "/w")
        if index < count - 1:
            _complete(store, session, [f"node_{index + 1}"], padding="x" * 60000 if limit == "bytes" else "")
    original_open = Path.open
    bytes_read = 0

    class Counted:
        def __init__(self, handle):  # type: ignore[no-untyped-def]
            self.handle = handle

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return self.handle.__exit__(*args)

        def seek(self, offset):  # type: ignore[no-untyped-def]
            return self.handle.seek(offset)

        def readline(self, size):  # type: ignore[no-untyped-def]
            nonlocal bytes_read
            data = self.handle.readline(size)
            bytes_read += len(data)
            return data

    def counted_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        handle = original_open(path, *args, **kwargs)
        return Counted(handle) if path.parent == store.paths.events_dir else handle

    monkeypatch.setattr(Path, "open", counted_open)
    graph, uncertain = store._memory_context_graph(["node_0"])
    assert len(graph) <= 128
    assert bytes_read <= 4 * 1024 * 1024
    assert store._affected_memory_context_roots(["node_0"], graph, uncertain) == {"node_0"}
