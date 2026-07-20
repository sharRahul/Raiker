"""Workstream F / Slice F1 (ZT-3) — posture snapshot on every governed action.

A posture snapshot records "who was in control, on what session, how strongly
authenticated, and by what decision path" for every governed execution. These
tests pin that:

* an executed governed action's event carries a metadata-only posture snapshot;
* the snapshot includes the identity, interface, auth-strength, and decision-path
  (decision mode / grant used) fields F1 promises;
* the snapshot never carries a secret, token, or file content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.posture import capture_posture
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    return _ws(tmp_path)


@pytest.fixture
def store(ws: Path) -> SQLiteStore:
    return SQLiteStore(ws)


@pytest.fixture
def authority(ws: Path, store: SQLiteStore) -> RuntimeAuthority:
    registry = build_default_executor_registry(ws, store)
    return RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    if isinstance(raw.get("principal_type"), str):
        raw["principal_type"] = PrincipalType(raw["principal_type"])
    return Principal(**raw)


def test_capture_posture_has_identity_and_auth_strength(store: SQLiteStore) -> None:
    posture = capture_posture(store, _human(store), "")
    assert posture["principal_id"] == "principal_owner"
    assert posture["principal_type"] == "human"
    assert posture["auth_strength"] in {"mfa", "password"}
    assert posture["interface"] == "local"
    # metadata-only: no secret/token/content-shaped keys
    assert not any(k in posture for k in ("password", "token", "secret", "content", "text"))


def test_executed_action_event_carries_posture(
    authority: RuntimeAuthority, store: SQLiteStore, ws: Path
) -> None:
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "p.txt", "text": "hi"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, _human(store))
    assert result.decision == "allow"

    events = EventViewer(store).list_events(event_type="action_executed", limit=10)
    assert events
    event = EventViewer(store).read_event_payload(events[0]["event_id"])
    assert event is not None
    posture = event["payload"]["posture"]
    assert posture["principal_id"] == "principal_owner"
    assert posture["action_type"] == "write_file"
    # decision-path fields are present (ask mode, no grant for a human write)
    assert "decision_mode" in posture
    assert "grant_id" in posture
