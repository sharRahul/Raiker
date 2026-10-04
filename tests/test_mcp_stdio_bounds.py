"""DEC-25 — a local MCP server's output is bounded while it is read.

``Popen.communicate()`` held both pipes in memory in full before the size check
could run, so a server that wrote gigabytes cost gigabytes before Raiker said no.
These run real child processes through :func:`run_bounded_stdio`, the way the
stdio session runs a server.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from raiker.runtime.executors.mcp import run_bounded_stdio


def _run(code: str, tmp_path: Path, **kwargs: object):  # type: ignore[no-untyped-def]
    return run_bounded_stdio(
        [sys.executable, "-c", code],
        b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
        cwd=str(tmp_path),
        env={**os.environ},
        **kwargs,  # type: ignore[arg-type]
    )


def test_an_ordinary_session_reads_everything_it_was_sent(tmp_path: Path) -> None:
    session = _run(
        "import sys; line = sys.stdin.readline(); sys.stdout.write(line); "
        "sys.stderr.write('note')",
        tmp_path,
        timeout=20,
    )
    assert session.stdout == b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    assert session.stderr_tail == b"note"
    assert not session.overflowed and not session.timed_out


def test_a_flood_on_stdout_stops_at_the_bound_and_stops_the_server(tmp_path: Path) -> None:
    started = time.monotonic()
    session = _run(
        "import sys\nwhile True: sys.stdout.write('x' * 65536)",
        tmp_path,
        timeout=30,
        max_stdout=100_000,
    )
    assert session.overflowed
    assert len(session.stdout) <= 100_000
    # Stopped at the bound, not at the timeout.
    assert time.monotonic() - started < 20


def test_a_flood_on_stderr_is_drained_and_only_its_tail_kept(tmp_path: Path) -> None:
    # Five megabytes on stderr would fill a pipe nobody read and hang the
    # server before it answered; draining it is what lets the answer through.
    session = _run(
        "import sys\nsys.stderr.write('e' * 5_000_000 + 'END')\nsys.stdout.write('ok\\n')",
        tmp_path,
        timeout=30,
        stderr_tail=64,
    )
    assert session.stdout == b"ok\n"
    assert len(session.stderr_tail) == 64
    assert session.stderr_tail.endswith(b"END")


def test_a_server_that_never_ends_is_stopped_at_the_timeout(tmp_path: Path) -> None:
    session = _run("import time\ntime.sleep(60)", tmp_path, timeout=1)
    assert session.timed_out


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX")
def test_stopping_a_server_stops_what_it_started(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild.pid"
    code = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(marker)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    session = _run(code, tmp_path, timeout=2)
    assert session.timed_out
    grandchild = int(marker.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        # A reaped-but-not-yet-collected zombie still answers kill(0); its
        # state is what says it is gone.
        try:
            with open(f"/proc/{grandchild}/stat") as stat:
                if stat.read().split()[2] == "Z":
                    break
        except OSError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the server's own child outlived it")
