from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pending_approval(
    workspace: Path,
    *,
    approval_id: str = "appr_1",
    action_id: str = "act_1",
    tool_name: str = "write_file",
    arguments: dict[str, object] | None = None,
) -> None:
    """Insert a pending approval-required write_file action, mirroring the broker's bookkeeping."""
    store = SQLiteStore(workspace)
    store.create_session("sess_a", str(workspace))
    action = ToolAction(
        action_id=action_id,
        tool_name=tool_name,
        arguments=arguments if arguments is not None else {"path": "notes.txt", "text": "hello\n"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_a", turn_id="turn_a", status="approval_required")
    store.insert_approval(approval_id, action)


def _pending_machine_approval(workspace: Path) -> str:
    store = SQLiteStore(workspace)
    store.create_session("sess_machine", str(workspace))
    identity = TurnMachineIdentityLifecycle(workspace, store).start(
        owner_principal_id="principal_owner",
        session_id="sess_machine",
        turn_id="turn_machine",
        role_ids=("assistant",),
    )
    action = ToolAction(
        action_id="act_machine",
        tool_name="write_file",
        arguments={"path": "agent.txt", "text": "hello"},
        risk_level="high",
        requires_approval=True,
        proposed_by=identity.claims.principal_id,
    )
    store.insert_tool_action(
        action,
        session_id="sess_machine",
        turn_id="turn_machine",
        status="approval_required",
        owner_principal_id="principal_owner",
        machine_subject=identity.claims.subject,
        machine_token_id=identity.claims.token_id,
    )
    store.insert_approval("appr_machine", action)
    return identity.claims.principal_id


class TestApprovalsRead:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/approvals").status_code == 401

    def test_list_pending(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        resp = client.get("/api/approvals", headers=_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        item = body[0]
        assert item["approval_id"] == "appr_1"
        assert item["tool_name"] == "write_file"
        assert item["capability"] == "file_write_execution"
        assert item["risk_level"] == "high"
        assert item["requires_approval"] is True
        assert item["executes_action"] is False
        assert item["critical"] is False

    def test_detail_has_file_diff(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        resp = client.get("/api/approvals/appr_1", headers=_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["preview_kind"] == "file_diff"
        assert body["diff"] is not None
        assert "hello" in body["diff"]
        # BUG-06: a file write executes on approval when both gates are open, and
        # the notice says exactly that rather than a hardcoded metadata-only line.
        assert body["executes_on_approval"] is True
        assert "performs the change" in body["metadata_only_notice"]

    def test_patch_detail_shows_the_calculated_file_diff(self, workspace: Path, client: TestClient) -> None:
        (workspace / "notes.txt").write_text("old\n", encoding="utf-8")
        _pending_approval(
            workspace,
            tool_name="apply_patch",
            arguments={
                "path": "notes.txt",
                "patch": "--- a/notes.txt\n+++ b/notes.txt\n@@ -1 +1 @@\n-old\n+new\n",
            },
        )
        token = _token(client)

        body = client.get("/api/approvals/appr_1", headers=_headers(token)).json()

        assert body["preview_kind"] == "file_diff"
        assert "-old" in body["diff"]
        assert "+new" in body["diff"]

    def test_detail_says_metadata_only_when_the_capability_cannot_execute(
        self, workspace: Path, client: TestClient
    ) -> None:
        # `network` is deliberately outside the relayed set, so approving it still
        # only records a decision — and the detail view still says so.
        _pending_approval(
            workspace, tool_name="network", arguments={"url": "https://example.com"}
        )
        token = _token(client)
        body = client.get("/api/approvals/appr_1", headers=_headers(token)).json()
        assert body["executes_on_approval"] is False
        assert "NOT execute" in body["metadata_only_notice"]

    def test_list_exposes_server_calculated_expiry_state(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
                ("2000-01-01T00:00:00Z", "appr_1"),
            )

        token = _token(client)
        response = client.get("/api/approvals", headers=_headers(token))

        assert response.status_code == 200
        approval = response.json()[0]
        assert approval["expires_at"] == "2000-01-01T00:00:00Z"
        assert approval["is_expired"] is True

    def test_terminal_approval_is_not_relabelled_expired_after_its_ttl(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE approvals SET status = ?, expires_at = ? WHERE approval_id = ?",
                ("approved", "2000-01-01T00:00:00Z", "appr_1"),
            )

        token = _token(client)
        response = client.get("/api/approvals", params={"status_filter": "approved"}, headers=_headers(token))

        assert response.status_code == 200
        approval = response.json()[0]
        assert approval["status"] == "approved"
        assert approval["is_expired"] is False

    def test_detail_unknown_is_404(self, client: TestClient) -> None:
        token = _token(client)
        assert client.get("/api/approvals/nope", headers=_headers(token)).status_code == 404

    def test_detail_names_machine_proposer_without_exposing_bearer(
        self, workspace: Path, client: TestClient
    ) -> None:
        machine_principal_id = _pending_machine_approval(workspace)
        token = _token(client)

        body = client.get(
            "/api/approvals/appr_machine", headers=_headers(token)
        ).json()

        proposed = body["approval"]["proposed_by"]
        assert proposed["principal_id"] == machine_principal_id
        assert proposed["principal_type"] == "ai_agent"
        assert proposed["turn_id"] == "turn_machine"
        assert body["approval"]["machine_identity"]["subject"].startswith(
            "spiffe://raiker/"
        )
        assert "token" not in str(body).lower()

        resolved = client.post(
            "/api/approvals/appr_machine/resolve",
            json={"approve": False, "reason": "not this time"},
            headers=_headers(token),
        ).json()
        assert resolved["proposed_by"]["principal_id"] == machine_principal_id
        assert resolved["approved_by"]["principal_id"] == "principal_owner"
        assert resolved["approved_by"]["principal_type"] == "human"


class TestApprovalsResolve:
    def test_approved_shell_executes_once_with_bounded_evidence(
        self, workspace: Path, client: TestClient
    ) -> None:
        _pending_approval(
            workspace,
            tool_name="shell",
            arguments={
                # RAIKER-2023: `python -c` is an interpreter escape and is now
                # refused by the command policy, so this scenario — approval
                # reaches a real executor and its evidence is bounded — is
                # exercised with a command that is not one.
                "command": "echo 'web relay'",
                "max_output_bytes": 64,
            },
        )
        token = _token(client)

        response = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "reviewed command"},
            headers=_headers(token),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "executed"
        assert body["executes_action"] is True
        assert body["execution"]["returncode"] == 0
        assert body["execution"]["stdout"].strip() == "web relay"
        assert body["execution"]["stdout_bytes"] <= 64

    def test_approve_records_metadata_only_for_a_non_relayed_capability(
        self, workspace: Path, client: TestClient
    ) -> None:
        _pending_approval(
            workspace, tool_name="network", arguments={"url": "https://example.com"}
        )
        token = _token(client)
        resp = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "looks good"},
            headers=_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["executes_action"] is False
        # approval_received is recorded; the action itself is never executed.
        store = SQLiteStore(workspace)
        types = {e["event_type"] for e in store.list_event_index(session_id="sess_a", limit=200)}
        assert "approval_received" in types
        assert store.load_approval("appr_1")["status"] == "approved"  # type: ignore[index]

    def test_deny_records_denied(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        resp = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": False, "reason": "too risky"},
            headers=_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "denied"
        store = SQLiteStore(workspace)
        types = {e["event_type"] for e in store.list_event_index(session_id="sess_a", limit=200)}
        assert "approval_denied" in types

    def test_tampered_payload_rejected(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        # Mutate the stored action payload after the approval hash was recorded.
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
                ('{"path": "evil.txt", "text": "pwned"}', "act_1"),
            )
        token = _token(client)
        resp = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "x"},
            headers=_headers(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "approval_payload_tampered"

    def test_expired_approval_rejected(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        # Force the approval past its TTL after it was recorded.
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
                ("2000-01-01T00:00:00Z", "appr_1"),
            )
        token = _token(client)
        resp = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "x"},
            headers=_headers(token),
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "approval_expired"
        assert store.load_approval("appr_1")["status"] == "expired"  # type: ignore[index]

    def test_unknown_request_field_rejected(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        resp = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "x", "execute_now": True},
            headers=_headers(token),
        )
        assert resp.status_code == 422

    def test_already_resolved_conflict(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        first = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": True, "reason": "ok"},
            headers=_headers(token),
        )
        assert first.status_code == 200
        again = client.post(
            "/api/approvals/appr_1/resolve",
            json={"approve": False, "reason": "changed mind"},
            headers=_headers(token),
        )
        assert again.status_code == 409
        assert again.json()["detail"]["reason_code"] == "approval_already_resolved"


class TestCriticalApprovalResolve:
    def test_critical_resolution_requires_an_elevated_session_and_uses_the_critical_lifecycle(
        self, workspace: Path, client: TestClient
    ) -> None:
        _pending_approval(workspace)
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute("UPDATE approvals SET critical = 1 WHERE approval_id = ?", ("appr_1",))

        control_token = _token(client)
        denied_without_step_up = client.post(
            "/api/approvals/appr_1/resolve-critical",
            json={"approve": False, "reason": "not approved"},
            headers=_headers(control_token),
        )
        assert denied_without_step_up.status_code == 403
        assert denied_without_step_up.json()["detail"]["reason_code"] == "scope_insufficient"
        assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]

        control_session = ApiSessionStore(workspace).get_by_token(control_token)
        assert control_session is not None
        elevated_token, _session = ApiSessionStore(workspace).create_session(
            control_session.principal_id, scope="elevated", expires_in_seconds=60
        )
        resolved = client.post(
            "/api/approvals/appr_1/resolve-critical",
            json={"approve": False, "reason": "not approved"},
            headers=_headers(elevated_token),
        )
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "denied"
        assert resolved.json()["decision"] == "deny"
        assert store.load_approval("appr_1")["status"] == "denied"  # type: ignore[index]
