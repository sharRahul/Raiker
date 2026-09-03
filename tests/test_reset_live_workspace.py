"""BUG-266 — a reset that cannot complete must stop the round, not hide."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

from scripts.reset_live_workspace import (
    port_is_open,
    remove_workspace,
    reset,
    wait_for_port_release,
)


def test_a_round_starts_on_an_empty_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "round"
    (workspace / "nested").mkdir(parents=True)
    (workspace / "nested" / "raiker.db").write_text("previous round")
    assert reset(workspace, None) is None
    assert workspace.is_dir()
    assert list(workspace.iterdir()) == []


def test_a_removal_that_leaves_the_directory_behind_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact shape of BUG-266: no exception, and the data still there.

    The Windows case reported success and left the previous round's account in
    place. The answer has to come from the filesystem, not from the absence of an
    error.
    """
    workspace = tmp_path / "round"
    workspace.mkdir()
    (workspace / "raiker.db").write_text("previous round")
    monkeypatch.setattr("scripts.reset_live_workspace.shutil.rmtree", lambda _path: None)
    failure = remove_workspace(workspace, timeout=0.5)
    assert failure is not None
    assert "still exists" in failure
    assert (workspace / "raiker.db").exists()


def test_a_handle_that_clears_on_the_second_attempt_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lagging handle is normal; a first failure is not proof of a stuck one."""
    workspace = tmp_path / "round"
    workspace.mkdir()
    (workspace / "raiker.db").write_text("previous round")
    import shutil

    # Captured before the patch: `scripts.reset_live_workspace.shutil` is the
    # same module object, so patching through it replaces the real function too.
    remove = shutil.rmtree
    attempts = {"count": 0}

    def flaky(path: str | Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PermissionError("the store is still open")
        remove(path)

    monkeypatch.setattr("scripts.reset_live_workspace.shutil.rmtree", flaky)
    assert remove_workspace(workspace, timeout=5.0) is None
    assert not workspace.exists()
    assert attempts["count"] == 2


def _listening_host() -> tuple[socket.socket, int, threading.Event]:
    """A socket that actually accepts, so a probe sees what it would see live."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            connection.close()

    threading.Thread(target=serve, daemon=True).start()
    return listener, listener.getsockname()[1], stop


def test_a_host_that_is_still_listening_stops_the_reset(tmp_path: Path) -> None:
    """The HTTP response is not the evidence. The process exit is."""
    listener, port, stop = _listening_host()
    workspace = tmp_path / "round"
    workspace.mkdir()
    (workspace / "raiker.db").write_text("previous round")
    try:
        assert port_is_open(port)
        assert wait_for_port_release(port, timeout=1.0) is False
        failure = reset(workspace, port, timeout=1.0)
        assert failure is not None
        assert "still listening" in failure
        # The round's data is untouched, which is what makes the refusal safe.
        assert (workspace / "raiker.db").exists()
    finally:
        stop.set()
        listener.close()


def test_the_reset_waits_for_the_port_rather_than_failing_immediately() -> None:
    listener, port, stop = _listening_host()
    def release() -> None:
        stop.set()
        listener.close()

    threading.Timer(0.4, release).start()
    assert wait_for_port_release(port, timeout=10.0) is True
