"""Process launchers never execute agent-controlled code on the host.

They run it in the native sandbox, or refuse. Either way a write to the host
path the child names never lands.
"""

import contextlib
import sys
from pathlib import Path

import pytest

from raiker.runtime.executors.mcp import run_bounded_stdio
from raiker.runtime.executors.sandbox import SandboxError, run_command
from raiker.runtime.executors.tier4_plugins import plugin_code_runtime


@pytest.mark.parametrize("launcher", ["command", "mcp"])
def test_a_launcher_never_starts_the_child_on_the_host(tmp_path: Path, launcher: str) -> None:
    marker = tmp_path / "executed"
    script = tmp_path / "child.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    with contextlib.suppress(SandboxError, FileNotFoundError):
        if launcher == "command":
            run_command([sys.executable, str(script)], cwd=tmp_path)
        else:
            run_bounded_stdio([sys.executable, str(script)], b"", cwd=str(tmp_path), env={}, timeout=5)
    assert not marker.exists()


def test_plugin_status_names_the_sandbox_and_never_the_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert plugin_code_runtime("demo")["where"] == "not_enabled"
    monkeypatch.setenv("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", "demo")
    status = plugin_code_runtime("demo")
    assert status["where"] == "native_sandbox"
    assert "native sandbox" in status["summary"].lower()
