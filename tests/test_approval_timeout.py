"""QUI-P06 — an unanswered approval expires after the owner's time limit."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore
from raiker.storage.stores.approvals import DEFAULT_APPROVAL_TIMEOUT_MINUTES
from tests.factories import tool_action


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _lifetime_minutes(store: SQLiteStore, approval_id: str) -> float:
    row = store.load_approval(approval_id)
    assert row is not None
    created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    return (expires - created).total_seconds() / 60


def _raise(store: SQLiteStore, owner: str, *, critical: bool = False) -> str:
    store.create_session("sess_a", "ws")
    action = tool_action(
        "write_file",
        {"path": "notes.txt", "text": "hi"},
        action_id="act_1",
        risk_level="high",
        requires_approval=True,
        proposed_by=owner,
    )
    store.insert_tool_action(action, session_id="sess_a", turn_id="turn_a", status="approval_required")
    store.insert_approval("appr_1", action, critical=critical)
    return "appr_1"


def test_default_time_limit_is_thirty_minutes(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    assert DEFAULT_APPROVAL_TIMEOUT_MINUTES == 30
    approval_id = _raise(store, "principal_owner")
    assert _lifetime_minutes(store, approval_id) == 30


def test_owner_setting_sets_the_time_limit(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    store.put_user_settings(
        "principal_owner", json.dumps({"security.approval_timeout_minutes": 60}), utc_now()
    )
    approval_id = _raise(store, "principal_owner")
    assert _lifetime_minutes(store, approval_id) == 60


def test_value_outside_the_choices_reads_as_the_default(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    store.put_user_settings(
        "principal_owner", json.dumps({"security.approval_timeout_minutes": 7}), utc_now()
    )
    assert store.approval_timeout_minutes("principal_owner") == 30


def test_critical_approval_keeps_its_own_lifecycle(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    approval_id = _raise(store, "principal_owner", critical=True)
    assert _lifetime_minutes(store, approval_id) == 24 * 60


def test_settings_route_refuses_an_unoffered_time_limit(workspace: Path) -> None:
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.put(
        "/api/settings", json={"settings": {"security.approval_timeout_minutes": 5}}, headers=headers
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == "invalid_approval_timeout"
    saved = client.put(
        "/api/settings", json={"settings": {"security.approval_timeout_minutes": 240}}, headers=headers
    )
    assert saved.status_code == 200, saved.text
