from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
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


def _owner_headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
    return {"Authorization": f"Bearer {raw}"}


def _activate(client: TestClient, headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/runtime-mode/activate",
        json={"mode_name": "local_single_user_runtime", "reason": "m5"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


class TestRuntimeMutations:
    def test_enable_supported_gate_succeeds_and_is_event_logged(
        self, workspace: Path, client: TestClient
    ) -> None:
        headers = _owner_headers(workspace)
        _activate(client, headers)
        # audit_export needs no executor / ack / token — a genuinely supported transition.
        resp = client.post(
            "/api/capability-gates/audit_export/set",
            json={"target_state": "enabled_policy_gated", "reason": "enable export"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        types = {e["event_type"] for e in SQLiteStore(workspace).list_event_index(limit=200)}
        assert "capability_transition_requested" in types
        assert "capability_enabled" in types

    def test_fail_closed_cap_cannot_be_enabled(self, workspace: Path, client: TestClient) -> None:
        headers = _owner_headers(workspace)
        _activate(client, headers)
        # hardware_operator_runtime has no registered executor → fail-closed / deferred.
        resp = client.post(
            "/api/capability-gates/hardware_operator_runtime/set",
            json={"target_state": "enabled_runtime", "reason": "try"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"].startswith("activation_blocked:no_executor")

    def test_fail_closed_cap_has_no_enable_transition(
        self, workspace: Path, client: TestClient
    ) -> None:
        headers = _owner_headers(workspace)
        _activate(client, headers)
        gate = client.get(
            "/api/capability-gates/hardware_operator_runtime", headers=headers
        ).json()
        # The UI uses allowed_transitions to decide enableability: no-executor caps expose no
        # enabled_policy_gated / enabled_runtime target.
        assert "enabled_policy_gated" not in gate["allowed_transitions"]
        assert "enabled_runtime" not in gate["allowed_transitions"]

    def test_confirmation_token_is_forwarded_for_tier2(
        self, workspace: Path, client: TestClient
    ) -> None:
        headers = _owner_headers(workspace)
        _activate(client, headers)
        # web_fetch (Tier-2) needs a recorded threat-model ack and a human confirmation token.
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
                " VALUES (?, ?, ?, ?)",
                ("web_fetch", "principal_rahul", utc_now(), "m5"),
            )
        # Without the token the activation check blocks it.
        without = client.post(
            "/api/capability-gates/web_fetch/set",
            json={"target_state": "enabled_runtime", "reason": "m5"},
            headers=headers,
        )
        assert without.status_code == 403
        # With the token forwarded through the existing route it succeeds.
        with_token = client.post(
            "/api/capability-gates/web_fetch/set",
            json={"target_state": "enabled_runtime", "reason": "m5", "confirmation_token": "tok-123"},
            headers=headers,
        )
        assert with_token.status_code == 200
        assert with_token.json()["ok"] is True

    def test_unauthorized_human_is_blocked(self, workspace: Path, client: TestClient) -> None:
        # A human principal that is not a runtime_gate_manager cannot flip gates.
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_bob", "human", "Bob", "[]", "[]", "development_preview", utc_now(), 1),
            )
        raw, _ = ApiSessionStore(workspace).create_session("principal_bob")
        resp = client.post(
            "/api/capability-gates/audit_export/set",
            json={"target_state": "enabled_policy_gated", "reason": "x"},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["ok"] is False
