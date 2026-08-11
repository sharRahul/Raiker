"""BUG-86 — locked memory must bound the keyed-connection population, and a
store that will not open must say so instead of failing sign-in generically.

The reproduction on Linux was: ``ulimit -l`` of 8 MB, a request threadpool
minting one key-bearing SQLCipher connection per worker thread, and eventually
``MemoryError`` out of ``connect`` on *every* request — because authentication
opens the store. The screen then told the owner verification had failed while
its own status strip called the runtime operational.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

import raiker.storage.sqlite as sqlite_module
from raiker.storage.sqlcipher_probe import MemorySecurityProbeResult, probe_memory_security
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


def _supported_probe() -> MemorySecurityProbeResult:
    return MemorySecurityProbeResult(True, "supported", "4.12.0", "2026-08-11T00:00:00Z")


@pytest.fixture(autouse=True)
def _default_memory_security_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)


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


def test_memory_security_auto_enables_only_after_a_passing_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decision is stated, and the default is the cheap, openable one.

    Locking key pages costs roughly seven times on every store operation, and
    when the platform's allowance runs out the failure is a total lockout at
    sign-in rather than slow work — which is exactly BUG-86. So Raiker does not
    lock by default, says which posture it is on, and honours an owner who asks
    for the other one.
    """
    monkeypatch.setattr(sqlite_module, "probe_memory_security", lambda root: _supported_probe())
    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    assert resolve_memory_security(refresh=True) == (True, "auto_probe_supported")

    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    assert resolve_memory_security(refresh=True) == (True, "requested_on")
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    assert resolve_memory_security(refresh=True) == (False, "requested_off")

    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)
    posture = memory_security_posture()
    assert posture["cipher_memory_security"] == "off"
    assert posture["memory_security_reason"] == "requested_off"
    # The allowance is reported so an owner deciding whether to turn it on can
    # see what this platform would actually give them. -1 is unlimited; None is
    # a platform that will not say.
    assert "memlock_allowance_bytes" in posture
    resolve_memory_security(refresh=True)


def test_the_pragma_is_set_explicitly_to_off_without_an_unsafe_parent_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Set on every connection, so the posture never depends on the build.

    Read back from the connection rather than timed: the cost is real — 0.17 s
    against 1.14 s for a bootstrap plus two hundred reads — but a stopwatch is
    not a property a test should rest on.
    """
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)
    store = SQLiteStore(tmp_path)
    assert str(store.connect().execute("PRAGMA cipher_memory_security").fetchone()[0]) == "0"

    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)


def test_a_refused_lock_fails_closed_by_name_when_the_owner_demanded_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``=on`` is the owner's decision, so it is honoured and named, not eroded."""
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    monkeypatch.setattr(sqlite_module, "probe_memory_security", lambda root: _supported_probe())
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
    monkeypatch.setattr(sqlite_module, "probe_memory_security", lambda root: _supported_probe())
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


def test_probe_maps_windows_stack_overflow_without_crashing_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, -1073741571, "", ""),
    )

    result = probe_memory_security(tmp_path)

    assert result.supported is False
    assert result.reason_code == "host_crash"


def test_frozen_probe_uses_private_payload_files_instead_of_python_module_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        payload_path = Path(command[2])
        result_path = Path(command[3])
        assert payload_path.parent == result_path.parent
        assert "key" in json.loads(payload_path.read_text(encoding="utf-8"))
        result_path.write_text(
            json.dumps({"status": "supported", "sqlcipher_version": "4.6.1"}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(subprocess, "run", run)
    result = probe_memory_security(tmp_path)

    assert captured["command"][:2] == [sys.executable, "--sqlcipher-probe-worker"]
    assert "input" not in captured["kwargs"]
    assert result.supported is True


def test_probe_maps_timeout_without_exposing_child_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timed_out(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(args[0], timeout=1, output="probe-key", stderr="secret")

    monkeypatch.setattr(subprocess, "run", timed_out)

    result = probe_memory_security(tmp_path, timeout_seconds=1)

    assert result.supported is False
    assert result.reason_code == "probe_timeout"
    assert "probe-key" not in repr(result)
    assert "secret" not in repr(result)


def test_auto_and_required_modes_use_the_isolated_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = MemorySecurityProbeResult(False, "host_crash", "4.12.0", "2026-08-11T00:00:00Z")
    monkeypatch.setattr(sqlite_module, "probe_memory_security", lambda root: failed)

    monkeypatch.delenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", raising=False)
    assert resolve_memory_security(tmp_path, refresh=True) == (
        False,
        "auto_probe_host_crash",
    )
    posture = memory_security_posture(tmp_path)
    assert posture["memory_security_mode"] == "auto"
    assert posture["memory_security_probe"] == "failed"

    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    assert resolve_memory_security(tmp_path, refresh=True) == (
        False,
        "required_but_unavailable_host_crash",
    )


def test_explicit_off_bypasses_the_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    monkeypatch.setattr(
        sqlite_module,
        "probe_memory_security",
        lambda root: pytest.fail("explicit off must not launch the probe"),
    )

    assert resolve_memory_security(tmp_path, refresh=True) == (False, "requested_off")
