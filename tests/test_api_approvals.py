from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
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

    def test_detail_has_file_diff(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
        token = _token(client)
        resp = client.get("/api/approvals/appr_1", headers=_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["preview_kind"] == "file_diff"
        assert body["diff"] is not None
        assert "hello" in body["diff"]
        assert "NOT execute" in body["metadata_only_notice"]

    def test_detail_unknown_is_404(self, client: TestClient) -> None:
        token = _token(client)
        assert client.get("/api/approvals/nope", headers=_headers(token)).status_code == 404


class TestApprovalsResolve:
    def test_approve_records_metadata_only(self, workspace: Path, client: TestClient) -> None:
        _pending_approval(workspace)
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
