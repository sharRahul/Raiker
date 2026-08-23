"""BUG-233 — an approval that knows when its own promise does not hold.

The notice for a file mutation read *"The previous file contents are
checkpointed first, so it can be rewound."* It was a constant for the whole
file-mutation class, and for a file over `MAX_PRE_IMAGE_BYTES` it was false: the
write happens, the pre-image is recorded `oversize`, and nothing can put it back.
The owner read the promise **before** deciding, and the capture that would have
contradicted it happens after.
"""

from __future__ import annotations

from pathlib import Path

from raiker.checkpoints.capture import MAX_PRE_IMAGE_BYTES
from raiker.cli.commands import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.control.service import RuntimeControlService


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    RuntimeControlService(ws).activate_runtime_mode("local_single_user_runtime", None, "test")
    return ws


def _oversize(dashboard: DashboardService, path: str) -> tuple[str, int] | None:
    return dashboard._oversize_target("write_file", {"path": path})  # noqa: SLF001


def test_a_file_over_the_cap_is_reported_as_unrestorable(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    big = ws / "big.bin"
    big.write_bytes(b"x" * (MAX_PRE_IMAGE_BYTES + 1))

    result = _oversize(DashboardService(ws), "big.bin")

    assert result is not None
    path, size = result
    assert path == "big.bin"
    assert size > MAX_PRE_IMAGE_BYTES


def test_a_file_at_the_cap_still_has_a_pre_image(tmp_path: Path) -> None:
    """The boundary is `>`, matching `CheckpointCaptureService`'s own rule."""
    ws = _workspace(tmp_path)
    (ws / "exact.bin").write_bytes(b"x" * MAX_PRE_IMAGE_BYTES)

    assert _oversize(DashboardService(ws), "exact.bin") is None


def test_a_new_file_is_never_reported_as_unrestorable(tmp_path: Path) -> None:
    """There is nothing to rewind *to*, so the rewind promise is not at stake."""
    ws = _workspace(tmp_path)

    assert _oversize(DashboardService(ws), "does-not-exist-yet.txt") is None


def test_a_path_outside_the_workspace_reports_no_promise(tmp_path: Path) -> None:
    """Containment is the executor's job; this function refuses to guess."""
    ws = _workspace(tmp_path)

    assert _oversize(DashboardService(ws), "../outside.txt") is None


def test_only_the_tools_that_make_the_promise_are_checked(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    dashboard = DashboardService(ws)
    big = ws / "big.bin"
    big.write_bytes(b"x" * (MAX_PRE_IMAGE_BYTES + 1))

    # A commit is git history rather than a checkpointed file, and its notice
    # says so — asking this question of it would be meaningless.
    assert dashboard._oversize_target("git_commit", {"path": "big.bin"}) is None  # noqa: SLF001
    for tool in ("write_file", "edit_file", "apply_patch", "create_document"):
        assert dashboard._oversize_target(tool, {"path": "big.bin"}) is not None  # noqa: SLF001
