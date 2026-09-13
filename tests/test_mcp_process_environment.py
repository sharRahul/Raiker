"""SEC-MCP-01 — a local MCP server is started with an environment, not with ours.

``subprocess.Popen`` with no ``env`` means *inherit everything the parent has*.
Raiker's own process holds provider keys, credential references and internal
settings, and every stdio MCP server the owner connected was handed all of them.
The server did not have to be malicious for that to matter: a crash dump, a
debug log or a process listing leaks what a process was given.

This is not a restriction on the owner, which is the posture Raiker holds to.
The owner never asked for their Anthropic key to be in a weather server's
environment; the exposure was an inheritance nobody chose. An owner who *does*
want a server to have a named variable says so by name, and that grant is what
these tests exercise alongside the default.

The last test is the one that matters: a real local server, started the way the
product starts one, reporting what it was actually given.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raiker.contracts.ids import new_id
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.mcp import (
    McpConnectorExecutor,
    allowed_mcp_env_names,
    mcp_stdio_env,
)
from raiker.storage.sqlite import SQLiteStore


def _action(action_type: str, arguments: dict[str, Any]) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=arguments,
        risk_level=RiskLevelValue.MEDIUM,
    )


def _principal() -> Any:
    return SimpleNamespace(principal_id="principal_owner")


# ── the constructed environment ─────────────────────────────────────────────


def test_a_provider_key_is_not_handed_to_a_local_server() -> None:
    built = mcp_stdio_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/owner",
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "OPENAI_API_KEY": "sk-proj-secret",
            "RAIKER_VAULT_PASSPHRASE": "hunter2",
        }
    )
    assert built["PATH"] == "/usr/bin"
    assert built["HOME"] == "/home/owner"
    for secret in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "RAIKER_VAULT_PASSPHRASE"):
        assert secret not in built
    assert "sk-ant-secret" not in json.dumps(built)


def test_an_unset_name_is_absent_rather_than_empty() -> None:
    # An empty string and "not set" are different facts to the programs that
    # read these; inventing the first for the second breaks shell-style checks.
    built = mcp_stdio_env({"PATH": "/usr/bin"})
    assert "HOME" not in built
    assert built["PATH"] == "/usr/bin"


def test_the_child_can_decode_its_own_output() -> None:
    # A bounded session writes every request up front and closes stdin. A server
    # that buffers its answer, or cannot encode it, fails in a way nobody
    # diagnoses — so both are set, and neither overrides an owner's own value.
    assert mcp_stdio_env({})["PYTHONUNBUFFERED"] == "1"
    assert mcp_stdio_env({})["PYTHONIOENCODING"] == "utf-8"


def test_the_owner_can_grant_a_name_a_server_actually_needs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_MCP_ENV_ALLOWLIST", "MY_SERVER_TOKEN, NODE_PATH")
    assert allowed_mcp_env_names() == ("MY_SERVER_TOKEN", "NODE_PATH")
    built = mcp_stdio_env({"MY_SERVER_TOKEN": "abc", "NODE_PATH": "/n", "OTHER": "no"})
    assert built["MY_SERVER_TOKEN"] == "abc"
    assert built["NODE_PATH"] == "/n"
    assert "OTHER" not in built


def test_the_allowlist_cannot_grant_away_its_own_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Not a boundary against the owner — an owner who wants a server to have a
    # secret can hand it one directly, and Raiker does not stand between an
    # owner and their own machine. It is a guard against the accident of a
    # config line widening the boundary that config line is written against.
    monkeypatch.setenv(
        "RAIKER_MCP_ENV_ALLOWLIST", "RAIKER_MCP_ENV_ALLOWLIST,RAIKER_MCP_COMMAND_ALLOWLIST"
    )
    assert allowed_mcp_env_names() == ()
    built = mcp_stdio_env({"RAIKER_MCP_ENV_ALLOWLIST": "x", "RAIKER_MCP_COMMAND_ALLOWLIST": "y"})
    assert "RAIKER_MCP_ENV_ALLOWLIST" not in built
    assert "RAIKER_MCP_COMMAND_ALLOWLIST" not in built


def test_an_empty_allowlist_grants_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_MCP_ENV_ALLOWLIST", " , ,")
    assert allowed_mcp_env_names() == ()


# ── the same fact, from inside a real server ────────────────────────────────

#: A dependency-free stdio MCP server that reports what it was started with.
#:
#: It writes to a file rather than answering with the environment, because the
#: answer is redacted before it reaches the artifacts — which is correct, and
#: would make this test assert nothing. The file is the server's own record of
#: what it saw.
_ENV_PROBE_SERVER = '''\
import json
import os
import sys

with open(os.path.join(os.path.dirname(__file__), "seen_env.json"), "w") as handle:
    json.dump(sorted(os.environ), handle)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    if message.get("method") == "initialize":
        result = {
            "protocolVersion": "2026-07-28",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "env-probe", "version": "1"},
        }
    elif message.get("method") == "tools/list":
        result = {
            "tools": [
                {
                    "name": "probe",
                    "description": "Reports nothing.",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        }
    else:
        result = {"content": [{"type": "text", "text": "ok"}]}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message.get("id"), "result": result}) + "\\n")
    sys.stdout.flush()
'''


def test_a_real_local_server_never_sees_the_workspace_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = tmp_path / "env_ws"
    (ws / "servers").mkdir(parents=True)
    (ws / "servers" / "probe.py").write_text(_ENV_PROBE_SERVER, encoding="utf-8")
    store = SQLiteStore(ws)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-must-not-travel")
    monkeypatch.setenv("RAIKER_MCP_ENV_ALLOWLIST", "RAIKER_MCP_TEST_GRANTED")
    monkeypatch.setenv("RAIKER_MCP_TEST_GRANTED", "granted")
    # A name the owner did not grant, to prove the passthrough list is a list
    # and not merely "everything that does not look like a key".
    monkeypatch.setenv("RAIKER_MCP_TEST_UNGRANTED", "ungranted")

    connector = McpConnectorExecutor(ws, store)
    result = connector.execute(
        _action("mcp_list_tools", {"command": ["python", "servers/probe.py"]}), _principal()
    )
    assert result.ok is True, result.reason_code

    seen = json.loads((ws / "servers" / "seen_env.json").read_text(encoding="utf-8"))
    assert "ANTHROPIC_API_KEY" not in seen
    assert "RAIKER_MCP_TEST_UNGRANTED" not in seen
    # What the owner granted arrived, and so did what any program needs to run.
    assert "RAIKER_MCP_TEST_GRANTED" in seen
    if "PATH" in os.environ:
        assert "PATH" in seen
