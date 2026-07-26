"""Workstream D / Slice D2 — asynchronous approval notifications.

Approvals never block a flow: parking a turn for approval delivers an owner-facing
notification (dashboard notification-center row + optional OS-level hook) so the
owner can approve from any surface. These tests pin:

* an approval created through the broker inserts an owner-scoped notification;
* the owner is resolved correctly (AI/automation → the instance owner account);
* the OS-level hook is env-gated and off by default (never fires uninvited);
* notification copy is metadata-only (tool name + risk, never the arguments).
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.notify import (
    fire_os_notification,
    notify_approval_pending,
    resolve_owner_principal_id,
)
from raiker.notify.approval_notifier import OS_NOTIFY_ENV
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(_ws(tmp_path))


def test_resolve_owner_falls_back_to_instance_owner(store: SQLiteStore) -> None:
    # An AI/automation principal id is not an account; the owner is the instance
    # owner account.
    assert resolve_owner_principal_id(store, "ai_worker") == "principal_owner"


def test_notify_approval_pending_inserts_owner_notification(store: SQLiteStore) -> None:
    notification_id = notify_approval_pending(
        store,
        acting_principal_id="ai_worker",
        approval_id="appr_123",
        tool_name="write_file",
        risk_level="low",
    )
    assert notification_id is not None
    rows = store.list_notifications("principal_owner")
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "approval_pending"
    assert row["subject_id"] == "appr_123"
    # metadata-only copy: mentions the tool name, never the arguments
    assert "write_file" in row["body"]
    assert row["read"] == 0


def test_notify_is_skipped_when_no_owner(tmp_path: Path) -> None:
    # No bootstrapped account → no owner to notify → skipped, not an error.
    ws = tmp_path / "empty"
    ws.mkdir()
    store = SQLiteStore(ws)
    assert notify_approval_pending(
        store, acting_principal_id=None, approval_id="appr_1", tool_name="write_file"
    ) is None


def test_broker_approval_delivers_notification(tmp_path: pytest.TempPathFactory) -> None:
    """A parked approval created through the broker notifies the owner (D2)."""
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import ToolAction
    from raiker.events.writer import EventLogWriter
    from raiker.policy.config import StaticPolicyConfig
    from raiker.policy.engine import PolicyEngine
    from raiker.tools.broker import ToolBroker

    ws = _ws(tmp_path)  # type: ignore[arg-type]
    store = SQLiteStore(ws)
    broker = ToolBroker(
        workspace_root=ws,
        policy_engine=PolicyEngine(StaticPolicyConfig(ws)),
        store=store,
        writer=EventLogWriter(store),
    )
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "shell", {"command": "echo hi"}, "high", True),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
    )
    assert decision.decision == "needs_approval"
    rows = store.list_notifications("principal_owner", unread_only=True)
    assert len(rows) == 1
    assert rows[0]["kind"] == "approval_pending"


def test_os_notification_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OS_NOTIFY_ENV, raising=False)
    assert fire_os_notification("Approval needed", "body") is False


def test_os_notification_fires_when_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "fired.txt"
    # A harmless owner-configured command that records that it ran. Title/body are
    # appended after the marker and ignored by the Python snippet.  Using the
    # current interpreter keeps this hook-contract test portable on Windows.
    command = shlex.join(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
        ]
    )
    monkeypatch.setenv(OS_NOTIFY_ENV, command)
    assert fire_os_notification("Approval needed", "body") is True
    assert marker.exists()
