"""Contract guard: every field the typed web client (apps/web/src/lib/apiTypes.ts) reads must
exist in the corresponding backend response. The check is directional — the backend may include
extra fields (e.g. schema_version) — but it must never drop a key the UI depends on. If this fails,
the frontend interface and the backend DTO have drifted and must be reconciled.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.storage.sqlite import SQLiteStore

# Key sets transcribed from apps/web/src/lib/apiTypes.ts (required, client-read fields).
AUTH_SESSION = {"token", "session_id", "principal_id", "expires_at"}
CAPABILITY_GATE = {
    "capability", "phase", "state", "default_state", "source", "runtime_enabled",
    "allowed_transitions", "can_current_principal_change", "blocked_reason_code", "readiness",
    "decision_mode",
}
RUNTIME_MODE = {"mode_name", "status", "activated_by", "activated_at", "reason", "allowed_modes"}
RUNTIME_READINESS = {"mode", "gates", "summary"}
DIAGNOSTICS = {
    "runtime_mode", "production_ready_local_single_user_runtime", "summary",
    "disabled_capabilities", "counts", "readiness", "missing_config", "provider_health", "scope_note",
}
PROVIDER_HEALTH = {
    "profile_id", "provider", "model", "endpoint_kind", "local_only", "requires_network",
    "selected", "status", "detail",
}
MODELS_VIEW = {
    "profiles", "current_profile_id", "hosted_model_gate_state",
    "private_network_model_gate_state", "model_egress_allowlist_configured",
    "remote_profile_count", "no_silent_hosted_fallback",
}
MODEL_PROFILE = {
    "profile_id", "provider", "model", "default_state", "local_only", "requires_network",
    "endpoint_kind", "requires_egress_policy", "requires_budget_policy", "runtime_gate",
    "off_machine", "selected",
}
EVENT_ENTRY = {"event_id", "session_id", "turn_id", "event_type", "actor", "timestamp", "risk_level", "summary"}
CHECKPOINT = {
    "checkpoint_id", "session_id", "turn_id", "task_id", "checkpoint_type", "created_at",
    "summary", "last_event_id", "can_restore_state", "can_restore_files",
}
SESSION_SUMMARY = {"session_id", "title", "status", "created_at", "updated_at", "turn_count"}
TASK_VIEW = {
    "task_id", "session_id", "status", "title", "objective", "current_step", "progress_percent",
    "created_at", "updated_at", "completed_at", "summary",
}
APPROVAL_VIEW = {
    "approval_id", "action_id", "status", "tool_name", "capability", "risk_level", "session_id",
    "turn_id", "created_at", "age_seconds", "requires_approval", "executes_action",
}
APPROVAL_DETAIL = {"approval", "arguments", "diff", "diff_path", "preview_kind", "metadata_only_notice"}
AGENT_RESPONSE = {
    "request_id", "session_id", "turn_id", "status", "message", "events_path", "checkpoint_path",
    "approval", "last_event_id",
}


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
    return str(client.post("/api/auth/session", json={"as_principal": None}).json()["token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_contract(expected: set[str], actual: dict[str, object], name: str) -> None:
    missing = expected - set(actual)
    assert not missing, f"{name}: backend response is missing client-read keys {sorted(missing)}"


def _seed_approval(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    store.create_session("sess_c", str(workspace))
    action = ToolAction(
        action_id="act_c",
        tool_name="write_file",
        arguments={"path": "c.txt", "text": "hi"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_c", turn_id="turn_c", status="approval_required")
    store.insert_approval("appr_c", action)


class TestObjectContracts:
    def test_auth_session(self, client: TestClient) -> None:
        body = client.post("/api/auth/session", json={"as_principal": None}).json()
        _assert_contract(AUTH_SESSION, body, "AuthSession")

    def test_runtime_mode_and_readiness(self, client: TestClient) -> None:
        h = _headers(_token(client))
        _assert_contract(RUNTIME_MODE, client.get("/api/runtime-mode", headers=h).json(), "RuntimeMode")
        readiness = client.get("/api/runtime-readiness", headers=h).json()
        _assert_contract(RUNTIME_READINESS, readiness, "RuntimeReadiness")
        _assert_contract(CAPABILITY_GATE, readiness["gates"][0], "CapabilityGate (readiness.gates)")

    def test_capability_gate(self, client: TestClient) -> None:
        h = _headers(_token(client))
        gates = client.get("/api/capability-gates", headers=h).json()
        _assert_contract(CAPABILITY_GATE, gates[0], "CapabilityGate")

    def test_diagnostics_and_provider_health(self, client: TestClient) -> None:
        h = _headers(_token(client))
        diag = client.get("/api/diagnostics", headers=h).json()
        _assert_contract(DIAGNOSTICS, diag, "Diagnostics")
        _assert_contract(PROVIDER_HEALTH, diag["provider_health"][0], "ProviderHealth")

    def test_models(self, client: TestClient) -> None:
        h = _headers(_token(client))
        models = client.get("/api/models", headers=h).json()
        _assert_contract(MODELS_VIEW, models, "ModelsView")
        _assert_contract(MODEL_PROFILE, models["profiles"][0], "ModelProfile")

    def test_agent_response(self, client: TestClient) -> None:
        h = _headers(_token(client))
        body = client.post("/api/prompts", json={"text": "hello"}, headers=h).json()
        _assert_contract(AGENT_RESPONSE, body, "AgentResponse")


class TestListContracts:
    def test_sessions_events_checkpoints(self, client: TestClient) -> None:
        h = _headers(_token(client))
        # A governed turn seeds a session, events and a checkpoint.
        client.post("/api/prompts", json={"text": "hello"}, headers=h)
        _assert_contract(SESSION_SUMMARY, client.get("/api/sessions", headers=h).json()[0], "SessionSummary")
        _assert_contract(EVENT_ENTRY, client.get("/api/events", headers=h).json()[0], "EventEntry")
        _assert_contract(CHECKPOINT, client.get("/api/checkpoints", headers=h).json()[0], "Checkpoint")

    def test_tasks(self, workspace: Path, client: TestClient) -> None:
        from raiker.events.writer import EventLogWriter
        from raiker.tasks.manager import TaskManager

        store = SQLiteStore(workspace)
        store.create_session("sess_t", str(workspace))
        TaskManager(store, EventLogWriter(store)).create_task(
            session_id="sess_t", title="t", objective="o"
        )
        h = _headers(_token(client))
        _assert_contract(TASK_VIEW, client.get("/api/tasks", headers=h).json()[0], "TaskView")

    def test_approvals(self, workspace: Path, client: TestClient) -> None:
        _seed_approval(workspace)
        h = _headers(_token(client))
        _assert_contract(APPROVAL_VIEW, client.get("/api/approvals", headers=h).json()[0], "ApprovalView")
        detail = client.get("/api/approvals/appr_c", headers=h).json()
        _assert_contract(APPROVAL_DETAIL, detail, "ApprovalDetailView")
        _assert_contract(APPROVAL_VIEW, detail["approval"], "ApprovalView (detail.approval)")
