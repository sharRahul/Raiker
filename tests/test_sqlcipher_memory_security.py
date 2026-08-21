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
import os
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

    BUG-205 — this used to read the pragma back and demand ``0``. That is not a
    property the platform offers: ``cipher_memory_security`` is process-global in
    the bundled SQLCipher build and latches one way, so any earlier test in the
    same process that enabled it leaves this reading ``1`` however many fresh
    connections and fresh workspaces come after. The assertion here is therefore
    what *is* per-connection and what *is* Raiker's to guarantee: the exact
    statement it issues, before the key is derived. The read-back is asserted
    below, in a process that has never enabled the pragma.
    """
    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)

    issued: list[str] = []
    real_connect = sqlite_module.sqlite3.connect

    def recording_connect(*args: Any, **kwargs: Any) -> Any:
        connection = real_connect(*args, **kwargs)
        # The driver's own statement trace, because the connection object refuses
        # attribute assignment. Key material is never retained — only that a key
        # was set, and where in the order it happened.
        connection.set_trace_callback(
            lambda statement: issued.append(
                "PRAGMA key = <redacted>"
                if statement.startswith("PRAGMA key =")
                else statement
            )
        )
        return connection

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", recording_connect)
    store = SQLiteStore(tmp_path)
    store.connect()
    monkeypatch.undo()

    pragmas = [statement for statement in issued if "cipher_memory_security" in statement]
    assert pragmas, "no memory-security pragma was issued on a keyed connection"
    assert all(statement == "PRAGMA cipher_memory_security = OFF" for statement in pragmas)
    # And it is issued *before* the key, because the pragma governs how the key
    # material about to be derived is held.
    first_pragma = next(i for i, s in enumerate(issued) if "cipher_memory_security" in s)
    first_key = next(i for i, s in enumerate(issued) if s.startswith("PRAGMA key ="))
    assert first_pragma < first_key

    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)


def test_a_process_that_never_enabled_the_pragma_really_reads_it_back_off(
    tmp_path: Path,
) -> None:
    """The read-back assertion the test above cannot make in a shared process.

    Run in a pristine interpreter with the variable unset, so it measures the
    platform rather than the order the suite happened to run in (BUG-205). This
    is the check that would catch Raiker silently opening keyed connections with
    memory security on when the owner asked for it off.
    """
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from raiker.storage.sqlite import SQLiteStore, resolve_memory_security\n"
        "assert resolve_memory_security(refresh=True) == (False, 'requested_off'), 'unexpected posture'\n"
        "store = SQLiteStore(Path(sys.argv[1]))\n"
        "print(store.connect().execute('PRAGMA cipher_memory_security').fetchone()[0])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "RAIKER_SQLCIPHER_MEMORY_SECURITY": "off"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0", result.stdout


def test_the_posture_reports_the_pragma_in_force_not_only_the_one_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A latched process must not report ``off`` while every connection is ``on``.

    BUG-205 — the latch sticks only in the safe direction, so this can never
    understate protection. It can overstate a *change*: an owner who set the
    variable to ``off`` and restarted nothing would otherwise read ``off`` on the
    health surface while the process kept locking pages. Health says which of the
    two it is.
    """
    close_cached_connections()
    monkeypatch.setattr(sqlite_module, "probe_memory_security", lambda root: _supported_probe())
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "on")
    resolve_memory_security(refresh=True)
    # The latch is the unit under test. Do not execute an ON pragma against a
    # platform whose real child-process probe returned ``host_crash``: forcing
    # the native SQLCipher library past that refusal terminates pytest itself on
    # Windows instead of testing the posture dictionary.
    monkeypatch.setattr(sqlite_module, "_MEMORY_SECURITY_EVER_ENABLED", True)
    assert sqlite_module.memory_security_ever_enabled() is True

    close_cached_connections()
    monkeypatch.setenv("RAIKER_SQLCIPHER_MEMORY_SECURITY", "off")
    resolve_memory_security(refresh=True)
    posture = memory_security_posture()
    # What the owner asked for, and — separately — what the process is doing.
    assert posture["cipher_memory_security"] == "off"
    assert posture["memory_security_reason"] == "requested_off"
    assert posture["memory_security_in_force"] == "on"

    close_cached_connections()
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
