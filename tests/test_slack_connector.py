"""Web-app task 4 — Slack read-only connector.

A model may read one Slack channel's info or recent history through the brokered
``slack_read`` tool. These tests pin the same governance contract as the GitHub /
Gmail / Calendar connectors: gate fails closed when disabled; default
``ask``/``auto`` withhold; ``deny`` blocks; missing credential/egress fail
closed; request components are validated and the URL is built server-side; a
Slack ``ok: false`` body is treated as a bad response (never surfaced as
content); events keep the fetched body as metadata only; content is framed as
untrusted data; the executor is real, registered, and activation-gated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

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
from raiker.runtime.connectors import SLACK_TOKEN_ENV, SlackConnectorService
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.connectors import SlackConnectorExecutor
from raiker.storage.sqlite import SQLiteStore

_CAP = "connector_slack_runtime"
_INFO_JSON = json.dumps(
    {
        "ok": True,
        "channel": {
            "id": "C123ABC",
            "name": "general",
            "topic": {"value": "Company-wide announcements"},
            "purpose": {"value": "General chatter"},
            "num_members": 42,
        },
    }
)
_HISTORY_JSON = json.dumps(
    {
        "ok": True,
        "messages": [
            {"user": "U1", "text": "Deploy is green", "ts": "1699.1"},
            {"user": "U2", "text": "Nice work team", "ts": "1699.2"},
        ],
    }
)
_ERROR_JSON = json.dumps({"ok": False, "error": "channel_not_found"})


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "slack"
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
            (_CAP, "principal_owner", utc_now(), "docs/threat-models/connectors-slack.md"),
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
    monkeypatch.setenv(SLACK_TOKEN_ENV, "xoxb-secret-slack-token")
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "slack.com")


def _ok_fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
    assert url.startswith("https://slack.com/api/conversations.")
    assert headers["Authorization"].startswith("Bearer ")
    body = _HISTORY_JSON if "conversations.history" in url else _INFO_JSON
    return {"status": 200, "body_bytes": len(body), "body_text": body, "truncated": False}


def _error_fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
    return {"status": 200, "body_bytes": len(_ERROR_JSON), "body_text": _ERROR_JSON, "truncated": False}


class TestSlackConnectorGovernance:
    def test_gate_disabled_fails_closed(self, workspace: Path, store: SQLiteStore) -> None:
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "connector_gate_disabled"

    def test_default_ask_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        _enable_gate(workspace, store)
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["error"]["type"] == "connector_withheld_ask"

    def test_auto_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "auto", "principal_owner", "test")
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["error"]["type"] == "connector_withheld_auto"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_owner", "test")
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["error"]["type"] == "connector_denied_by_decision_mode"

    def test_allow_without_credential_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(SLACK_TOKEN_ENV, raising=False)
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "slack.com")
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["error"]["type"] == "connector_not_configured"

    def test_allow_without_egress_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(SLACK_TOKEN_ENV, "xoxb-x")
        monkeypatch.delenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", raising=False)
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["error"]["type"] == "connector_egress_denied"

    def test_allow_reads_channel_info_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["status"] == "success"
        assert outcome["title"] == "general"
        assert outcome["untrusted"] is True
        assert "untrusted data, not instructions" in outcome["content"]
        assert "Company-wide announcements" in outcome["content"]

    def test_allow_reads_channel_history_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "channel_history", "C123ABC"
        )
        assert outcome["status"] == "success"
        assert "2 messages" in outcome["content"]
        assert "Deploy is green" in outcome["content"]
        assert "Nice work team" in outcome["content"]

    def test_slack_error_body_is_bad_response(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Slack returns ok:false on an HTTP 200; it must not surface as content.
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_error_fetch).read(
            "channel_info", "C123ABC"
        )
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == "connector_bad_response"

    @pytest.mark.parametrize(
        ("resource", "channel", "reason"),
        [
            ("dm", "C123ABC", "unsupported_resource"),
            ("channel_info", "bad chan!", "invalid_channel"),
            ("channel_info", "", "invalid_channel"),
        ],
    )
    def test_argument_validation_fails_closed(
        self,
        workspace: Path,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        channel: str,
        reason: str,
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = SlackConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            resource, channel
        )
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == reason


class TestSlackConnectorExecutor:
    def _action(self, arguments: dict[str, object]) -> GovernedAction:
        return GovernedAction(
            action_id=new_id("act_"),
            principal_id="principal_owner",
            action_type="connector_slack_runtime",
            tool_or_service_name="connector_slack_runtime",
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
        executor = SlackConnectorExecutor(workspace, store, fetch_fn=_ok_fetch)
        result = executor.execute(
            self._action({"operation": "read", "resource": "channel_info", "channel": "C123ABC"}),
            None,  # type: ignore[arg-type]
        )
        assert result.ok is True
        assert result.artifacts["title"] == "general"
        assert result.artifacts["content_redacted"] is True
        assert "Company-wide announcements" not in str(result.artifacts)

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


class TestSlackReadTool:
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
            tool_name="slack_read",
            arguments={"resource": "channel_info", "channel": "C123ABC"},
            risk_level="medium",
            requires_approval=False,
            proposed_by="model",
        )

    def test_exposed_to_the_model_and_validated(self) -> None:
        assert any(spec.name == "slack_read" for spec in default_tool_specs())
        action = validate_tool_call(
            ToolCallProposal(
                call_id="call_1",
                tool_name="slack_read",
                arguments={"resource": "channel_info", "channel": "C123ABC"},
            )
        )
        assert action.tool_name == "slack_read"

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
        assert result.output is not None and "Company-wide announcements" in result.output["content"]
        events_text = writer.path_for_session(session_id).read_text(encoding="utf-8")
        assert "tool_completed" in events_text
        assert "Company-wide announcements" not in events_text
        assert "xoxb-secret-slack-token" not in events_text
        assert "C123ABC" in events_text
