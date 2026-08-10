"""BUG-86 — locked memory must bound the keyed-connection population, and a
store that will not open must say so instead of failing sign-in generically.

The reproduction on Linux was: ``ulimit -l`` of 8 MB, a request threadpool
minting one key-bearing SQLCipher connection per worker thread, and eventually
``MemoryError`` out of ``connect`` on *every* request — because authentication
opens the store. The screen then told the owner verification had failed while
its own status strip called the runtime operational.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

import raiker.storage.sqlite as sqlite_module
from raiker.storage.sqlite import (
    SQLiteStore,
    StoreUnavailableError,
    cached_connection_count,
    close_cached_connections,
    connection_cache_ceiling,
    connection_cache_limit,
    memory_security_posture,
    resolve_memory_security,
    store_health,
)


def test_the_ceiling_is_an_absolute_connection_count_not_a_thread_multiple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bound on key-bearing connections cannot depend on the thread count.

    Before the fix the ceiling was the per-thread limit times eight, so the real
    population grew with whatever the server's threadpool happened to be — and
    each of those connections spends the process's locked-memory allowance.
    """
    monkeypatch.delenv("RAIKER_SQLITE_CONNECTION_CACHE_CEILING", raising=False)
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "8")
    assert connection_cache_ceiling() == sqlite_module._DEFAULT_CONNECTION_CACHE_CEILING
    # Raising the per-thread limit alone must not raise the process ceiling
    # above what was declared for the process.
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_CEILING", "6")
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "2")
    assert connection_cache_ceiling() == 6
    # A ceiling below the per-thread limit would contradict itself; the limit
    # is the floor.
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "9")
    assert connection_cache_ceiling() == 9


def test_a_threadpool_stays_under_the_declared_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "4")
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_CEILING", "6")
    barrier = threading.Barrier(6)
    failures: list[BaseException] = []

    def serve(worker: int) -> None:
        try:
            barrier.wait(timeout=30)
            for index in range(4):
                workspace = tmp_path / f"w{worker}_{index}"
                workspace.mkdir(exist_ok=True)
                assert SQLiteStore(workspace).table_names()
        except BaseException as exc:  # noqa: BLE001 - reported through the assert
            failures.append(exc)

    threads = [threading.Thread(target=serve, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert failures == []
    assert cached_connection_count() <= 6
    close_cached_connections()


def test_memory_security_is_off_unless_the_owner_asks_for_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decision is stated, and the default is the cheap, openable one.

    Locking key pages costs roughly seven times on every store operation, and
    when the platform's allowance runs out the failure is a total lockout at
    sign-in rather than slow work — which is exactly BUG-86. So Raiker does not
    lock by default, says which posture it is on, and honours an owner who asks
    for the other one.
    """
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    assert resolve_memory_security(refresh=True) == (
        False,
        "default_off_cost_and_lockout_risk",
    )

    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    assert resolve_memory_security(refresh=True) == (True, "requested_on")
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    assert resolve_memory_security(refresh=True) == (False, "requested_off")

    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    resolve_memory_security(refresh=True)
    posture = memory_security_posture()
    assert posture["cipher_memory_security"] == "off"
    assert posture["memory_security_reason"] == "default_off_cost_and_lockout_risk"
    # The allowance is reported so an owner deciding whether to turn it on can
    # see what this platform would actually give them. -1 is unlimited; None is
    # a platform that will not say.
    assert "memlock_allowance_bytes" in posture
    resolve_memory_security(refresh=True)


def test_the_pragma_is_set_explicitly_and_defaults_to_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set on every connection, so the posture never depends on the build.

    Read back from the connection rather than timed: the cost is real — 0.17 s
    against 1.14 s for a bootstrap plus two hundred reads — but a stopwatch is
    not a property a test should rest on.
    """
    close_cached_connections()
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    resolve_memory_security(refresh=True)
    store = SQLiteStore(tmp_path)
    assert str(store.connect().execute("PRAGMA cipher_memory_security").fetchone()[0]) == "0"

    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    resolve_memory_security(refresh=True)
    locked = SQLiteStore(tmp_path)
    assert str(locked.connect().execute("PRAGMA cipher_memory_security").fetchone()[0]) == "1"

    close_cached_connections()
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    resolve_memory_security(refresh=True)


def test_a_refused_lock_fails_closed_by_name_when_the_owner_demanded_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``=on`` is the owner's decision, so it is honoured and named, not eroded."""
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    assert resolve_memory_security(refresh=True) == (True, "requested_on")

    def refusing_open(_self: SQLiteStore) -> Any:
        raise MemoryError("cannot allocate locked pages")

    monkeypatch.setattr(SQLiteStore, "_open_keyed", refusing_open)
    with pytest.raises(StoreUnavailableError) as raised:
        SQLiteStore(tmp_path)
    assert raised.value.reason == "store_memory_lock_unavailable"
    # The message names the machine, what it refused, and the setting that
    # asked for it — not "verification".
    assert "lock the memory pages" in raised.value.detail
    assert "RAIKER_SQLCIPHER_MEMORY_SECURITY=on" in raised.value.detail
    close_cached_connections()
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    resolve_memory_security(refresh=True)


def test_store_health_reports_the_unopenable_store_rather_than_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    close_cached_connections()
    assert store_health(tmp_path)["store"] == "ok"

    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    resolve_memory_security(refresh=True)

    def refusing_open(_self: SQLiteStore) -> Any:
        raise MemoryError("cannot allocate locked pages")

    monkeypatch.setattr(SQLiteStore, "_open_keyed", refusing_open)
    close_cached_connections()
    view = store_health(tmp_path)
    assert view["store"] == "unavailable"
    assert view["reason"] == "store_memory_lock_unavailable"
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    resolve_memory_security(refresh=True)


def test_a_cached_handle_that_lost_its_key_pages_is_replaced_not_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe on a cached handle answered MemoryError in the field log.

    Only ``sqlite3.Error`` was caught, so the failure escaped ``connect`` and
    every request in that worker failed from then on.
    """
    close_cached_connections()
    store = SQLiteStore(tmp_path)
    live = store.connect()

    class Exhausted:
        def execute(self, _sql: str) -> Any:
            raise MemoryError("locked pages reclaimed")

        def close(self) -> None:
            return None

    key = (store.paths.workspace_root, threading.get_ident())
    with sqlite_module._CONNECTIONS_LOCK:
        sqlite_module._CONNECTIONS[key] = Exhausted()  # type: ignore[assignment]

    replacement = store.connect()
    assert not isinstance(replacement, Exhausted)
    assert replacement.execute("SELECT 1").fetchone()[0] == 1
    assert live is not None
    close_cached_connections()


def test_the_limit_still_bounds_one_threads_workspaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLITE_CONNECTION_CACHE_LIMIT", "3")
    for index in range(connection_cache_limit() * 4):
        workspace = tmp_path / f"ws_{index}"
        workspace.mkdir()
        assert SQLiteStore(workspace).table_names()
        assert cached_connection_count() <= connection_cache_limit()
    close_cached_connections()
