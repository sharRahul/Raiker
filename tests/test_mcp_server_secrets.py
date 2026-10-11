"""DEC-15 step 2 — a secret one local MCP server is given, and only that server.

"Replace inline secrets/environment values with purpose-bound secret handles.
Deliver only declared values to that server process and redact before
persistence/model exposure." The only way to give a server a credential was
``RAIKER_MCP_ENV_ALLOWLIST``, which hands the named variable from Raiker's own
environment to every local server. A server's secret now lives in the vault
under that server, is started with that server only, is never read back, and is
replaced in what the server writes before anything keeps it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.control.dashboard import DashboardService
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.mcp import McpConnectorExecutor
from raiker.runtime.mcp_secrets import REDACTED, redact_values, secret_env, validate_name
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action

OWNER = "principal_owner"
TOKEN = "ghp_live-token-for-weather-only"

#: Writes the two variables it was given to a file, then answers its one tool
#: with the token itself — the server that leaks, which is what redaction is for.
_PROBE = '''\
import json
import os
import sys

with open(os.path.join(os.path.dirname(__file__), os.environ.get("PROBE_OUT", "seen.json")), "w") as handle:
    json.dump({"token": os.environ.get("WEATHER_TOKEN"), "names": sorted(os.environ)}, handle)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2026-07-28", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "probe", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "leak", "description": "Says its token.",
                             "inputSchema": {"type": "object", "properties": {}}}]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": "token=" + str(os.environ.get("WEATHER_TOKEN"))}]}
    else:
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message.get("id"), "result": result}) + "\\n")
    sys.stdout.flush()
'''


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    (workspace / "servers").mkdir(parents=True)
    (workspace / "servers" / "weather.py").write_text(_PROBE, encoding="utf-8")
    (workspace / "servers" / "other.py").write_text(_PROBE, encoding="utf-8")
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    return workspace


def _server(store: SQLiteStore, name: str) -> str:
    server_id = new_id("mcp_")
    store.create_mcp_server(
        server_id=server_id, principal_id=OWNER, name=name,
        command=["python", f"servers/{name}.py"], status="connected",
    )
    return server_id


def _run(ws: Path, store: SQLiteStore, name: str, action_type: str = "mcp_list_tools", **extra: Any) -> Any:
    executor = McpConnectorExecutor(ws, store)
    return executor.execute(
        governed_action(
            action_type, principal_id=OWNER, risk_level=RiskLevelValue.MEDIUM,
            arguments={"command": ["python", f"servers/{name}.py"], **extra},
        ),
        SimpleNamespace(principal_id=OWNER),  # type: ignore[arg-type]
    )


def test_a_secret_reaches_its_own_server_and_no_other(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = DashboardService(ws)
    weather = _server(service.store, "weather")
    _server(service.store, "other")
    assert service.set_mcp_server_secret(OWNER, weather, "WEATHER_TOKEN", TOKEN).ok

    monkeypatch.setenv("PROBE_OUT", "seen.json")
    assert _run(ws, service.store, "weather").ok
    seen = json.loads((ws / "servers" / "seen.json").read_text(encoding="utf-8"))
    assert seen["token"] == TOKEN

    assert _run(ws, service.store, "other").ok
    seen = json.loads((ws / "servers" / "seen.json").read_text(encoding="utf-8"))
    assert seen["token"] is None and "WEATHER_TOKEN" not in seen["names"]


def test_what_a_server_writes_back_never_carries_its_secret(ws: Path) -> None:
    store = SQLiteStore(ws)
    weather = _server(store, "weather")
    assert DashboardService(ws).set_mcp_server_secret(OWNER, weather, "WEATHER_TOKEN", TOKEN).ok
    seen: list[str] = []
    executor = McpConnectorExecutor(ws, store, content_sink=lambda text: seen.append(str(text)))
    result = executor.execute(
        governed_action(
            "mcp_call_tool", principal_id=OWNER, risk_level=RiskLevelValue.MEDIUM,
            arguments={"command": ["python", "servers/weather.py"], "tool_name": "leak"},
        ),
        SimpleNamespace(principal_id=OWNER),  # type: ignore[arg-type]
    )
    assert result.ok, result.reason_code
    everything = json.dumps(result.artifacts) + result.summary + "".join(seen)
    assert TOKEN not in everything
    assert REDACTED in "".join(seen) or REDACTED in everything


def test_names_are_listed_and_values_are_never_returned(ws: Path) -> None:
    from raiker.api.app import create_app
    from raiker.api.sessions import ApiSessionStore

    store = SQLiteStore(ws)
    weather = _server(store, "weather")
    token, _ = ApiSessionStore(ws).create_session(OWNER)
    client = TestClient(create_app(workspace_root=ws))
    h = {"Authorization": f"Bearer {token}"}

    put = client.put(
        f"/api/mcp/servers/{weather}/secrets/WEATHER_TOKEN", json={"value": TOKEN}, headers=h
    )
    assert put.status_code == 200, put.text
    assert put.json()["names"] == ["WEATHER_TOKEN"]
    listed = client.get(f"/api/mcp/servers/{weather}/secrets", headers=h)
    servers = client.get("/api/mcp/servers", headers=h)
    for answer in (put, listed, servers):
        assert TOKEN not in answer.text
    assert listed.json()["names"] == ["WEATHER_TOKEN"] and listed.json()["updated_at"]
    row = next(s for s in servers.json() if s["server_id"] == weather)
    assert row["vault_env"] == ["WEATHER_TOKEN"]

    reserved = client.put(
        f"/api/mcp/servers/{weather}/secrets/PATH", json={"value": "/tmp/evil"}, headers=h
    )
    assert reserved.status_code == 422
    assert reserved.json()["detail"]["reason_code"] == "mcp_secret_name_reserved"

    gone = client.delete(f"/api/mcp/servers/{weather}/secrets/WEATHER_TOKEN", headers=h)
    assert gone.status_code == 200 and gone.json()["names"] == []
    missing = client.delete(f"/api/mcp/servers/{weather}/secrets/WEATHER_TOKEN", headers=h)
    assert missing.status_code == 404


def test_removing_the_server_removes_its_secrets(ws: Path) -> None:
    service = DashboardService(ws)
    weather = _server(service.store, "weather")
    assert service.set_mcp_server_secret(OWNER, weather, "WEATHER_TOKEN", TOKEN).ok
    assert service.delete_mcp_server(OWNER, weather).ok
    assert secret_env(service.store, OWNER, weather) == {}


def test_a_remote_server_has_no_process_to_give_a_secret_to(ws: Path) -> None:
    service = DashboardService(ws)
    server_id = new_id("mcp_")
    service.store.create_mcp_server(
        server_id=server_id, principal_id=OWNER, name="remote", command=[],
        transport="http", endpoint_url="https://mcp.example.com/mcp",
    )
    result = service.set_mcp_server_secret(OWNER, server_id, "WEATHER_TOKEN", TOKEN)
    assert result.reason_code == "mcp_secret_local_only"


def test_another_owner_cannot_read_or_set_a_servers_secrets(ws: Path) -> None:
    service = DashboardService(ws)
    weather = _server(service.store, "weather")
    assert service.set_mcp_server_secret(OWNER, weather, "WEATHER_TOKEN", TOKEN).ok
    assert secret_env(service.store, "principal_other", weather) == {}


def test_names_and_redaction_rules() -> None:
    assert validate_name("WEATHER_TOKEN") is None
    assert validate_name("weather") == "mcp_secret_name_invalid"
    assert validate_name("PATH") == "mcp_secret_name_reserved"
    assert validate_name("RAIKER_MCP_ENV_ALLOWLIST") == "mcp_secret_name_reserved"
    assert redact_values("a=s3cret-value b=x", ["s3cret-value", "x"]) == f"a={REDACTED} b=x"
