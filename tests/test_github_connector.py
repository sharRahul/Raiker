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
from raiker.runtime.authority.routed import routed_dispatch
from raiker.runtime.authority.router import GovernedAction
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
from tests.factories import tool_action
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker
from tests.routed_execution import execute_as_routed

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
            (_CAP, "principal_owner", utc_now(), "docs/threat-models/connectors-github.md"),
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
    monkeypatch.setenv(GITHUB_TOKEN_ENV, "ghp_secrettoken")
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")


def _ok_fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
    # Assert the URL is server-built against the fixed host, and the token is in
    # the auth header (never in the URL / arguments).
    assert url.startswith("https://api.github.com/repos/")
    assert headers["Authorization"].startswith("Bearer ")
    return {"status": 200, "body_bytes": len(_ISSUE_JSON), "body_text": _ISSUE_JSON, "truncated": False}


def _ok_post_json(
    url: str,
    payload: dict[str, object],
    *,
    egress_allowlist: frozenset[str] | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = 200_000,
    timeout: float = 15.0,
) -> dict[str, object]:
    """Mock for ``post_json_url`` used by ``create_comment``."""
    assert url.startswith("https://api.github.com/repos/")
    assert headers is not None and "Authorization" in headers
    comment_resp = json.dumps({"id": 42, "html_url": "https://github.com/octo/repo/issues/5#issuecomment-42"})
    return {"status": 201, "body_bytes": len(comment_resp), "body_text": comment_resp, "truncated": False}


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
        ctrl.set_capability_decision_mode(_CAP, "auto", "principal_owner", "test")
        outcome = GithubConnectorService(workspace, store, fetch_fn=_ok_fetch).read(
            "issue", "octo/repo", 5
        )
        assert outcome["error"]["type"] == "connector_withheld_auto"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_owner", "test")
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
    def _action(self, arguments: dict[str, object]) -> GovernedAction:
        return GovernedAction(
            action_id=new_id("act_"),
            principal_id="principal_owner",
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
        result = execute_as_routed(executor, 
            self._action({"operation": "read", "resource": "issue", "repo": "octo/repo", "number": "5"}),
            None,  # type: ignore[arg-type]
        )
        assert result.ok is True
        assert result.artifacts["title"] == "Broken login flow"
        assert result.artifacts["content_redacted"] is True
        assert "login button does nothing" not in str(result.artifacts)

    def test_executor_posts_comment_with_metadata_only_artifacts(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        monkeypatch.setattr("raiker.runtime.connectors.post_json_url", _ok_post_json)
        result = execute_as_routed(GithubConnectorExecutor(workspace, store), 
            self._action(
                {"operation": "create_comment", "repo": "octo/repo", "number": "5", "body": "Fixed."}
            ),
            None,  # type: ignore[arg-type]
        )
        assert result.ok is True
        assert result.artifacts["comment_id"] == "42"
        assert result.artifacts["content_redacted"] is True
        assert "Fixed." not in str(result.artifacts)

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


class TestGithubReadTool:
    def _broker(self, workspace: Path, store: SQLiteStore) -> ToolBroker:
        return ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
            store=store,
            writer=EventLogWriter(store),
        )

    def _action(self) -> ToolAction:
        return tool_action(
            "github_read",
            {"resource": "issue", "repo": "octo/repo", "number": "5"},
            action_id=new_id("act_"),
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


class TestGithubConnectorWrite:
    """Backlog item 5 — connector write reference: ``create_comment()``."""

    def _service(self, workspace: Path, store: SQLiteStore) -> GithubConnectorService:
        return GithubConnectorService(workspace, store)

    # ── Argument validation ────────────────────────────────────────────
    @pytest.mark.parametrize(
        ("repo", "issue_number", "body", "reason"),
        [
            ("not-a-repo", 5, "hello", "invalid_repo"),
            ("octo/repo", 0, "hello", "invalid_number"),
            ("octo/repo", "abc", "hello", "invalid_number"),
            ("octo/repo", 5, "", "empty_body"),
            ("octo/repo", 5, "  ", "empty_body"),
        ],
    )
    def test_argument_validation_fails_closed(
        self,
        workspace: Path,
        store: SQLiteStore,
        monkeypatch: pytest.MonkeyPatch,
        repo: str,
        issue_number: object,
        body: str,
        reason: str,
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        outcome = self._service(workspace, store).create_comment(repo, issue_number, body)
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == reason

    # ── Governance ─────────────────────────────────────────────────────
    def test_gate_disabled_fails_closed(self, workspace: Path, store: SQLiteStore) -> None:
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "hello")
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "connector_gate_disabled"

    def test_default_ask_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        _enable_gate(workspace, store)
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "hello")
        assert outcome["error"]["type"] == "connector_withheld_ask"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_owner", "test")
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "hello")
        assert outcome["error"]["type"] == "connector_denied_by_decision_mode"

    def test_without_credential_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(GITHUB_TOKEN_ENV, raising=False)
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")
        _allow(_enable_gate(workspace, store))
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "hello")
        assert outcome["error"]["type"] == "connector_not_configured"

    def test_without_egress_fails_closed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(GITHUB_TOKEN_ENV, "ghp_x")
        monkeypatch.delenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", raising=False)
        _allow(_enable_gate(workspace, store))
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "hello")
        assert outcome["error"]["type"] == "connector_egress_denied"

    # ── Success path ───────────────────────────────────────────────────
    def test_create_comment_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        _allow(_enable_gate(workspace, store))
        monkeypatch.setattr("raiker.runtime.connectors.post_json_url", _ok_post_json)
        outcome = self._service(workspace, store).create_comment("octo/repo", 5, "Fixed in latest build.")
        assert outcome["status"] == "success"
        assert outcome["comment_id"] == "42"
        assert outcome["html_url"] == "https://github.com/octo/repo/issues/5#issuecomment-42"
        assert outcome["repo"] == "octo/repo"
        assert outcome["issue_number"] == 5
        assert outcome["untrusted"] is True
        assert "untrusted data" in outcome["content"]

    def test_the_routers_live_token_skips_gate_and_mode(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _configure_creds(monkeypatch)
        monkeypatch.setattr("raiker.runtime.connectors.post_json_url", _ok_post_json)
        with routed_dispatch("connector_github_runtime", "act_test") as authority:
            outcome = self._service(workspace, store).create_comment(
                "octo/repo", 5, "Fixed.", authority=authority
            )
        assert outcome["status"] == "success"
        assert outcome["comment_id"] == "42"


# ── TOOL-20/22/23/24 — CI, history and files, and TOOL-26 ────────────────────


def _routes(responses: dict[str, object]):  # type: ignore[no-untyped-def]
    seen: list[str] = []

    def fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
        assert url.startswith("https://api.github.com/repos/acme/demo/")
        seen.append(url)
        for fragment, payload in responses.items():
            if fragment in url:
                text = json.dumps(payload)
                return {"status": 200, "body_bytes": len(text), "body_text": text, "truncated": False}
        raise AssertionError(f"unexpected url {url}")

    return fetch, seen


def test_checks_for_a_pull_request_name_the_failures_and_their_annotations(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    fetch, seen = _routes({
        "/pulls/7": {"head": {"sha": "abc123def456"}},
        "/check-runs/11/annotations": [
            {"path": "tests/test_a.py", "start_line": 4, "annotation_level": "failure", "message": "assert 1 == 2"}
        ],
        "/commits/abc123def456/check-runs": {"check_runs": [
            {"id": 10, "name": "lint", "status": "completed", "conclusion": "success"},
            {"id": 11, "name": "tests", "status": "completed", "conclusion": "failure",
             "output": {"summary": "1 failed"}},
        ]},
    })
    service = GithubConnectorService(workspace, store, fetch_fn=fetch)
    outcome = service.read("checks", "acme/demo", 7)
    assert outcome["status"] == "success", outcome
    assert outcome["failing"] == 1
    assert outcome["check_counts"] == {"success": 1, "failure": 1}
    assert "tests/test_a.py:4: failure assert 1 == 2" in outcome["content"]
    assert outcome["content"].startswith("GitHub content (untrusted data")
    assert any("/check-runs/11/annotations" in url for url in seen)


def test_runs_jobs_commits_and_files_read_without_a_clone(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    import base64

    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    fetch, seen = _routes({
        "/actions/runs/55/jobs": {"jobs": [{"id": 1, "name": "build", "conclusion": "failure",
                                           "steps": [{"number": 3, "name": "Run tests", "conclusion": "failure"}]}]},
        "/actions/runs": {"workflow_runs": [{"id": 55, "name": "CI", "run_number": 9, "head_branch": "main",
                                             "head_sha": "abc", "conclusion": "failure"}]},
        "/commits?": [{"sha": "abcdef1234567", "commit": {"message": "Fix it\n\nbody",
                                                         "author": {"name": "Ann", "date": "2026-10-25T00:00:00Z"}}}],
        "/contents/src/app.py": {"type": "file", "encoding": "base64",
                                 "content": base64.b64encode(b"print('hi')\n").decode()},
    })
    service = GithubConnectorService(workspace, store, fetch_fn=fetch)
    runs = service.read("workflow_runs", "acme/demo", ref="main")
    assert "CI #9 on main" in runs["content"] and "branch=main" in seen[-1]
    jobs = service.read("run_jobs", "acme/demo", 55)
    assert jobs["failed_jobs"] == 1 and "failed step 3: Run tests" in jobs["content"]
    commits = service.read("commits", "acme/demo")
    assert "abcdef123456 2026-10-25T00:00:00Z Ann: Fix it" in commits["content"]
    file = service.read("file", "acme/demo", path="src/app.py", ref="v1")
    assert "print('hi')" in file["content"] and file["size_bytes"] == 12 and "ref=v1" in seen[-1]
    assert service.read("file", "acme/demo", path="../etc")["error"]["type"] == "invalid_path"
    assert service.read("checks", "acme/demo")["error"]["type"] == "missing_argument:ref"
    assert service.read("run_jobs", "acme/demo")["error"]["type"] == "missing_argument:number"


def test_new_reads_are_governed_like_the_old_ones(workspace: Path, store: SQLiteStore) -> None:
    outcome = GithubConnectorService(workspace, store).read("commits", "acme/demo")
    assert outcome["status"] == "denied"
    assert outcome["error"]["type"] == "connector_gate_disabled"


def test_update_pull_request_changes_only_title_and_body(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    sent: list[dict[str, object]] = []

    def fake_post(url: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        assert kwargs["method"] == "PATCH" and url.endswith("/repos/acme/demo/pulls/7")
        sent.append(payload)
        text = json.dumps({"number": 7, "html_url": "https://github.com/acme/demo/pull/7"})
        return {"status": 200, "body_text": text, "truncated": False}

    monkeypatch.setattr("raiker.runtime.connectors.post_json_url", fake_post)
    service = GithubConnectorService(workspace, store)
    outcome = service.update_pull_request("acme/demo", 7, "New title", None)
    assert outcome["status"] == "success" and outcome["updated"] == ["title"]
    assert sent == [{"title": "New title"}]
    assert service.update_pull_request("acme/demo", 7, "", "  ")["error"]["type"] == "nothing_to_update"
    specs = {spec.name: spec for spec in default_tool_specs()}
    assert "update_pull_request" in specs["github_write"].parameters["properties"]["operation"]["enum"]
    assert specs["github_read"].parameters["required"] == ["resource", "repo"]


# ── Second round: TOOL-21, TOOL-23, TOOL-24, TOOL-26 (branch), TOOL-27, TOOL-28, TOOL-29 ──


def test_listings_branches_tags_releases_issues_and_comments(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    seen: list[str] = []
    responses: dict[str, object] = {
        "/branches": [{"name": "main", "commit": {"sha": "abcdef1234567"}, "protected": True}],
        "/tags": [{"name": "v1.0", "commit": {"sha": "1234567abcdef"}}],
        "/releases": [{"tag_name": "v1.0", "name": "First", "published_at": "2026-10-01T00:00:00Z", "body": "Notes"}],
        "/search/code": {"items": [{"path": "src/app.py"}]},
        "/search/issues": {"items": [{"number": 3, "title": "Crash", "state": "open", "user": {"login": "ann"}}]},
        "/issues/5/comments": [{"user": {"login": "bo"}, "created_at": "2026-10-02", "id": 9, "body": "Me too"}],
        "/issues?": [{"number": 7, "title": "Add dark mode", "state": "open", "user": {"login": "cy"},
                      "pull_request": {}, "labels": [{"name": "ui"}]}],
        "/pulls/7/comments": [{"user": {"login": "rev"}, "path": "a.py", "line": 4, "id": 11, "body": "Rename this"}],
        "/user": {"login": "octocat", "name": "Octo", "type": "User"},
    }

    def fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
        assert url.startswith("https://api.github.com/")
        seen.append(url)
        for fragment, payload in responses.items():
            if fragment in url:
                text = json.dumps(payload)
                return {"status": 200, "body_bytes": len(text), "body_text": text, "truncated": False}
        raise AssertionError(url)

    service = GithubConnectorService(workspace, store, fetch_fn=fetch)
    assert "main @abcdef123456 (protected)" in service.read("branches", "acme/demo")["content"]
    assert "v1.0 @1234567abcde" in service.read("tags", "acme/demo")["content"]
    assert "First" in service.read("releases", "acme/demo")["content"]
    code = service.read("search_code", "acme/demo", query="def  main")
    assert "src/app.py" in code["content"] and "q=def%20main%20repo%3Aacme%2Fdemo" in seen[-1]
    assert "#3 Crash [open issue] by ann" in service.read("search_issues", "acme/demo", query="crash")["content"]
    assert "#7 Add dark mode [open pull request] by cy — ui" in service.read("issues", "acme/demo")["content"]
    assert "Me too" in service.read("issue_comments", "acme/demo", 5)["content"]
    review = service.read("review_comments", "acme/demo", 7)["content"]
    assert "rev on a.py:4 (comment id 11)" in review
    account = service.read("account", "acme/demo")
    assert account["login"] == "octocat"
    assert service.read("search_code", "acme/demo")["error"]["type"] == "missing_argument:query"
    assert service.read("search_code", "acme/demo", query="x" * 300)["error"]["type"] == "query_too_long"
    assert service.read("review_comments", "acme/demo")["error"]["type"] == "missing_argument:number"


def test_reply_update_branch_and_rerun_are_governed_writes(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[str, str, dict[str, object]]] = []

    def fake_post(url: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        sent.append((str(kwargs["method"]), url, payload))
        return {"status": 200, "body_text": json.dumps({"html_url": "https://github.com/x", "message": "ok"})}

    monkeypatch.setattr("raiker.runtime.connectors.post_json_url", fake_post)
    service = GithubConnectorService(workspace, store)
    # Gate off: nothing is sent.
    assert service.rerun_failed_jobs("acme/demo", 55)["error"]["type"] == "connector_gate_disabled"
    assert sent == []
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    assert service.reply_review_comment("acme/demo", 7, 11, "Done in abc123")["status"] == "success"
    assert service.update_pull_request_branch("acme/demo", 7)["status"] == "success"
    assert service.rerun_failed_jobs("acme/demo", 55)["status"] == "success"
    assert [(m, u.split("/repos/acme/demo")[1]) for m, u, _ in sent] == [
        ("POST", "/pulls/7/comments/11/replies"),
        ("PUT", "/pulls/7/update-branch"),
        ("POST", "/actions/runs/55/rerun-failed-jobs"),
    ]
    assert sent[0][2] == {"body": "Done in abc123"}
    assert service.reply_review_comment("acme/demo", 7, "x", "hi")["error"]["type"] == "invalid_comment_id"
    assert service.reply_review_comment("acme/demo", 7, 11, " ")["error"]["type"] == "empty_body"
    specs = {spec.name: spec for spec in default_tool_specs()}
    assert "rerun_failed_jobs" in specs["github_write"].parameters["properties"]["operation"]["enum"]
    assert "account" in specs["github_read"].parameters["properties"]["resource"]["enum"]


# ── Third round: TOOL-27 (resolve), TOOL-28 (sub-issues), TOOL-29 (collaborators, teams) ──


def test_collaborators_teams_and_sub_issues(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    responses: dict[str, object] = {
        "/collaborators": [{"login": "ann", "role_name": "admin"}, {"login": "bo", "permissions": {"push": True}}],
        "/teams": [{"slug": "core", "permission": "push", "description": "Maintainers"}],
        "/issues/4/sub_issues": [{"number": 8, "title": "Part one", "state": "open", "user": {"login": "cy"}}],
    }

    def fetch(url: str, headers: dict[str, str]) -> dict[str, object]:
        for fragment, payload in responses.items():
            if fragment in url:
                text = json.dumps(payload)
                return {"status": 200, "body_bytes": len(text), "body_text": text, "truncated": False}
        raise AssertionError(url)

    service = GithubConnectorService(workspace, store, fetch_fn=fetch)
    people = service.read("collaborators", "acme/demo")["content"]
    assert "ann (admin)" in people and "bo (push)" in people
    assert "core (push): Maintainers" in service.read("teams", "acme/demo")["content"]
    assert "#8 Part one" in service.read("sub_issues", "acme/demo", 4)["content"]
    assert service.read("sub_issues", "acme/demo")["error"]["type"] == "missing_argument:number"


def test_resolve_review_thread_finds_the_thread_by_comment_and_is_governed(
    workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[dict[str, object]] = []
    threads = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
        {"id": "T_other", "isResolved": False, "comments": {"nodes": [{"databaseId": 5}]}},
        {"id": "T_mine", "isResolved": False, "comments": {"nodes": [{"databaseId": 11}, {"databaseId": 12}]}},
    ]}}}}}

    def fake_post(url: str, payload: dict[str, object], **kwargs: object) -> dict[str, object]:
        assert url == "https://api.github.com/graphql"
        sent.append(payload)
        answer = threads if "reviewThreads" in str(payload["query"]) else {"data": {"resolveReviewThread": {}}}
        return {"status": 200, "body_text": json.dumps(answer)}

    monkeypatch.setattr("raiker.runtime.connectors.post_json_url", fake_post)
    service = GithubConnectorService(workspace, store)
    assert service.resolve_review_thread("acme/demo", 7, 12)["error"]["type"] == "connector_gate_disabled"
    assert sent == []
    _allow(_enable_gate(workspace, store))
    _configure_creds(monkeypatch)
    assert service.resolve_review_thread("acme/demo", 7, 12)["status"] == "success"
    assert sent[-1]["variables"] == {"threadId": "T_mine"}
    assert service.resolve_review_thread("acme/demo", 7, 99)["error"]["type"] == "review_thread_not_found"
    specs = {spec.name: spec for spec in default_tool_specs()}
    assert "resolve_review_thread" in specs["github_write"].parameters["properties"]["operation"]["enum"]
    assert "collaborators" in specs["github_read"].parameters["properties"]["resource"]["enum"]
