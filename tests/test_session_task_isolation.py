from __future__ import annotations

from raiker.contracts.ids import utc_now
from raiker.contracts.models import TaskRecord, User
from raiker.storage.sqlite import SQLiteStore


def _user(store: SQLiteStore, user_id: str) -> None:
    store.insert_user(
        User(
            user_id=user_id,
            display_name=user_id,
            email=None,
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )


def _task(store: SQLiteStore, task_id: str, session_id: str) -> None:
    store.insert_task(
        TaskRecord(
            task_id=task_id,
            session_id=session_id,
            title="t",
            objective="o",
            status="queued",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )


def test_list_sessions_scoped_by_user(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _user(store, "user_a")
    _user(store, "user_b")
    store.create_session("s_a", str(tmp_path), user_id="user_a")
    store.create_session("s_b", str(tmp_path), user_id="user_b")
    store.create_session("s_legacy", str(tmp_path))  # no user_id → shared

    a_ids = {s["session_id"] for s in store.list_sessions(user_id="user_a")}
    assert "s_a" in a_ids
    assert "s_legacy" in a_ids  # legacy remains visible
    assert "s_b" not in a_ids  # another account's session is hidden

    b_ids = {s["session_id"] for s in store.list_sessions(user_id="user_b")}
    assert "s_b" in b_ids
    assert "s_a" not in b_ids

    # No user filter → everything (back-compat).
    assert len(store.list_sessions()) == 3


def test_list_tasks_scoped_by_user(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    _user(store, "user_a")
    _user(store, "user_b")
    store.create_session("s_a", str(tmp_path), user_id="user_a")
    store.create_session("s_b", str(tmp_path), user_id="user_b")
    _task(store, "t_a", "s_a")
    _task(store, "t_b", "s_b")

    a_tasks = {t.task_id for t in store.list_tasks(user_id="user_a")}
    assert a_tasks == {"t_a"}
    b_tasks = {t.task_id for t in store.list_tasks(user_id="user_b")}
    assert b_tasks == {"t_b"}
