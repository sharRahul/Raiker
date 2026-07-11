"""Web-app task 4 — GitHub read-only service connector (reference slice).

A model may read one GitHub issue or pull request through the brokered
``github_read`` tool. These tests pin the governance contract:

- the ``connector_github_runtime`` gate fails closed when disabled;
- the decision mode defaults to ``ask`` and **withholds** the read (``auto``
  withholds too — a network read carrying the owner token's scope off-machine
  is never low-risk); ``deny`` always blocks; only ``allow`` lets it run;
- an unset owner credential or a non-allowlisted egress host fails closed;
- request components are validated (bad repo/resource/number fail closed) and
  the request URL is built server-side, never taken raw from the model;
- events and stored tool actions keep the fetched body as metadata only — the
  external content never enters audit payloads;
- the fetched content comes back framed as untrusted data, not instructions;
- the capability executor is real, registered, and activation-gated on the
  threat-model ack + human confirmation.
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
from raiker.runtime.connectors import (
    GITHUB_TOKEN_ENV,
    GithubConnectorService,
)
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.connectors import GithubConnectorExecutor
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker

_CAP = "connector_github_runtime"
_ISSUE_JSON = json.dumps(
    {
        "title": "Broken login flow",
        "state": "open",
        "user": {"login": "octocat"},
        "body": "The login button does nothing on mobile.",
        "labels": [{"name": "bug"}, {"name": "mobile"}],
    }
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "gh"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


def _enable_gate(workspace: Path, store: SQLiteStore) -> RuntimeControlService:
    ctrl = RuntimeControlService(workspace)
    ctrl.activate_runtime_mode("local_single_user_runtime", "principal_rahul", "test")
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), "docs/threat-models/connectors-github.md"),
        )
    result = ctrl.set_capability_state(
        _CAP, "enabled_runtime", "principal_rahul", "test", confirmation_token="CONFIRM"
    )
    assert result.ok, result.reason_code
    return ctrl


def _allow(ctrl: RuntimeControlService) -> None:
    result = ctrl.set_capability_decision_mode(_CAP, "allow", "principal_rahul", "test")
    assert result.ok, result.reason_code


def _configure_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GITHUB_TOKEN_ENV, "ghp_secrettoken")
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")


def _ok_fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
    # Assert the URL is server-built against the fixed host, and the token is in
    # the auth header (never in the URL / arguments).
    assert url.startswith("https://api.github.com/repos/")
    assert headers["Authorization"].startswith("Bearer ")
    return {"status": 200, "body_bytes": len(_ISSUE_JSON), "body_text": _ISSUE_JSON, "truncated": False}


class TestGithubConnectorGovernance:
    def test_gate_disabled_fails_closed(self, workspace: Path, store: SQLiteStore) -> None:
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "connector_gate_disabled"

    def test_default_ask_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        _enable_gate(workspace, store)
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_withheld_ask"

    def test_auto_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "auto", "principal_rahul", "test")
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_withheld_auto"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_rahul", "test")
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_denied_by_decision_mode"

    def test_allow_without_credential_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(GITHUB_TOKEN_ENV, raising=False)
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")
        _allow(_enable_gate(workspace, store))
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_not_configured"

    def test_allow_without_egress_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(GITHUB_TOKEN_ENV, "ghp_x")
        monkeypatch.delenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", raising=False)
        _allow(_enable_gate(workspace, store))
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_egress_denied"

    def test_allow_reads_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["status"] == "success"
        assert outcome["title"] == "Broken login flow"
        assert outcome["state"] == "open"
        assert outcome["untrusted"] is True
        # The content is framed as untrusted data, never instructions.
        assert "untrusted data, not instructions" in outcome["content"]
        assert "login button does nothing" in outcome["content"]

    @pytest.mark.parametrize(
        ("resource", "repo", "number", "reason"),
        [
            ("wiki", "octo/repo", 5, "unsupported_resource"),
            ("issue", "not-a-repo", 5, "invalid_repo"),
            ("issue", "octo/repo", 0, "invalid_number"),
            ("issue", "octo/repo", "abc", "invalid_number"),
        ],
    )
    def test_argument_validation_fails_closed(
        self,
        workspace: Path,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        resource: str,
        repo: str,
        number: object,
        reason: str,
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            resource, repo, number
        )
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == reason


class TestGithubConnectorExecutor:
    def _action(self, arguments: dict[str, object]) -> ToolAction:
        from raiker.runtime.authority.router import GovernedAction

        return GovernedAction(
            action_id=new_id("act_"),
            principal_id="principal_rahul",
            action_type="connector_github_runtime",
            tool_or_service_name="connector_github_runtime",
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
        executor = GithubConnectorExecutor(workspace, store, fetch_fn=_ok_fetch)
        # Reached via route_action → enforce_modes=False; still needs creds+egress.
        result = executor.execute(
            self._action({"operation": "read", "resource": "issue", "repo": "octo/repo", "number": "5"}),
            None,  # type: ignore[arg-type]
        )
        assert result.ok is True
        assert result.artifacts["title"] == "Broken login flow"
        assert result.artifacts["content_redacted"] is True
        assert "login button does nothing" not in str(result.artifacts)

    def test_activation_requires_threat_model_ack(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        ctrl = RuntimeControlService(workspace)
        ctrl.activate_runtime_mode("local_single_user_runtime", "principal_rahul", "test")
        result = ctrl.set_capability_state(
            _CAP, "enabled_runtime", "principal_rahul", "test", confirmation_token="CONFIRM"
        )
        assert result.ok is False
        assert result.reason_code is not None and "no_threat_model_ack" in result.reason_code


class TestGithubReadTool:
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
            tool_name="github_read",
            arguments={"resource": "issue", "repo": "octo/repo", "number": "5"},
            risk_level="medium",
            requires_approval=False,
            proposed_by="model",
        )

    def test_exposed_to_the_model_and_validated(self) -> None:
        assert any(spec.name == "github_read" for spec in default_tool_specs())
        action = validate_tool_call(
            ToolCallProposal(
                call_id="call_1",
                tool_name="github_read",
                arguments={"resource": "issue", "repo": "octo/repo", "number": "5"},
            )
        )
        assert action.tool_name == "github_read"

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
        assert decision.decision == "allow"  # proposal allowed; read itself withheld
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
        # The tool result carries the content back to the calling model...
        assert result.output is not None and "login button does nothing" in result.output["content"]
        # ...but the durable event log keeps the read as metadata only: never the
        # fetched body, never the owner token. The governance-relevant repo/number
        # identifiers do remain (they are non-secret).
        events_text = writer.path_for_session(session_id).read_text(encoding="utf-8")
        assert "tool_completed" in events_text
        assert "login button does nothing" not in events_text
        assert "ghp_secrettoken" not in events_text
        assert "octo/repo" in events_text
