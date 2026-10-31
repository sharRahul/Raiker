"""Legacy process launchers must not execute agent-controlled code on the host."""

import sys
from pathlib import Path

import pytest

from raiker.runtime.executors.mcp import run_bounded_stdio
from raiker.runtime.executors.sandbox import SandboxError, run_command
from raiker.runtime.executors.tier4_plugins import plugin_code_runtime


@pytest.mark.parametrize("launcher", ["command", "mcp"])
def test_legacy_launcher_refuses_without_starting_child(tmp_path: Path, launcher: str) -> None:
    marker = tmp_path / "executed"
    script = tmp_path / "child.py"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    with pytest.raises(SandboxError, match="native_sandbox_required"):
        if launcher == "command":
            run_command([sys.executable, str(script)], cwd=tmp_path)
        else:
            run_bounded_stdio([sys.executable, str(script)], b"", cwd=str(tmp_path), env={}, timeout=5)
    assert not marker.exists()


def test_plugin_status_does_not_claim_disabled_execution_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", "demo")
    status = plugin_code_runtime("demo")
    assert status["where"] == "not_enabled"
    assert "native sandbox" in status["summary"].lower()
