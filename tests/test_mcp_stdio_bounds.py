"""Local stdio never starts a server on the host: it is sandboxed or refused."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

from raiker.runtime.executors.mcp import run_bounded_stdio
from raiker.runtime.executors.sandbox import SandboxError


def test_a_local_server_never_writes_the_host(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    code = f"from pathlib import Path; Path({str(marker)!r}).write_text('started')"
    with contextlib.suppress(SandboxError, FileNotFoundError):
        run_bounded_stdio(
            [sys.executable, "-c", code], b"", cwd=str(tmp_path),
            env=dict(os.environ), timeout=5,
        )
    assert not marker.exists()
