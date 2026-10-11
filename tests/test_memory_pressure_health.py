"""DEC-24 step 1 — memory left on this machine is a health fact, beside the disk.

Only what the operating system calls *available* counts — memory held by caches
is given back on demand — and a machine whose memory cannot be read is
``unknown``, never ``ok``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from raiker.control.dashboard_parts.models import _parse_meminfo, memory_pressure

GIB = 1024**3
MIB = 1024**2


@pytest.mark.parametrize(
    ("total", "available", "state"),
    [
        (32 * GIB, 8 * GIB, "ok"),
        # 10% available is an ordinary working machine, not an incident.
        (32 * GIB, int(3.2 * GIB), "ok"),
        (8 * GIB, 400 * MIB, "low"),
        # 4% of a large machine is still 5 GB, but relatively it is low.
        (128 * GIB, int(5.12 * GIB), "low"),
        (8 * GIB, 200 * MIB, "critical"),
        (256 * GIB, int(2.5 * GIB), "critical"),
    ],
)
def test_the_state_follows_absolute_and_relative_room(total: int, available: int, state: str) -> None:
    reading = memory_pressure(lambda: (available, total))
    assert reading == {"state": state, "available_bytes": available, "total_bytes": total}


def test_an_unreadable_machine_is_unknown_not_ok() -> None:
    assert memory_pressure(lambda: None) == {
        "state": "unknown",
        "available_bytes": None,
        "total_bytes": None,
    }

    def refuse() -> tuple[int, int]:
        raise OSError("no /proc")

    assert memory_pressure(refuse)["state"] == "unknown"


def test_linux_reads_the_kernels_available_estimate_not_free() -> None:
    text = "MemTotal:       16000000 kB\nMemFree:          100000 kB\nMemAvailable:    9000000 kB\n"
    assert _parse_meminfo(text) == (9000000 * 1024, 16000000 * 1024)


def test_an_old_kernel_without_an_estimate_is_unknown() -> None:
    """MemFree alone undercounts by every cache, so it is not used in its place."""
    assert _parse_meminfo("MemTotal: 1000 kB\nMemFree: 10 kB\n") is None


@pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="read on Windows and Linux only")
def test_this_machine_answers() -> None:
    reading = memory_pressure()
    assert reading["state"] in {"ok", "low", "critical"}
    assert isinstance(reading["total_bytes"], int) and reading["total_bytes"] > 0


def test_the_diagnostics_read_carries_it(tmp_path: Path) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.dashboard import DashboardService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    view = DashboardService(tmp_path).get_diagnostics(None)
    assert view.memory_pressure["state"] in {"ok", "low", "critical", "unknown"}
