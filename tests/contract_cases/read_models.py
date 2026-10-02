"""Read-model views a service method returns (Stage A, and the routes it found eligible)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, Seed, first, plain, then, with_turn
from tests.factories import tool_action


def _approval(_ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    store = SQLiteStore(_ws)
    store.create_session("sess_c", str(_ws))
    action = tool_action(
        "write_file", {"path": "c.txt", "text": "hi"}, action_id="act_c",
        risk_level="high", requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_c", turn_id="turn_c", status="approval_required")
    store.insert_approval("appr_c", action)
    return "/api/approvals"


def _memory(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    write_memory(
        "Remember this", workspace_root=ws, store=SQLiteStore(ws),
        governance=MemoryGovernance(
            "evt_c", "", None, "test", 1.0, 1.0, "until_forget", "approved", "principal_owner"
        ),
    )
    return "/api/memory"


def _task(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    from raiker.events.writer import EventLogWriter
    from raiker.tasks.manager import TaskManager

    store = SQLiteStore(ws)
    store.create_session("sess_t", str(ws))
    TaskManager(store, EventLogWriter(store)).create_task(session_id="sess_t", title="t", objective="o")
    return "/api/tasks"


def _project(_ws: Path, client: TestClient, h: dict[str, str]) -> str:
    client.post("/api/projects", json={"name": "Alpha"}, headers=h)
    return "/api/projects"


def _repo(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    (ws / "projects" / "app").mkdir(parents=True)
    client.post("/api/code/repos", json={"kind": "local", "path": "projects/app"}, headers=h)
    return "/api/code/repos"


def _mcp(suffix: str) -> Seed:
    def seed(_ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
        store = SQLiteStore(_ws)
        store.create_mcp_server(
            server_id="mcp_contract", principal_id="principal_owner", name="contract",
            command=["python", "server.py"], template="python-stdio-echo", status="connected",
        )
        store.insert_mcp_session_log(
            server_id="mcp_contract", principal_id="principal_owner", transport="stdio",
            operation="tools/list", hosts=[], tool_calls=0, bytes_in=0, bytes_out=0,
            error_count=0, outcome="ok", started_at="2026-07-18T10:00:00Z",
        )
        return "/api/mcp/servers" + suffix

    return seed


def _finding(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    store = SQLiteStore(ws)
    finding_id = store.insert_security_finding(
        principal_id="principal_owner", source="mcp_monitor", severity="medium", code="probe",
        summary="A probe finding", redacted_detail={"count": 1}, subject_id="mcp_contract",
    )
    store.insert_notification(
        principal_id="principal_owner", kind="security_finding", title="Probe",
        body="A probe finding", finding_id=finding_id, subject_id="mcp_contract",
    )
    return finding_id


def _credential(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    from raiker.runtime.connector_ecosystem import ConnectorVault
    from raiker.security.credentials import CredentialLifecycle

    store = SQLiteStore(ws)
    ConnectorVault(store).put("principal_owner", "github", {"token": "ghp_contract"})
    CredentialLifecycle(store).record_verified("principal_owner", "github")
    return "github"


def _created_task(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/tasks", {"title": "Contract", "description": "Check the contract"}


def _mcp_finding(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _mcp("")(ws, client, h)
    _finding(ws, client, h)
    return "/api/mcp/servers/mcp_contract/findings"


def _turn(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    with_turn("")(ws, client, h)
    session_id = first(client, h, "/api/sessions", "session_id")
    return "/api/turns/" + str(SQLiteStore(ws).list_turns(session_id)[0]["turn_id"])


CASES: Cases = {
    ("GET", "/api/approvals"): _approval,
    ("GET", "/api/capability-gates"): plain("/api/capability-gates"),
    ("GET", "/api/checkpoints"): with_turn("/api/checkpoints"),
    ("GET", "/api/code/repos"): _repo,
    ("GET", "/api/connections"): plain("/api/connections"),
    ("GET", "/api/events"): with_turn("/api/events"),
    ("GET", "/api/extensions"): plain("/api/extensions"),
    ("GET", "/api/mcp/servers"): _mcp(""),
    ("GET", "/api/mcp/servers/{server_id}/sessions"): _mcp("/mcp_contract/sessions"),
    ("GET", "/api/memory"): _memory,
    ("GET", "/api/projects"): _project,
    ("GET", "/api/runtime-mode"): plain("/api/runtime-mode"),
    ("GET", "/api/runtime-readiness"): plain("/api/runtime-readiness"),
    ("GET", "/api/sessions"): with_turn("/api/sessions"),
    ("GET", "/api/tasks"): _task,
    ("GET", "/api/work-threads"): with_turn("/api/work-threads"),
    ("GET", "/api/work-threads/page"): with_turn("/api/work-threads/page"),
    ("GET", "/api/approvals/{approval_id}"): then(_approval, lambda c, h: "/api/approvals/appr_c"),
    ("GET", "/api/capability-gates/{capability}"): lambda _ws, c, h: (
        "/api/capability-gates/" + first(c, h, "/api/capability-gates", "capability")
    ),
    ("GET", "/api/chat-search"): with_turn("/api/chat-search?q=hello"),
    ("GET", "/api/checkpoints/{checkpoint_id}"): then(
        with_turn(""), lambda c, h: "/api/checkpoints/" + first(c, h, "/api/checkpoints", "checkpoint_id")
    ),
    ("GET", "/api/diagnostics"): plain("/api/diagnostics"),
    ("GET", "/api/mcp/servers/{server_id}/findings"): _mcp_finding,
    ("GET", "/api/memory/settings"): plain("/api/memory/settings"),
    ("GET", "/api/notifications"): then(_finding, lambda c, h: "/api/notifications"),
    ("GET", "/api/projects/{project_id}"): then(
        _project,
        lambda c, h: "/api/projects/" + c.get("/api/projects", headers=h).json()["projects"][0]["project_id"],
    ),
    ("POST", "/api/security/breach-check"): then(
        _finding, lambda c, h: ("/api/security/breach-check", {"password": "x", "enabled": False})
    ),
    ("GET", "/api/security/credentials"): then(_credential, lambda c, h: "/api/security/credentials"),
    ("POST", "/api/security/credentials/{provider}/verify"): then(
        _credential, lambda c, h: "/api/security/credentials/github/verify"
    ),
    ("GET", "/api/security/findings"): then(_finding, lambda c, h: "/api/security/findings"),
    ("POST", "/api/security/scan"): then(_finding, lambda c, h: "/api/security/scan"),
    ("GET", "/api/sessions/{session_id}/context-usage"): then(
        with_turn(""),
        lambda c, h: f"/api/sessions/{first(c, h, '/api/sessions', 'session_id')}/context-usage",
    ),
    ("POST", "/api/tasks"): _created_task,
    ("GET", "/api/tasks/{task_id}"): then(
        _task, lambda c, h: "/api/tasks/" + first(c, h, "/api/tasks", "task_id")
    ),
    ("POST", "/api/tasks/{task_id}/run"): then(
        _task, lambda c, h: f"/api/tasks/{first(c, h, '/api/tasks', 'task_id')}/run"
    ),
    ("GET", "/api/turns/{turn_id}"): _turn,
}


