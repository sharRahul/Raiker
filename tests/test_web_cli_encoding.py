"""CLI output must work with redirected Windows code-page streams."""
import os
import subprocess
import sys


def test_web_help_supports_cp1252_output() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "raiker.api.serve", "--help"],
        env={**os.environ, "PYTHONIOENCODING": "cp1252:strict"},
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("cp1252")
    assert b"--private-host" in result.stdout
    assert b"two-step sign-in" in result.stdout
