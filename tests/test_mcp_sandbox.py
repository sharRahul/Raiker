"""Local stdio MCP servers run in the native boundary, holding only their folder."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.execution.commands import sandboxed_program
from raiker.execution.commands.sandboxed_program import ProgramRefused
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.mcp import McpConnectorExecutor
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "servers" / "weather" / "lib").mkdir(parents=True)
    (ws / "servers" / "weather" / "server.py").write_text("pass\n", encoding="utf-8")
    (ws / "servers" / "weather" / "lib" / "data.json").write_text("{}", encoding="utf-8")
    (ws / "servers" / "weather" / ".git").mkdir()
    (ws / "servers" / "weather" / ".git" / "config").write_text("x", encoding="utf-8")
    (ws / "notes.txt").write_text("project file", encoding="utf-8")
    return ws


def test_the_server_folder_is_staged_and_its_arguments_rewritten(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    target = tmp_path / "scratch"
    server, args = sandboxed_program.stage_program_folder(
        ws, ["servers/weather/server.py", "--data", "servers/weather/lib/data.json", "-v"], target
    )
    assert server == target
    assert args == ["server.py", "--data", "lib/data.json", "-v"]
    assert (target / "lib" / "data.json").exists()
    assert not (target / ".git").exists()
    assert not (target / "notes.txt").exists()


def test_an_argument_outside_the_server_folder_is_refused(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    with pytest.raises(ProgramRefused, match="sandbox_argument_outside_program_folder"):
        sandboxed_program.stage_program_folder(ws, ["servers/weather/server.py", "notes.txt"], tmp_path / "scratch")


def test_an_interpreter_in_the_project_or_home_is_passed_over(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    (ws / "bin").mkdir(parents=True)
    fake = ws / "bin" / ("python.exe" if sys.platform == "win32" else "python")
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    with pytest.raises(FileNotFoundError):
        sandboxed_program.sandbox_interpreter("python", str(ws / "bin"), ws.resolve())


_PEEK = '''\
import json, os, sys
for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        result = {"protocolVersion": "2026-07-28", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "peek", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "peek", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        project = os.environ["PEEK_TARGET"]
        try:
            with open(project, encoding="utf-8") as handle:
                seen = handle.read()
        except OSError as error:
            seen = "refused:" + type(error).__name__
        result = {"content": [{"type": "text", "text": json.dumps({"seen": seen})}]}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message.get("id"), "result": result}), flush=True)
'''


def test_a_real_server_cannot_read_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real boundary: the server answers, and the project file is out of reach."""
    from raiker.execution.commands.backends.native import NativeSandboxDriver

    ws = _workspace(tmp_path)
    (ws / ".raiker").mkdir()
    if not NativeSandboxDriver(ws).probe().available:
        pytest.skip("no enforced native boundary on this host")
    (ws / "servers" / "weather" / "server.py").write_text(_PEEK, encoding="utf-8")
    monkeypatch.setenv("RAIKER_MCP_ENV_ALLOWLIST", "PEEK_TARGET")
    monkeypatch.setenv("PEEK_TARGET", str(ws / "notes.txt"))
    texts: list[str] = []
    executor = McpConnectorExecutor(ws, SQLiteStore(ws), content_sink=lambda text: texts.append(str(text)))
    result = executor.execute(
        governed_action(
            "mcp_call_tool",
            principal_id="principal_owner",
            risk_level=RiskLevelValue.MEDIUM,
            arguments={"command": ["python3" if sys.platform != "win32" else "python",
                                   "servers/weather/server.py"], "tool_name": "peek"},
        ),
        SimpleNamespace(principal_id="principal_owner"),  # type: ignore[arg-type]
    )
    assert result.ok, result.reason_code
    seen = json.loads("".join(texts))["seen"]
    assert seen.startswith("refused:"), seen


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux mounts toolchains")
def test_only_an_interpreter_prefix_outside_usr_is_mounted(tmp_path: Path) -> None:
    from raiker.execution.commands.backends.native import toolchain_mounts

    prefix = tmp_path / "opt" / "python"
    (prefix / "bin").mkdir(parents=True)
    (prefix / "bin" / "python").write_text("", encoding="utf-8")
    (prefix / "bin" / "cargo").write_text("", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    assert toolchain_mounts(prefix / "bin" / "python", ws) == [str(prefix)]
    assert toolchain_mounts(prefix / "bin" / "cargo", ws) == []
    assert toolchain_mounts("/usr/bin/python3", ws) == []
    inside = ws / ".venv" / "bin"
    inside.mkdir(parents=True)
    (inside / "python").write_text("", encoding="utf-8")
    assert toolchain_mounts(inside / "python", ws) == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux mounts toolchains")
def test_a_link_in_the_copy_never_mounts_a_home_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.execution.commands.backends.native import toolchain_mounts

    home = tmp_path / "home" / "owner"
    (home / "notes" / "bin").mkdir(parents=True)
    (home / "notes" / "bin" / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    ws = tmp_path / "copy"
    (ws / ".venv" / "bin").mkdir(parents=True)
    link = ws / ".venv" / "bin" / "python"
    link.symlink_to(home / "notes" / "bin" / "python")
    assert toolchain_mounts(link, ws) == []
    # Nor any other user's home, nor a target that is not an interpreter.
    other = Path("/home/someone/bin/python")
    assert toolchain_mounts(other, ws) == []
    secret = tmp_path / "opt" / "tool" / "bin" / "secrets.txt"
    secret.parent.mkdir(parents=True)
    secret.write_text("", encoding="utf-8")
    renamed = ws / ".venv" / "bin" / "python3"
    renamed.symlink_to(secret)
    assert toolchain_mounts(renamed, ws) == []
