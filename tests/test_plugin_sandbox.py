"""Installed plugin code runs in the native boundary, holding only its folder."""

import sys
from pathlib import Path

import pytest

from raiker.runtime.executors.sandbox import run_command


def test_a_real_plugin_runs_but_cannot_read_the_project(tmp_path: Path) -> None:
    from raiker.execution.commands.backends.native import NativeSandboxDriver

    ws = tmp_path / "ws"
    (ws / ".raiker").mkdir(parents=True)
    if not NativeSandboxDriver(ws).probe().available:
        pytest.skip("no enforced native boundary on this host")
    secret = ws / "notes.txt"
    secret.write_text("project file", encoding="utf-8")
    (ws / "plugins" / "demo").mkdir(parents=True)
    (ws / "plugins" / "demo" / "main.py").write_text(
        "import sys\n"
        "try:\n"
        f"    open({str(secret)!r}).read(); print('read')\n"
        "except OSError:\n"
        "    print('refused')\n",
        encoding="utf-8",
    )
    result = run_command(
        ["python" if sys.platform == "win32" else "python3", "plugins/demo/main.py"],
        cwd=ws,
        timeout=30,
        allowlist=frozenset({"python", "python3"}),
    )
    assert result["returncode"] == 0, result["stderr"]
    assert result["stdout"].strip() == "refused"
