"""BUG-322 and DEC-24 step 6 — damaged search indexes, named where an owner looks.

FIXED-763 named a damaged text index, but only inside Diagnostics' fold and
only when somebody opened it. The check now runs on the host tick and records
its answer, the Overview's attention list reads that record, and the owner is
told once. A vector is a projection like a text index: one that cannot be read
was skipped by retrieval in silence; it is now counted, named and removable,
and the memory behind it becomes *not yet indexed* again.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.memory.integrity import inspect_memory_integrity
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.notify.index_notifier import INDEX_DAMAGED_KIND, notify_search_index_damaged
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text

GOVERNANCE = MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test")


def _memory_with_vector(store: SQLiteStore, root: Path, text: str, embedding: str) -> tuple[str, str]:
    memory = write_memory(text, workspace_root=root, scope="project:x", store=store, governance=GOVERNANCE)
    vector_id = new_id("vec_")
    store.insert_vector_record(
        VectorRecord(
            vector_id, VectorIndex.compute_content_hash(memory.text), memory.text,
            LOCAL_EMBEDDING_MODEL, 384, memory.scope, memory.sensitivity, utc_now(), embedding,
        )
    )
    store.link_memory_projection(memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL)
    return memory.memory_id, vector_id


def _damage_conversation_index(store: SQLiteStore) -> None:
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO conversation_fts (turn_id, session_id, role, text) "
            "VALUES ('turn_1', 'sess_1', 'user', 'hello damaged index')"
        )
    with store.connect() as connection:
        connection.execute("DELETE FROM conversation_fts_data WHERE id NOT IN (1, 10)")


def test_a_vector_that_is_not_its_own_dimensions_is_named(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _memory_with_vector(store, tmp_path, "A healthy memory.", json.dumps(embed_text("A healthy memory.", 384)))
    _, short = _memory_with_vector(store, tmp_path, "A truncated vector.", json.dumps([0.1, 0.2]))
    _, garbled = _memory_with_vector(store, tmp_path, "A garbled vector.", "[0.1, 0.2,")
    assert set(store.damaged_vector_ids()) == {short, garbled}
    report = inspect_memory_integrity(store=store, workspace_root=tmp_path)
    assert report.damaged_vector_count == 2
    assert not report.clean


def test_removing_damaged_vectors_leaves_the_memory_waiting_to_be_indexed(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    memory_id, damaged = _memory_with_vector(store, tmp_path, "A garbled vector.", "not json")
    healthy_memory, healthy = _memory_with_vector(
        store, tmp_path, "A healthy memory.", json.dumps(embed_text("A healthy memory.", 384))
    )
    assert store.remove_damaged_vectors() == 1
    assert store.damaged_vector_ids() == []
    assert store.get_vector_record(damaged) is None
    assert store.get_vector_record(healthy) is not None
    # The memory itself is untouched and is now what the index action embeds.
    assert store.get_active_approved_memory(memory_id) is not None
    missing = {row["memory_id"] for row in store.list_memories_missing_embedding(LOCAL_EMBEDDING_MODEL)}
    assert memory_id in missing and healthy_memory not in missing


def test_the_check_records_every_index_and_reports_new_damage_once(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert store.check_search_indexes() == []
    recorded = {row["index_name"]: row["state"] for row in store.list_search_index_health()}
    assert recorded == {name: "ok" for name in (*SQLiteStore.TEXT_INDEX_TABLES, "vector_records")}

    _damage_conversation_index(store)
    assert store.check_search_indexes() == [{"index_name": "conversation_fts", "damaged_count": 1}]
    # Still damaged on the next tick: recorded, not reported again.
    assert store.check_search_indexes() == []
    first = store.list_search_index_health()[0]
    assert first["index_name"] == "conversation_fts" and first["state"] == "damaged"
    assert first["first_damaged_at"]

    store.rebuild_text_indexes()
    store.check_search_indexes()
    assert all(row["state"] == "ok" for row in store.list_search_index_health())


def test_the_owner_is_told_in_words_with_the_index_named(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    notification_id = notify_search_index_damaged(store, "vector_records", 3)
    assert notification_id is not None
    [row] = [item for item in store.list_notifications("principal_owner") if item["kind"] == INDEX_DAMAGED_KIND]
    assert row["title"] == "Search by meaning needs repairing"
    assert "3 stored vectors could not be read" in row["body"]
    assert "vector_records" not in row["body"]


def test_diagnostics_carries_the_recorded_check(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    client = TestClient(create_app(tmp_path))
    token = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    store = SQLiteStore(tmp_path)
    _damage_conversation_index(store)
    store.check_search_indexes()
    indexes = client.get("/api/diagnostics", headers=headers).json()["search_indexes"]
    assert indexes[0] == {
        **indexes[0],
        "index_name": "conversation_fts",
        "label": "Conversation search",
        "state": "damaged",
    }
    repaired = client.post("/api/memory/text-indexes/rebuild", headers=headers)
    assert repaired.status_code == 200
    after = client.get("/api/diagnostics", headers=headers).json()["search_indexes"]
    assert all(row["state"] == "ok" for row in after)
    removed = client.post("/api/memory/vectors/remove-damaged", headers=headers).json()
    assert removed == {"ok": True, "removed": 0, "damaged_vector_count": 0}
