"""M7 security regression suite for the local web dashboard surface.

These tests are guards: each one MUST fail if the corresponding governance property is
weakened. They exercise the same governed API the web UI uses, asserting the UI cannot bypass
policy / RuntimeAuthority, that disabled/deferred and sensitive-domain capabilities stay
un-enableable, that approval resolution is metadata-only (never executes), and that STOP/interrupts
remain human-only safe-boundary operations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import ToolAction
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

# Domains that stay fail-closed/unenableable (no real executor). reminder,
# calendar, and email are now real local-only executors, so they are governed-
# enableable and no longer belong in this "stays blocked" list.
SENSITIVE_DOMAIN_CAPS = [
    "finance_runtime",
    "investment_runtime",
    "medical_runtime",
    "cctv_runtime",
    "home_security_runtime",
    "hardware_operator_runtime",
]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _owner(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_rahul")
    return {"Authorization": f"Bearer {raw}"}


def _ai_principal(workspace: Path) -> dict[str, str]:
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("principal_ai", "ai_agent", "AI", '["assistant"]', "[]", "development_preview", utc_now(), 1),
        )
    raw, _ = ApiSessionStore(workspace).create_session("principal_ai")
    return {"Authorization": f"Bearer {raw}"}


def _activate(client: TestClient, headers: dict[str, str]) -> None:
    client.post(
        "/api/runtime-mode/activate",
        json={"mode_name": "local_single_user_runtime", "reason": "regression"},
        headers=headers,
    )


def _seed_pending_write_approval(workspace: Path) -> str:
    store = SQLiteStore(workspace)
    store.create_session("sess_r", str(workspace))
    action = ToolAction(
        action_id="act_r",
        tool_name="write_file",
        arguments={"path": "should_not_exist.txt", "text": "must not be written"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_r", turn_id="turn_r", status="approval_required")
    store.insert_approval("appr_r", action)
    return "appr_r"


# 1. UI/API actions cannot bypass policy / RuntimeAuthority.
class TestNoPolicyBypass:
    def test_dangerous_cap_enable_is_denied_without_acks(self, workspace: Path, client: TestClient) -> None:
        headers = _owner(workspace)
        _activate(client, headers)
        # shell_execution is Tier-2 and dangerous; with no threat-model ack / token it must be denied.
        resp = client.post(
            "/api/capability-gates/shell_execution/set",
            json={"target_state": "enabled_policy_gated", "reason": "bypass attempt"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["ok"] is False

    def test_unknown_resolve_field_is_rejected(self, workspace: Path, client: TestClient) -> None:
        approval_id = _seed_pending_write_approval(workspace)
        resp = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "x", "execute_now": True},
            headers=_owner(workspace),
        )
        # Smuggling an execute flag (or any unknown field) is rejected by the schema.
        assert resp.status_code == 422


# 2. Disabled/deferred capabilities are not enableable and expose no enabled transition.
class TestDeferredCapsNotEnableable:
    def test_no_executor_cap_cannot_be_enabled(self, workspace: Path, client: TestClient) -> None:
        headers = _owner(workspace)
        _activate(client, headers)
        gate = client.get("/api/capability-gates/vector_embedding_runtime", headers=headers).json()
        assert "enabled_runtime" not in gate["allowed_transitions"]
        assert "enabled_policy_gated" not in gate["allowed_transitions"]
        resp = client.post(
            "/api/capability-gates/vector_embedding_runtime/set",
            json={"target_state": "enabled_runtime", "reason": "try"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"].startswith("activation_blocked:no_executor")


# 3. Approval resolution is metadata-only — it records a decision and never executes.
class TestApprovalMetadataOnly:
    def test_approve_does_not_execute_the_action(self, workspace: Path, client: TestClient) -> None:
        approval_id = _seed_pending_write_approval(workspace)
        resp = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ok"},
            headers=_owner(workspace),
        )
        assert resp.status_code == 200
        assert resp.json()["executes_action"] is False
        # The proposed file must NOT have been written by resolving the approval.
        assert not (workspace / "should_not_exist.txt").exists()
        store = SQLiteStore(workspace)
        viewer = EventViewer(store)
        events = [
            e
            for e in store.list_event_index(session_id="sess_r", limit=200)
            if e["event_type"] == "approval_received"
        ]
        assert events, "approval_received event must be recorded"
        payload = viewer.read_event_payload(events[0]["event_id"])
        assert payload is not None
        # The durable event itself records that no action was executed.
        assert payload["payload"]["executes_action"] is False


# 4. Sensitive personal/physical domains stay blocked/deferred.
class TestSensitiveDomainsBlocked:
    @pytest.mark.parametrize("capability", SENSITIVE_DOMAIN_CAPS)
    def test_domain_disabled_and_unenableable(
        self, workspace: Path, client: TestClient, capability: str
    ) -> None:
        headers = _owner(workspace)
        _activate(client, headers)
        gate = client.get(f"/api/capability-gates/{capability}", headers=headers).json()
        assert gate["state"] in {"disabled", "planned"}
        assert "enabled_runtime" not in gate["allowed_transitions"]
        resp = client.post(
            f"/api/capability-gates/{capability}/set",
            json={"target_state": "enabled_runtime", "reason": "try"},
            headers=headers,
        )
        assert resp.status_code == 403


# 5. STOP is human-only and safe-boundary; AI cannot interrupt or mutate gates.
class TestStopAndAiAuthority:
    def test_ai_cannot_interrupt(self, workspace: Path, client: TestClient) -> None:
        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_x", "all": True},
            headers=_ai_principal(workspace),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "human_principal_required"

    def test_ai_cannot_mutate_gates(self, workspace: Path, client: TestClient) -> None:
        resp = client.post(
            "/api/capability-gates/audit_export/set",
            json={"target_state": "enabled_policy_gated", "reason": "ai try"},
            headers=_ai_principal(workspace),
        )
        assert resp.status_code == 403

    def test_human_stop_is_safe_boundary(self, workspace: Path, client: TestClient) -> None:
        store = SQLiteStore(workspace)
        store.create_session("sess_s", str(workspace))
        manager = TaskManager(store, EventLogWriter(store))
        task = manager.create_task(session_id="sess_s", title="demo", objective="do x")
        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_s", "all": True, "action_type": "cancel", "reason": "stop"},
            headers=_owner(workspace),
        )
        assert resp.status_code == 200
        assert resp.json()["safe_boundary"] is True
        types = {e["event_type"] for e in store.list_event_index(session_id="sess_s", limit=200)}
        assert {"interrupt_received", "safe_boundary_reached", "task_cancelled"} <= types
        assert store.load_task(task.task_id).status == "cancelled"  # type: ignore[union-attr]
