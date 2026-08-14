from __future__ import annotations

import os
from pathlib import Path

import pytest

from raiker.execution.commands.cache_snapshots import CacheSnapshotError, CacheSnapshotService


def test_cache_snapshot_accepts_regular_files_and_strips_execution_bits(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    script = source / "tool.sh"
    script.write_text("echo safe", encoding="utf-8")
    script.chmod(0o755)
    snapshot = CacheSnapshotService(max_files=10, max_bytes=1000).publish(source, target)
    assert snapshot.file_count == 1
    assert (target / "tool.sh").read_text(encoding="utf-8") == "echo safe"
    assert (target / "tool.sh").stat().st_mode & 0o111 == 0


def test_cache_snapshot_rejects_links_and_limits(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_text("1", encoding="utf-8")
    os.link(source / "one", source / "hard-link")
    with pytest.raises(CacheSnapshotError, match="cache_snapshot_hardlink_rejected"):
        CacheSnapshotService().publish(source, tmp_path / "target")

    source2 = tmp_path / "source2"
    source2.mkdir()
    (source2 / "large").write_bytes(b"x" * 11)
    with pytest.raises(CacheSnapshotError, match="cache_snapshot_byte_limit"):
        CacheSnapshotService(max_bytes=10).publish(source2, tmp_path / "target2")


def test_cache_publish_is_atomic_on_validation_failure(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "old").write_text("keep", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "large").write_bytes(b"x" * 11)
    with pytest.raises(CacheSnapshotError):
        CacheSnapshotService(max_bytes=10).publish(source, target)
    assert (target / "old").read_text(encoding="utf-8") == "keep"
