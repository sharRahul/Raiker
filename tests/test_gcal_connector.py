"""Web-app task 4 — Google Calendar read-only connector.

A model may read one Calendar event or calendar through the brokered
``gcal_read`` tool. These tests pin the same governance contract as the GitHub /
Gmail connectors: gate fails closed when disabled; default ``ask``/``auto``
withhold; ``deny`` blocks; missing credential/egress fail closed; request
components are validated and the URL is built server-side; events keep the
fetched body as metadata only; content is framed as untrusted data; the executor
is real, registered, and activation-gated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ToolAction
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import default_tool_specs, validate_tool_call
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.connectors import GCAL_TOKEN_ENV, GcalConnectorService
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.connectors import GcalConnectorExecutor
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

_CAP = "connector_gcal_runtime"
_EVENT_JSON = json.dumps(
    {
        "summary": "Sprint planning",
        "status": "confirmed",
        "start": {"dateTime": "2026-07-15T10:00:00-07:00"},
        "end": {"dateTime": "2026-07-15T11:00:00-07:00"},
        "location": "Room 4",
        "organizer": {"email": "lead@example.com"},
        "attendees": [{"email": "a@example.com"}, {"email": "b@example.com"}],
        "description": "Plan the sprint backlog.",
    }
)
_CALENDAR_JSON = json.dumps(
    {
        "summary": "Team Calendar",
        "timeZone": "America/Los_Angeles",
        "description": "Shared team events.",
    }
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "gcal"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _enable_gate(workspace: Path, store: SQLiteStore) -> RuntimeControlService:
    ctrl = RuntimeControlService(workspace)
    ctrl.activate_runtime_mode("local_single_user_runtime", "principal_owner", "test")
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), "docs/threat-models/connectors-gcal.md"),
        )
    result = ctrl.set_capability_state(
        _CAP, "enabled_runtime", "principal_owner", "test", confirmation_token="CONFIRM"
    )
    assert result.ok, result.reason_code
    return ctrl


def _allow(ctrl: RuntimeControlService) -> None:
    result = ctrl.set_capability_decision_mode(_CAP, "allow", "principal_owner", "test")
    assert result.ok, result.reason_code


def _configure_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GCAL_TOKEN_ENV, "ya29.calendar-token")
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "www.googleapis.com")


def _ok_fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
    assert url.startswith("https://www.googleapis.com/calendar/v3/calendars/")
    assert headers["Authorization"].startswith("Bearer ")
    body = _EVENT_JSON if "/events/" in url else _CALENDAR_JSON
    return {"status": 200, "body_bytes": len(body), "body_text": body, "truncated": False}


class TestGcalConnectorGovernance:
    def test_gate_disabled_fails_closed(self, workspace: Path, store: SQLiteStore) -> None:
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "connector_gate_disabled"

    def test_default_ask_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        _enable_gate(workspace, store)
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["error"]["type"] == "connector_withheld_ask"

    def test_auto_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "auto", "principal_owner", "test")
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["error"]["type"] == "connector_withheld_auto"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_owner", "test")
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["error"]["type"] == "connector_denied_by_decision_mode"

    def test_allow_without_credential_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(GCAL_TOKEN_ENV, raising=False)
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "www.googleapis.com")
        _allow(_enable_gate(workspace, store))
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["error"]["type"] == "connector_not_configured"

    def test_allow_without_egress_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(GCAL_TOKEN_ENV, "ya29.x")
        monkeypatch.delenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", raising=False)
        _allow(_enable_gate(workspace, store))
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["error"]["type"] == "connector_egress_denied"

    def test_allow_reads_event_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "event", "primary", "evt1"
        )
        assert outcome["status"] == "success"
        assert outcome["title"] == "Sprint planning"
        assert outcome["untrusted"] is True
        assert "untrusted data, not instructions" in outcome["content"]
        assert "Plan the sprint backlog." in outcome["content"]
        assert "attendees: 2" in outcome["content"]

    def test_allow_reads_calendar_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "calendar", "primary"
        )
        assert outcome["status"] == "success"
        assert outcome["title"] == "Team Calendar"
        assert "America/Los_Angeles" in outcome["content"]

    @pytest.mark.parametrize(
        ("resource", "calendar_id", "event_id", "reason"),
        [
            ("meeting", "primary", "evt1", "unsupported_resource"),
            ("event", "bad id!", "evt1", "invalid_calendar_id"),
            ("event", "primary", "bad id!", "invalid_event_id"),
            ("event", "primary", "", "invalid_event_id"),
        ],
    )
    def test_argument_validation_fails_closed(
        self,
        workspace: Path,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        calendar_id: str,
        event_id: str,
        reason: str,
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = GcalConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            resource, calendar_id, event_id
        )
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == reason


class TestGcalConnectorExecutor:
    def _action(self, arguments: dict[str, object]) -> GovernedAction:
        return GovernedAction(
            action_id=new_id("act_"),
            principal_id="principal_owner",
            action_type="connector_gcal_runtime",
            tool_or_service_name="connector_gcal_runtime",
            arguments=arguments,
        )

    def test_registered_as_real_executor(self, workspace: Path, store: SQLiteStore) -> None:
        assert _CAP in REAL_EXECUTOR_CAPABILITIES
        registry = build_default_executor_registry(workspace, store)
        assert registry.has(_CAP)

    def test_executor_metadata_only_on_success(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        executor = GcalConnectorExecutor(workspace, store, fetch_fn=_ok_fetch)
        result = executor.execute(
            self._action(
                {"operation": "read", "resource": "event", "calendar_id": "primary", "event_id": "evt1"}
            ),
            None,  # type: ignore[arg-type]
        )
        assert result.ok is True
        assert result.artifacts["title"] == "Sprint planning"
        assert result.artifacts["content_redacted"] is True
        assert "Plan the sprint backlog." not in str(result.artifacts)

    def test_activation_requires_threat_model_ack(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        ctrl = RuntimeControlService(workspace)
        ctrl.activate_runtime_mode("local_single_user_runtime", "principal_owner", "test")
        result = ctrl.set_capability_state(
            _CAP, "enabled_runtime", "principal_owner", "test", confirmation_token="CONFIRM"
        )
        assert result.ok is False
        assert result.reason_code is not None and "no_threat_model_ack" in result.reason_code


class TestGcalReadTool:
    def _broker(self, workspace: Path, store: SQLiteStore) -> ToolBroker:
        return ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
            store=store,
            writer=EventLogWriter(store),
        )

    def _action(self) -> ToolAction:
        return ToolAction(
            action_id=new_id("act_"),
            tool_name="gcal_read",
            arguments={"resource": "event", "calendar_id": "primary", "event_id": "evt1"},
            risk_level="medium",
            requires_approval=False,
            proposed_by="model",
        )

    def test_exposed_to_the_model_and_validated(self) -> None:
        assert any(spec.name == "gcal_read" for spec in default_tool_specs())
        action = validate_tool_call(
            ToolCallProposal(
                call_id="call_1",
                tool_name="gcal_read",
                arguments={"resource": "event", "calendar_id": "primary", "event_id": "evt1"},
            )
        )
        assert action.tool_name == "gcal_read"

    def test_policy_engine_allows_the_proposal(self, workspace: Path) -> None:
        decision = PolicyEngine(StaticPolicyConfig(workspace)).review(self._action())
        assert decision.decision == "allow"

    def test_default_ask_withholds_through_the_broker(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _enable_gate(workspace, store)
        broker = self._broker(workspace, store)
        result, decision = broker.execute(
            self._action(), session_id=new_id("sess_"), turn_id=None
        )
        assert decision.decision == "allow"
        assert result.status == "denied"
        assert result.error is not None and result.error["type"] == "connector_withheld_ask"

    def test_events_keep_fetched_content_metadata_only(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        monkeypatch.setattr("raiker.runtime.connectors._default_fetch", _ok_fetch)
        ctrl = _enable_gate(workspace, store)
        _allow(ctrl)
        broker = self._broker(workspace, store)
        writer = broker.writer
        assert writer is not None
        session_id = new_id("sess_")
        result, _decision = broker.execute(self._action(), session_id=session_id, turn_id=None)
        assert result.status == "success"
        assert result.output is not None and "Plan the sprint backlog." in result.output["content"]
        events_text = writer.path_for_session(session_id).read_text(encoding="utf-8")
        assert "tool_completed" in events_text
        assert "Plan the sprint backlog." not in events_text
        assert "ya29.calendar-token" not in events_text
        assert "primary" in events_text
