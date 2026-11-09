# SPDX-License-Identifier: Apache-2.0
"""Real ENOSPC on an explicitly supplied, small disposable Linux tmpfs.

Mount an empty tmpfs of 16 MiB, make it writable by the test user, then set
RAIKER_STORAGE_FAULT_ROOT to its mount point. The test refuses ordinary disks
and populated mounts; it never fills the workspace's actual filesystem.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from raiker.execution import workspaces


def test_actual_storage_exhaustion_preserves_originals_and_recovers(tmp_path: Path) -> None:
    if sys.platform != "linux":
        pytest.skip("requires a disposable Linux tmpfs")
    configured = os.environ.get("RAIKER_STORAGE_FAULT_ROOT")
    if not configured:
        pytest.skip("requires an empty disposable tmpfs: RAIKER_STORAGE_FAULT_ROOT")
    mount = Path(configured).resolve()
    usage = shutil.disk_usage(mount)
    assert mount.is_mount(), "refusing to fill a directory on another filesystem"
    assert 8 * 1024**2 <= usage.total <= 32 * 1024**2, "requires a small dedicated filesystem"
    assert not list(mount.iterdir()), "requires an empty disposable mount"
    with tempfile.TemporaryDirectory(prefix="raiker-enospc-", dir=mount) as folder:
        base = Path(folder)
        project = base / "project"
        project.mkdir()
        originals = {"README.md": b"owner readme", "app.py": b"owner code"}
        for name, content in originals.items():
            (project / name).write_bytes(content)
        copy = workspaces.create_task_workspace(project, tmp_path / "copies", "storage")
        (copy.root / "README.md").write_text("reviewed readme")
        (copy.root / "app.py").write_bytes(b"x" * (2 * 1024**2))
        diff = workspaces.diff_workspace(copy)
        filler = base / "pressure.bin"
        filler.write_bytes(b"0" * (int(usage.total * .98) - shutil.disk_usage(mount).used))
        full = shutil.disk_usage(mount)
        journal = tmp_path / "journals"
        try:
            with pytest.raises(workspaces.WorkspaceError, match="workspace_rollback_incomplete"):
                workspaces.promote(copy, diff, journal_dir=journal)
            pending = list(journal.iterdir())
            assert len(pending) == 1
            assert workspaces._read_journal(pending[0])["state"] == "applying"
        finally:
            filler.unlink(missing_ok=True)
        assert workspaces.recover_promotions(journal) == [pending[0].name]
        assert {p.name: p.read_bytes() for p in project.iterdir()} == originals
        print(json.dumps({"filesystem_bytes": full.total, "used_fraction": full.used / full.total,
                          "originals_restored": True, "fault": "real ENOSPC"}))
