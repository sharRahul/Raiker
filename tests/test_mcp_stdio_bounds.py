"""Local stdio must remain unavailable until it has a native sandbox broker."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from raiker.runtime.executors.mcp import run_bounded_stdio
from raiker.runtime.executors.sandbox import SandboxError


def test_local_stdio_is_refused_before_the_server_starts(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    code = f"from pathlib import Path; Path({str(marker)!r}).write_text('started')"
    with pytest.raises(SandboxError, match="native_sandbox_required"):
        run_bounded_stdio(
            [sys.executable, "-c", code], b"", cwd=str(tmp_path),
            env=dict(os.environ), timeout=1,
        )
    assert not marker.exists()
