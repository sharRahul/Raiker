from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

import raiker.storage.sqlite as sqlite_module
from raiker.storage.sqlite import (
    SQLiteStore,
    cached_connection_count,
    close_cached_connections,
    connection_cache_ceiling,
    connection_cache_limit,
    invalidate_workspace_connections,
)


def _open_descriptors() -> int | None:
    """This process's open file descriptors, or ``None`` where unobservable.

    Linux exposes them as ``/proc/self/fd``. The bound this asserts is the
    point of BUG-50, so where the count cannot be read the caller falls back to
    the cache size — the thing that was actually unbounded.
    """
    if not sys.platform.startswith("linux"):
        return None
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return None


def test_worker_reuses_one_keyed_connection_for_a_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalidate_workspace_connections(tmp_path)
    real_connect = sqlite_module.sqlite3.connect
    opened = 0

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting_connect)

    first = SQLiteStore(tmp_path)
    second = SQLiteStore(tmp_path)
    assert first.table_names()
    assert second.table_names()

    assert opened == 1


def test_workspace_invalidation_closes_and_rekeys_on_next_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalidate_workspace_connections(tmp_path)
    real_connect = sqlite_module.sqlite3.connect
    opened = 0

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting_connect)
    store = SQLiteStore(tmp_path)
    assert store.table_names()
    assert opened == 1

    invalidate_workspace_connections(tmp_path)
    assert store.table_names()
    assert opened == 2


def test_many_workspaces_do_not_grow_the_cache_or_the_descriptor_count(
    tmp_path: Path,
) -> None:
    """BUG-50 — opening far more workspaces than the limit stays bounded.

    Before the bound, opening 50 workspaces in one process raised its open
    descriptors from 4 to 154 and released none of them.
    """
    close_cached_connections()
    limit = connection_cache_limit()
    baseline = _open_descriptors()

    workspaces = limit * 6 + 2
    for index in range(workspaces):
        workspace = tmp_path / f"workspace_{index}"
        workspace.mkdir()
        assert SQLiteStore(workspace).table_names()
        assert cached_connection_count() <= limit

    assert cached_connection_count() <= limit
    after = _open_descriptors()
    if baseline is not None and after is not None:
        # Each cached connection costs a handful of descriptors; the assertion
        # that matters is that the count tracks the *limit* and not the number
        # of workspaces the process has ever opened.
        assert after - baseline <= limit * 6
    close_cached_connections()


def test_eviction_keeps_the_warm_workspace_and_drops_the_stalest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIXED-91's property survives the bound for a workspace still in use."""
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "2")

    warm = tmp_path / "warm"
    warm.mkdir()
    warm_store = SQLiteStore(warm)
    assert warm_store.table_names()

    real_connect = sqlite_module.sqlite3.connect
    opened = 0

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting_connect)

    # Touch the warm workspace between each cold one, so it is never the least
    # recently used entry and never the one evicted.
    for index in range(6):
        cold = tmp_path / f"cold_{index}"
        cold.mkdir()
        assert SQLiteStore(cold).table_names()
        assert warm_store.table_names()

    assert cached_connection_count() <= 2
    # Six cold workspaces opened; the warm one never paid key derivation again.
    assert opened == 6
    close_cached_connections()


def test_a_threadpool_does_not_multiply_the_bound_by_its_worker_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ceiling is process-wide, not per thread.

    A request threadpool serving many instance workspaces is the case BUG-50
    names. Each worker only ever evicts its own handles, so the allowance a
    thread gives itself has to shrink as more threads take up the cache.
    """
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "2")
    ceiling = connection_cache_ceiling()

    workers = 8
    per_worker = 6
    barrier = threading.Barrier(workers)
    failures: list[BaseException] = []

    def serve(worker: int) -> None:
        try:
            barrier.wait(timeout=30)
            for index in range(per_worker):
                workspace = tmp_path / f"w{worker}_{index}"
                workspace.mkdir(exist_ok=True)
                assert SQLiteStore(workspace).table_names()
        except BaseException as exc:  # noqa: BLE001 - reported through the assert below
            failures.append(exc)

    threads = [threading.Thread(target=serve, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert failures == []
    # Every worker touched six distinct workspaces — 48 in all — and the process
    # holds no more than the ceiling.
    assert cached_connection_count() <= ceiling
    close_cached_connections()


def test_a_dead_thread_does_not_keep_its_workspace_handle_open(tmp_path: Path) -> None:
    """Thread churn must not walk the bound upwards."""
    close_cached_connections()
    workspace = tmp_path / "worker_workspace"
    workspace.mkdir()

    def open_it() -> None:
        assert SQLiteStore(workspace).table_names()

    worker = threading.Thread(target=open_it)
    worker.start()
    worker.join()
    assert cached_connection_count() == 1

    # The next connect from a live thread reaps the exited worker's handle.
    other = tmp_path / "main_workspace"
    other.mkdir()
    assert SQLiteStore(other).table_names()
    assert cached_connection_count() == 1
    close_cached_connections()


def test_one_thread_never_closes_another_live_thread_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eviction is per thread because ``connect`` has no release point."""
    close_cached_connections()
    monkeypatch.delenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", raising=False)
    held = tmp_path / "held"
    held.mkdir()

    opened = threading.Event()
    release = threading.Event()
    still_usable: list[bool] = []

    def hold_open() -> None:
        connection = SQLiteStore(held).connect()
        opened.set()
        release.wait(timeout=10)
        try:
            connection.execute("SELECT 1")
            still_usable.append(True)
        except Exception:
            still_usable.append(False)

    worker = threading.Thread(target=hold_open)
    worker.start()
    assert opened.wait(timeout=10)

    for index in range(connection_cache_limit() * 3):
        workspace = tmp_path / f"main_{index}"
        workspace.mkdir()
        assert SQLiteStore(workspace).table_names()

    release.set()
    worker.join(timeout=10)
    assert still_usable == [True]
    close_cached_connections()
