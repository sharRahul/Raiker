"""BUG-24 — a decision made in one tab continues the turn parked in another.

The client half is a broadcast plus a poll; this is the authority the poll asks.
What has to hold: a parked turn appears only once its approval is resolved, it
disappears the moment a client claims it, it never crosses an account boundary,
and it carries ids rather than conversation state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime.turn_suspension import approval_outcome
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


def _session(client: TestClient) -> tuple[dict[str, str], str]:
    body = client.post("/api/auth/session", json={"as_principal": None}).json()
    return {"Authorization": f"Bearer {body['token']}"}, str(body["principal_id"])


def _park(
    workspace: Path,
    principal_id: str,
    *,
    approval_id: str = "appr_1",
    session_id: str = "sess_1",
) -> SQLiteStore:
    store = SQLiteStore(workspace)
    store.insert_suspended_turn(
        {
            "approval_id": approval_id,
            "session_id": session_id,
            "turn_id": "turn_1",
            "request_id": "req_1",
            "principal_id": principal_id,
            "action_id": "act_1",
            "tool_name": "write_file",
            "call_id": "call_1",
            "prompt_text": "write notes.md",
            "messages_json": json.dumps([{"role": "user", "content": "write notes.md"}]),
            "options_json": "{}",
            "client_json": "{}",
        }
    )
    return store


class TestResumableTurns:
    def test_pending_parked_turn_metadata_can_be_restored_with_a_session(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.create_session("sess_1", str(workspace), user_id="owner")
        store.insert_turn("sess_1", "turn_1", "write notes.md", "needs_approval")

        body = client.get("/api/sessions/sess_1", headers=headers).json()

        assert len(body["parked_approvals"]) == 1
        assert body["parked_approvals"][0] == {
            "approval_id": "appr_1",
            "turn_id": "turn_1",
            "tool_name": "write_file",
            "created_at": body["parked_approvals"][0]["created_at"],
        }
        assert "messages_json" not in client.get(
            "/api/sessions/sess_1", headers=headers
        ).text

    def test_pending_parked_turn_metadata_is_principal_scoped(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, "principal_someone_else")
        store.create_session("sess_1", str(workspace), user_id="owner")
        store.insert_turn("sess_1", "turn_1", "write notes.md", "needs_approval")

        body = client.get("/api/sessions/sess_1", headers=headers).json()
        assert principal != "principal_someone_else"
        assert body["parked_approvals"] == []

    def test_a_turn_is_not_resumable_until_its_approval_is_resolved(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        _park(workspace, principal)
        body = client.get("/api/approvals/resumable", headers=headers).json()
        assert body["turns"] == []

    def test_a_resolved_turn_is_listed_with_its_decision(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome(
            "appr_1", json.dumps(approval_outcome(approved=True, executed=True))
        )
        turns = client.get("/api/approvals/resumable", headers=headers).json()["turns"]
        assert len(turns) == 1
        assert turns[0]["approval_id"] == "appr_1"
        assert turns[0]["session_id"] == "sess_1"
        assert turns[0]["outcome_status"] == "success"

    def test_a_rejection_is_reported_as_a_rejection(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome(
            "appr_1", json.dumps(approval_outcome(approved=False, executed=False))
        )
        turns = client.get("/api/approvals/resumable", headers=headers).json()["turns"]
        assert turns[0]["outcome_status"] == "rejected"

    def test_a_claimed_turn_stops_being_offered_so_only_one_tab_resumes_it(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome(
            "appr_1", json.dumps(approval_outcome(approved=True, executed=True))
        )
        assert client.get("/api/approvals/resumable", headers=headers).json()["turns"]
        # Exactly what a resuming client does first. The second claim fails,
        # which is the exactly-once guarantee the two tabs actually race on.
        assert store.claim_suspended_turn("appr_1") is True
        assert store.claim_suspended_turn("appr_1") is False
        assert client.get("/api/approvals/resumable", headers=headers).json()["turns"] == []

    def test_the_list_can_be_narrowed_to_one_conversation(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        _park(workspace, principal, approval_id="appr_2", session_id="sess_2")
        for approval_id in ("appr_1", "appr_2"):
            store.record_suspended_turn_outcome(
                approval_id, json.dumps(approval_outcome(approved=True, executed=True))
            )
        narrowed = client.get(
            "/api/approvals/resumable?session_id=sess_2", headers=headers
        ).json()["turns"]
        assert [turn["approval_id"] for turn in narrowed] == ["appr_2"]

    def test_another_account_never_sees_this_turn(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome(
            "appr_1", json.dumps(approval_outcome(approved=True, executed=True))
        )
        assert store.list_resumable_suspended_turns("principal_someone_else") == []
        # And the owner's own read still finds it, so the scoping is real.
        assert client.get("/api/approvals/resumable", headers=headers).json()["turns"]

    def test_no_conversation_state_is_returned(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome(
            "appr_1", json.dumps(approval_outcome(approved=True, executed=True))
        )
        raw = client.get("/api/approvals/resumable", headers=headers).text
        assert "write notes.md" not in raw
        assert "messages_json" not in raw

    def test_the_read_requires_a_bearer_token(self, client: TestClient) -> None:
        assert client.get("/api/approvals/resumable").status_code in (401, 403)

    def test_the_literal_route_is_not_captured_by_the_approval_id_route(
        self, client: TestClient
    ) -> None:
        # `/api/approvals/{approval_id}` would otherwise swallow "resumable" and
        # 404 as an unknown approval.
        headers, _principal = _session(client)
        response = client.get("/api/approvals/resumable", headers=headers)
        assert response.status_code == 200
        assert "turns" in response.json()

    def test_an_unreadable_outcome_is_reported_as_unknown_rather_than_hidden(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers, principal = _session(client)
        store = _park(workspace, principal)
        store.record_suspended_turn_outcome("appr_1", "not json at all")
        turns = client.get("/api/approvals/resumable", headers=headers).json()["turns"]
        assert turns[0]["outcome_status"] == "unknown"
