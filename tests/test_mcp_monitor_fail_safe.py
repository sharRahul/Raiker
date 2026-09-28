"""CR-10 — an MCP monitor that cannot look stops the connection, not the session.

``McpConnectorExecutor._observe`` used to swallow every exception from the
monitor and carry on. The monitor is not only telemetry: its findings trip the
auto-pause circuit breaker. A monitor that raised was a containment control that
had stopped running, and the connection went on as though it had not.

What these tests pin:

- the session that was already run still reports what happened — a monitoring
  failure is not retroactively a session failure;
- the connection is paused with a reason the MCP card shows, and a notification,
  exactly as a high-severity finding would pause it, and the owner's Resume
  reopens it;
- when the pause cannot be written either, the connection is held in-process
  and refused with ``mcp_monitor_unavailable`` until the monitor's own read
  answers again, and then it runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raiker.runtime.executors import mcp as mcp_executor
from raiker.runtime.executors.mcp import McpConnectorExecutor
from raiker.security.mcp_monitor import McpContainment
from raiker.storage.sqlite import SQLiteStore
from tests.test_mcp_containment import _action, _build_echo_server, _principal, _row_by_name, _ws


class _BrokenMonitor:
    def __init__(self) -> None:
        self.calls = 0

    def observe(self, telemetry: Any) -> list[Any]:
        self.calls += 1
        raise RuntimeError("finding store unavailable")


@pytest.fixture(autouse=True)
def _no_leftover_holds() -> Any:
    yield
    with mcp_executor._UNMONITORED_LOCK:
        mcp_executor._UNMONITORED.clear()


def _connect(connector: McpConnectorExecutor, rel: str) -> Any:
    return connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )


def test_an_unmonitored_session_pauses_its_connection(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    # A healthy first session records the connection profile.
    assert _connect(McpConnectorExecutor(ws, store), rel).ok is True

    broken = McpConnectorExecutor(ws, store, monitor=_BrokenMonitor())  # type: ignore[arg-type]
    session = _connect(broken, rel)
    # The session itself happened and says so.
    assert session.ok is True, session.reason_code

    server = _row_by_name(store, "echo")
    assert server["monitor_state"] == "paused"
    assert server["paused_reason"] == mcp_executor.MONITOR_UNAVAILABLE_REASON
    kinds = [n["kind"] for n in store.list_notifications("principal_owner")]
    assert "connection_paused" in kinds

    # The next session does not run until the owner resumes.
    refused = _connect(McpConnectorExecutor(ws, store), rel)
    assert refused.ok is False
    assert refused.reason_code == "mcp_connection_paused"

    McpContainment(store).resume("principal_owner", server["server_id"], source="owner")
    assert _connect(McpConnectorExecutor(ws, store), rel).ok is True


def test_when_the_pause_cannot_be_written_the_connection_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    assert _connect(McpConnectorExecutor(ws, store), rel).ok is True

    def _cannot_write(*args: Any, **kwargs: Any) -> bool:
        raise RuntimeError("store is read-only")

    monkeypatch.setattr(store, "set_mcp_monitor_state", _cannot_write)
    broken = McpConnectorExecutor(ws, store, monitor=_BrokenMonitor())  # type: ignore[arg-type]
    assert _connect(broken, rel).ok is True

    # The monitor's own read is still failing: refused, and the reason says why.
    def _cannot_read(*args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError("store unreadable")

    monkeypatch.setattr(store, "list_mcp_session_logs", _cannot_read)
    refused = _connect(McpConnectorExecutor(ws, store), rel)
    assert refused.ok is False
    assert refused.reason_code == "mcp_monitor_unavailable"

    # The read answers again: the hold lifts and the session runs, observed.
    monkeypatch.undo()
    assert _connect(McpConnectorExecutor(ws, store), rel).ok is True
    assert not mcp_executor._UNMONITORED


def test_a_healthy_monitor_holds_nothing(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    assert _connect(connector, rel).ok is True
    assert _connect(connector, rel).ok is True
    assert _row_by_name(store, "echo")["monitor_state"] == "active"
    assert not mcp_executor._UNMONITORED


def test_one_workspaces_hold_does_not_reach_another(tmp_path: Path) -> None:
    mcp_executor._hold_unmonitored(tmp_path / "a", "principal_owner", "mcp_1")
    assert mcp_executor._is_unmonitored(tmp_path / "a", "principal_owner", "mcp_1")
    assert not mcp_executor._is_unmonitored(tmp_path / "b", "principal_owner", "mcp_1")
