"""DEC-24 step 1 — free space on the workspace's volume is a health fact.

A full disk fails the database, a backup and an update's staging at once, so the
diagnostics read names it — ``low`` and ``critical`` by absolute and relative
room together — and an unreadable volume is ``unknown``, never ``ok``.
"""

from __future__ import annotations

import shutil
from collections import namedtuple
from pathlib import Path

import pytest

from raiker.control.dashboard_parts.models import storage_space

Usage = namedtuple("Usage", "total used free")
GIB = 1024**3


@pytest.mark.parametrize(
    ("total", "free", "state"),
    [
        (1000 * GIB, 500 * GIB, "ok"),
        # 3% of a large disk is still 30 GB: absolute room keeps it at low, not ok.
        (1000 * GIB, 30 * GIB, "low"),
        (10 * GIB, int(1.5 * GIB), "low"),
        (10 * GIB, 300 * 1024**2, "critical"),
        # 1% of a huge disk is critical however many bytes it is.
        (10_000 * GIB, 100 * GIB, "critical"),
    ],
)
def test_the_state_follows_absolute_and_relative_room(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, total: int, free: int, state: str
) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: Usage(total, total - free, free))
    reading = storage_space(tmp_path)
    assert reading["state"] == state
    assert reading["free_bytes"] == free
    assert reading["total_bytes"] == total


def test_an_unreadable_volume_is_unknown_not_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_path: object) -> Usage:
        raise OSError("gone")

    monkeypatch.setattr(shutil, "disk_usage", refuse)
    assert storage_space(tmp_path) == {"state": "unknown", "free_bytes": None, "total_bytes": None}


def test_the_diagnostics_read_carries_it(tmp_path: Path) -> None:
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.control.dashboard import DashboardService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    view = DashboardService(tmp_path).get_diagnostics(None)
    assert view.storage_space["state"] in {"ok", "low", "critical"}
    assert isinstance(view.storage_space["free_bytes"], int)
