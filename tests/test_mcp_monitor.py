"""Per-session MCP monitoring + anomaly detection (monitored MCP connections,
Phase B).

After each governed MCP session the connector executor hands *redacted*
telemetry to :class:`McpSessionMonitor`, which:

- writes one redacted ``mcp_session_log`` row (tool-call count, hosts, byte
  counts, error count, outcome — never payloads, tokens, or host secrets);
- forms a rolling per-connection baseline from prior session rows; and
- evaluates the anomaly rules (new host, volume spike, tool-set swap,
  sensitive-data *shape*, error/refusal burst). Each hit raises a redacted
  ``security_findings`` row and an ``mcp_anomaly_detected`` audit event.

The invariant proved throughout: no raw payload, token, or host secret ever
reaches a finding, an event, or a session-log row — only redacted metadata.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from raiker.contracts.ids import new_id
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.mcp import McpBuilderExecutor, McpConnectorExecutor
from raiker.security.mcp_monitor import (
    ERROR_BURST_THRESHOLD,
    McpSessionMonitor,
    McpSessionTelemetry,
    shape_sensitivity,
)
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "mon_ws"
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


# ── Session log: redacted, per-session ───────────────────────────────────────


def test_each_session_writes_a_redacted_session_log_row(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid, tool_calls=2, bytes_in=321, bytes_out=45, error_count=0))
    rows = store.list_mcp_session_logs(sid, "principal_owner")
    assert len(rows) == 1
    row = rows[0]
    assert row["server_id"] == sid
    assert row["tool_calls"] == 2
    assert row["bytes_in"] == 321
    assert row["bytes_out"] == 45
    assert row["error_count"] == 0
    assert row["outcome"] == "ok"
    assert row["hosts"] == ["mcp.example.com"]


def test_first_session_forms_baseline_without_anomalies(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    # The very first session for a connection establishes the baseline. Nothing
    # is "unusual" yet, so no findings are raised even for a new host.
    findings = monitor.observe(_telemetry(sid, hosts=("mcp.example.com",)))
    assert findings == []
    assert store.list_security_findings("principal_owner") == []


# ── Anomaly rules ────────────────────────────────────────────────────────────


def test_new_host_raises_finding_and_event(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid, hosts=("mcp.example.com",)))  # baseline
    findings = monitor.observe(_telemetry(sid, hosts=("evil.example.net",)))
    codes = {f.code for f in findings}
    assert "new_host" in codes
    stored = store.list_security_findings("principal_owner", source="mcp_monitor")
    assert any(f["code"] == "new_host" for f in stored)
    events = store.list_event_index(event_type="mcp_anomaly_detected")
    assert any(events)


def test_volume_spike_raises_finding(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    for _ in range(3):
        monitor.observe(_telemetry(sid, bytes_in=100, bytes_out=100))
    findings = monitor.observe(_telemetry(sid, bytes_in=50_000, bytes_out=50_000))
    assert any(f.code == "volume_spike" for f in findings)


def test_tool_set_swap_raises_high_severity_finding(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store, tools=["search", "fetch"])
    monitor = McpSessionMonitor(store)
    # Establish a baseline session first so this is not the connection's first.
    monitor.observe(_telemetry(sid, operation="mcp_connect", tools=("search", "fetch")))
    findings = monitor.observe(
        _telemetry(sid, operation="mcp_connect", tools=("search", "fetch", "exfiltrate"))
    )
    swap = [f for f in findings if f.code == "tool_set_changed"]
    assert swap, findings
    assert swap[0].severity == "high"
    assert "exfiltrate" in swap[0].detail.get("added", [])


def test_sensitive_shape_raises_finding_without_storing_value(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid))  # baseline
    findings = monitor.observe(_telemetry(sid, arg_sensitivity="credential_like"))
    assert any(f.code == "sensitive_shape" for f in findings)
    # Only the classification label is stored, never a raw value.
    stored = store.list_security_findings("principal_owner", source="mcp_monitor")
    sens = [f for f in stored if f["code"] == "sensitive_shape"][0]
    assert sens["redacted_detail"]["arg_sensitivity"] == "credential_like"


def test_new_host_plus_sensitive_shape_is_high_severity(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid, hosts=("mcp.example.com",)))  # baseline
    findings = monitor.observe(
        _telemetry(sid, hosts=("new.example.net",), arg_sensitivity="credential_like")
    )
    sens = [f for f in findings if f.code == "sensitive_shape"]
    assert sens and sens[0].severity == "high"


def test_error_burst_raises_finding(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    findings: list[Any] = []
    for _ in range(ERROR_BURST_THRESHOLD):
        findings = monitor.observe(_telemetry(sid, outcome="error", error_count=1))
    assert any(f.code == "error_burst" for f in findings)
    assert any(f.severity == "high" for f in findings if f.code == "error_burst")


def test_error_burst_fires_once_not_on_every_further_error(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    fired: list[str] = []
    # Six consecutive error sessions — the burst should be flagged exactly once,
    # when the threshold is first crossed, not again on every further error.
    for _ in range(ERROR_BURST_THRESHOLD + 3):
        result = monitor.observe(_telemetry(sid, outcome="error", error_count=1))
        fired.extend(f.code for f in result if f.code == "error_burst")
    assert fired.count("error_burst") == 1
    stored = store.list_security_findings("principal_owner", source="mcp_monitor")
    assert sum(1 for f in stored if f["code"] == "error_burst") == 1


# ── Redaction proof ──────────────────────────────────────────────────────────


def test_no_raw_value_reaches_log_finding_or_event(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    sid = _seed_server(store)
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid))  # baseline
    # Telemetry only ever carries redacted metadata — labels, counts, hosts.
    monitor.observe(
        _telemetry(sid, hosts=("new.example.net",), arg_sensitivity="credential_like", bytes_in=9)
    )
    secret_markers = ("Bearer", "password", "-----BEGIN")
    # session-log rows
    for row in store.list_mcp_session_logs(sid, "principal_owner"):
        blob = json.dumps(row)
        assert not any(m in blob for m in secret_markers)
    # findings
    for f in store.list_security_findings("principal_owner"):
        blob = json.dumps(f)
        assert not any(m in blob for m in secret_markers)
    # audit events on disk
    events_file = store.paths.events_dir / "mcp.jsonl"
    if events_file.exists():
        text = events_file.read_text()
        assert not any(m in text for m in secret_markers)


def test_shape_sensitivity_labels_secrets_only(tmp_path: Path) -> None:
    # A credential-like value is labelled; ordinary text returns None. The raw
    # value is never returned — only the label.
    assert shape_sensitivity("password: hunter2-supersecret-value") == "credential_like"
    assert shape_sensitivity("just a normal sentence") is None
    assert shape_sensitivity("") is None


# ── Owner isolation ──────────────────────────────────────────────────────────


def test_session_logs_and_findings_are_owner_isolated(tmp_path: Path) -> None:
    store = SQLiteStore(_ws(tmp_path))
    sid_a = _seed_server(store, principal_id="principal_a", name="a")
    monitor = McpSessionMonitor(store)
    monitor.observe(_telemetry(sid_a, principal_id="principal_a"))
    monitor.observe(
        _telemetry(sid_a, principal_id="principal_a", hosts=("brand.new.host",))
    )
    assert store.list_mcp_session_logs(sid_a, "principal_a")
    # A different owner sees none of it.
    assert store.list_mcp_session_logs(sid_a, "principal_b") == []
    assert store.list_security_findings("principal_a", source="mcp_monitor")
    assert store.list_security_findings("principal_b", source="mcp_monitor") == []


# ── End-to-end through the connector executor (real local stdio session) ─────


def _build_echo_server(ws: Path, store: SQLiteStore) -> str:
    builder = McpBuilderExecutor(ws, store)
    result = builder.execute(
        _action("mcp_server_create", {"name": "echo", "template": "python-stdio-echo"}),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    return str(result.artifacts["path"])


def test_executor_records_session_log_for_real_stdio_session(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    result = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert result.ok is True, result.reason_code
    # The governed session produced a redacted monitoring row for the connection.
    server = store.get_mcp_server_by_name("principal_owner", "echo")
    assert server is not None
    rows = store.list_mcp_session_logs(server["server_id"], "principal_owner")
    assert len(rows) == 1
    assert rows[0]["outcome"] == "ok"
    assert rows[0]["operation"] == "mcp_connect"


def test_executor_sensitive_call_shape_is_flagged_end_to_end(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    # Establish the connection + a baseline session first.
    connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    # Now echo back a credential-shaped argument. The monitor classifies its
    # *shape* transiently and records only the label — never the value.
    secret = "password: super-secret-credential-1234567890"
    result = connector.execute(
        _action(
            "mcp_call_tool",
            {"command": ["python", rel], "tool_name": "echo", "tool_arguments": {"text": secret}},
        ),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    findings = store.list_security_findings("principal_owner", source="mcp_monitor")
    assert any(f["code"] == "sensitive_shape" for f in findings)
    # The raw credential value never lands in any finding.
    assert all(secret not in json.dumps(f) for f in findings)
    server = store.get_mcp_server_by_name("principal_owner", "echo")
    assert server is not None
    for row in store.list_mcp_session_logs(server["server_id"], "principal_owner"):
        assert secret not in json.dumps(row)
