"""Notify + instant kill switch + revocable auto-pause circuit breaker
(monitored MCP connections, Phase C).

Phase B raises redacted findings; Phase C turns them into *action*:

- Every finding raises a **notification** the owner can see.
- A **high-severity** finding auto-transitions the connection to ``paused``
  (a revocable circuit breaker) so further sessions are refused until the owner
  resumes — this is what keeps a frictionless-by-default posture safe when the
  owner is away.
- The owner has an instant **kill** switch (refuse everything) and a one-call
  **stop** (pause), both revocable with **resume**.
- Every transition emits its audit event and a notification.
- Pause / resume / kill are owner-scoped and human-only.

The containment gate lives in the connector path: before a session runs, a
``paused`` or ``killed`` connection fails closed with a clear, non-fabricated
reason (missing-prerequisite honesty, not an owner-facing ban).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.control.service import RuntimeControlService
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.mcp import McpBuilderExecutor, McpConnectorExecutor
from raiker.security.mcp_monitor import McpContainment, McpSessionMonitor, McpSessionTelemetry
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "cont_ws"
    ws.mkdir()
    return ws


def _principal(pid: str = "principal_owner") -> Any:
    return SimpleNamespace(principal_id=pid)


def _action(action_type: str, arguments: dict, *, principal_id: str = "principal_owner") -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=arguments,
        risk_level=RiskLevelValue.MEDIUM,
    )


def _seed_server(
    store: SQLiteStore,
    *,
    principal_id: str = "principal_owner",
    name: str = "remote",
    transport: str = "http",
    tools: list[str] | None = None,
    endpoint_url: str | None = "https://mcp.example.com/rpc",
) -> str:
    sid = new_id("mcp_")
    store.create_mcp_server(
        server_id=sid,
        principal_id=principal_id,
        name=name,
        command=[],
        template=None,
        transport=transport,
        status="created",
        tools=tools,
        endpoint_url=endpoint_url,
    )
    return sid


def _telemetry(server_id: str, **kw: Any) -> McpSessionTelemetry:
    base: dict[str, Any] = {
        "principal_id": "principal_owner",
        "server_id": server_id,
        "transport": "http",
        "operation": "mcp_call_tool",
        "hosts": ("mcp.example.com",),
        "tool_calls": 1,
        "tools": (),
        "bytes_in": 100,
        "bytes_out": 100,
        "error_count": 0,
        "outcome": "ok",
    }
    base.update(kw)
    return McpSessionTelemetry(**base)


def _build_echo_server(ws: Path, store: SQLiteStore) -> str:
    builder = McpBuilderExecutor(ws, store)
    result = builder.execute(
        _action("mcp_server_create", {"name": "echo", "template": "python-stdio-echo"}),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    return str(result.artifacts["path"])


def _row(store: SQLiteStore, sid: str, pid: str = "principal_owner") -> dict[str, Any]:
    row = store.get_mcp_server(sid, pid)
    assert row is not None
    return row


def _row_by_name(store: SQLiteStore, name: str, pid: str = "principal_owner") -> dict[str, Any]:
    row = store.get_mcp_server_by_name(pid, name)
    assert row is not None
    return row


# ── Monitor state storage ────────────────────────────────────────────────────


def test_new_connection_defaults_to_active_monitor_state(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    row = _row(store, sid)
    assert row.get("monitor_state") == "active"
    assert row.get("paused_reason") is None


def test_set_monitor_state_is_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    assert store.set_mcp_monitor_state(sid, "principal_owner", "paused", paused_reason="x") is True
    assert _row(store, sid)["monitor_state"] == "paused"
    # A different owner cannot flip another owner's connection.
    assert store.set_mcp_monitor_state(sid, "principal_other", "killed") is False
    assert _row(store, sid)["monitor_state"] == "paused"


# ── Notifications storage ────────────────────────────────────────────────────


def test_notifications_insert_list_and_mark_read(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    nid = store.insert_notification(
        principal_id="principal_owner", kind="anomaly", title="t", body="b"
    )
    rows = store.list_notifications("principal_owner")
    assert len(rows) == 1
    assert rows[0]["notification_id"] == nid
    assert rows[0]["read"] in (0, False)
    assert store.mark_notification_read(nid, "principal_owner") is True
    assert store.list_notifications("principal_owner", unread_only=True) == []
    # Owner isolation.
    assert store.list_notifications("principal_other") == []
    assert store.mark_notification_read(nid, "principal_other") is False


# ── Auto-pause circuit breaker (monitor) ─────────────────────────────────────


def test_high_severity_finding_auto_pauses_connection(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store, tools=["search", "fetch"])
    monitor = McpSessionMonitor(store)
    # Baseline first so the tool-set swap is measured against history.
    monitor.observe(_telemetry(sid, operation="mcp_connect", tools=("search", "fetch")))
    assert _row(store, sid)["monitor_state"] == "active"
    # A tool-set swap is high-severity → the circuit breaker trips.
    findings = monitor.observe(
        _telemetry(sid, operation="mcp_connect", tools=("search", "fetch", "exfiltrate"))
    )
    assert any(f.severity == "high" for f in findings)
    row = _row(store, sid)
    assert row["monitor_state"] == "paused"
    assert row["paused_reason"]
    assert row["paused_at"]
    # A pause event + a notification were raised.
    assert store.list_event_index(event_type="mcp_connection_paused")
    notes = store.list_notifications("principal_owner")
    assert any(n["kind"] == "connection_paused" for n in notes)


def test_every_finding_raises_a_notification(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid, hosts=("mcp.example.com",)))  # baseline, no finding
    assert store.list_notifications("principal_owner") == []
    # A medium finding (new host) still notifies, without pausing.
    monitor.observe(_telemetry(sid, hosts=("new.example.net",)))
    notes = store.list_notifications("principal_owner")
    assert any(n["kind"] == "anomaly" for n in notes)
    assert _row(store, sid)["monitor_state"] == "active"


def test_auto_pause_only_transitions_once_while_paused(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid))  # baseline
    # Two consecutive high-severity sessions; the connection pauses once and the
    # paused_at is not churned on the second (already paused).
    monitor.observe(_telemetry(sid, hosts=("a.new.host",), arg_sensitivity="credential_like"))
    first = _row(store, sid)
    assert first["monitor_state"] == "paused"
    monitor.observe(_telemetry(sid, hosts=("b.new.host",), arg_sensitivity="credential_like"))
    second = _row(store, sid)
    assert second["paused_at"] == first["paused_at"]
    pause_events = store.list_event_index(event_type="mcp_connection_paused")
    assert len(list(pause_events)) == 1


# ── Containment gate in the connector path ───────────────────────────────────


def test_paused_connection_refuses_further_sessions(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    # First connect succeeds and records the profile.
    ok = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert ok.ok is True, ok.reason_code
    server = _row_by_name(store, "echo")
    store.set_mcp_monitor_state(server["server_id"], "principal_owner", "paused", paused_reason="test")
    # Now the gate refuses the session with a clear, non-fabricated reason.
    blocked = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert blocked.ok is False
    assert blocked.reason_code == "mcp_connection_paused"


def test_killed_connection_refuses_all_sessions(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    server = _row_by_name(store, "echo")
    store.set_mcp_monitor_state(server["server_id"], "principal_owner", "killed")
    blocked = connector.execute(
        _action(
            "mcp_call_tool",
            {"command": ["python", rel], "name": "echo", "tool_name": "echo",
             "tool_arguments": {"text": "hi"}},
        ),
        _principal(),
    )
    assert blocked.ok is False
    assert blocked.reason_code == "mcp_connection_killed"


def test_resume_clears_pause_and_reallows_sessions(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    server = _row_by_name(store, "echo")
    sid = server["server_id"]
    store.set_mcp_monitor_state(sid, "principal_owner", "paused", paused_reason="test")
    containment = McpContainment(store)
    assert containment.resume("principal_owner", sid, source="owner") is True
    row = _row(store, sid)
    assert row["monitor_state"] == "active"
    assert row["paused_reason"] is None
    # And a session runs again.
    again = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert again.ok is True, again.reason_code


# ── Containment helper: transitions emit event + notification ────────────────


def test_containment_transitions_emit_event_and_notification(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    containment = McpContainment(store)
    assert containment.pause("principal_owner", sid, reason="manual", source="owner") is True
    assert containment.kill("principal_owner", sid, source="owner") is True
    assert containment.resume("principal_owner", sid, source="owner") is True
    assert store.list_event_index(event_type="mcp_connection_paused")
    assert store.list_event_index(event_type="mcp_connection_killed")
    assert store.list_event_index(event_type="mcp_connection_resumed")
    kinds = {n["kind"] for n in store.list_notifications("principal_owner")}
    assert {"connection_paused", "connection_killed", "connection_resumed"} <= kinds


# ── Control service: owner-scoped + human-only ───────────────────────────────


def _owner_service(ws: Path) -> tuple[RuntimeControlService, str, str]:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    store = SQLiteStore(ws)
    sid = _seed_server(store, principal_id="principal_owner", name="remote")
    return svc, sid, "principal_owner"


def test_owner_present_stop_pauses_in_one_call(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc, sid, _ = _owner_service(ws)
    result = svc.pause_mcp_server("principal_owner", sid, reason="stop")
    assert result.ok is True, result.reason_code
    assert result.data["monitor_state"] == "paused"
    assert _row(SQLiteStore(ws), sid)["monitor_state"] == "paused"


def test_kill_then_resume_via_control_service(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc, sid, _ = _owner_service(ws)
    assert svc.kill_mcp_server("principal_owner", sid).ok is True
    assert _row(SQLiteStore(ws), sid)["monitor_state"] == "killed"
    assert svc.resume_mcp_server("principal_owner", sid).ok is True
    assert _row(SQLiteStore(ws), sid)["monitor_state"] == "active"


def test_containment_rejects_ai_principal(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    store = SQLiteStore(ws)
    # Register an AI principal and give it a server row of its own.
    from raiker.runtime.authority.models import PrincipalType

    store.insert_principal(
        principal_id="principal_ai",
        principal_type=PrincipalType.AI_AGENT.value,
        display_name="Assistant",
        role_ids=("role_assistant",),
    )
    sid = _seed_server(store, principal_id="principal_ai", name="ai-remote")
    # Containment is human-only: an AI principal is refused (never the trust
    # anchor). Resolution rejects the AI principal before any state changes.
    result = svc.pause_mcp_server("principal_ai", sid)
    assert result.ok is False
    assert _row(store, sid, "principal_ai")["monitor_state"] == "active"


def test_containment_is_owner_scoped_unknown_for_foreign_server(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc, _sid, _ = _owner_service(ws)
    store = SQLiteStore(ws)
    other = _seed_server(store, principal_id="principal_other", name="theirs")
    result = svc.pause_mcp_server("principal_owner", other)
    assert result.ok is False
    assert result.reason_code is not None
    assert result.reason_code.startswith("unknown_mcp_server")
    # The other owner's connection is untouched.
    assert _row(store, other, "principal_other")["monitor_state"] == "active"


# ── Async scenario: unattended session trips a rule and is auto-contained ────


def test_unattended_high_severity_session_is_auto_paused_until_resume(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    # Baseline connect.
    connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    server = _row_by_name(store, "echo")
    sid = server["server_id"]
    # An unattended tool call handling a credential-shaped value on a brand-new
    # host would be high-severity; simulate the high-severity finding directly
    # through the monitor to prove the executor's own session then auto-contains.
    monitor = McpSessionMonitor(store)
    monitor.observe(
        _telemetry(
            sid, transport="stdio", hosts=("suspicious.new.host",),
            arg_sensitivity="credential_like",
        )
    )
    assert _row(store, sid)["monitor_state"] == "paused"
    # The very next session cannot continue.
    blocked = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert blocked.ok is False
    assert blocked.reason_code == "mcp_connection_paused"
    # Owner resumes; the connection works again.
    McpContainment(store).resume("principal_owner", sid, source="owner")
    resumed = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert resumed.ok is True, resumed.reason_code


# ── Management API (Phase C endpoints) ───────────────────────────────────────


def _mgmt_client(tmp_path: Path, sub: str = "cont_api") -> Any:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / sub
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    client = TestClient(create_app(ws))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return ws, client


def test_api_pause_resume_kill_flow(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "cont_flow")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    sid = client.get("/api/mcp/servers").json()[0]["server_id"]

    paused = client.post(f"/api/mcp/servers/{sid}/pause", json={"reason": "stop"})
    assert paused.status_code == 200, paused.text
    assert paused.json()["monitor_state"] == "paused"
    assert client.get("/api/mcp/servers").json()[0]["monitor_state"] == "paused"

    resumed = client.post(f"/api/mcp/servers/{sid}/resume")
    assert resumed.status_code == 200, resumed.text
    assert client.get("/api/mcp/servers").json()[0]["monitor_state"] == "active"

    killed = client.post(f"/api/mcp/servers/{sid}/kill")
    assert killed.status_code == 200, killed.text
    assert client.get("/api/mcp/servers").json()[0]["monitor_state"] == "killed"

    # A killed connection refuses a governed test-connect with a clear reason.
    blocked = client.post(f"/api/mcp/servers/{sid}/connect")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["reason_code"] == "mcp_connection_killed"


def test_api_notifications_surface_after_transition(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "cont_notes")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    sid = client.get("/api/mcp/servers").json()[0]["server_id"]
    client.post(f"/api/mcp/servers/{sid}/pause", json={"reason": "stop"})
    notes = client.get("/api/notifications").json()
    assert any(n["kind"] == "connection_paused" for n in notes)
    nid = notes[0]["notification_id"]
    assert client.post(f"/api/notifications/{nid}/read").status_code == 200
    assert client.get("/api/notifications?unread_only=true").json() == []


def test_api_findings_listing_is_owner_scoped(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "cont_find")
    store = SQLiteStore(ws)
    sid = _seed_server(store, principal_id="principal_owner", name="remote")
    store.insert_security_finding(
        principal_id="principal_owner", source="mcp_monitor", severity="high",
        code="tool_set_changed", summary="swap", redacted_detail={"added": ["x"]},
        subject_id=sid,
    )
    findings = client.get(f"/api/mcp/servers/{sid}/findings").json()
    assert any(f["code"] == "tool_set_changed" for f in findings)


def test_api_containment_requires_auth(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / "cont_noauth"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    client = TestClient(create_app(ws))
    assert client.post("/api/mcp/servers/whatever/pause").status_code == 401
    assert client.get("/api/notifications").status_code == 401


def test_api_pause_foreign_server_is_owner_scoped(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "cont_iso")
    store = SQLiteStore(ws)
    other = _seed_server(store, principal_id="principal_other", name="theirs")
    resp = client.post(f"/api/mcp/servers/{other}/pause")
    assert resp.status_code == 403
    assert _row(store, other, "principal_other")["monitor_state"] == "active"
