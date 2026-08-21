from __future__ import annotations

import os
from pathlib import Path

import pytest

from raiker.execution.commands.credential_overlay import CredentialOverlay


def test_overlay_excludes_runtime_state_and_uses_a_separate_read_only_git_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "source"
    (workspace / ".git").mkdir(parents=True)
    (workspace / ".raiker").mkdir()
    (workspace / "src").mkdir()
    (workspace / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (workspace / ".raiker" / "vault.key").write_text("never copy", encoding="utf-8")
    (workspace / "src" / "main.py").write_text("print('ok')", encoding="utf-8")

    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()

    assert (overlay.workspace / "src" / "main.py").is_file()
    assert not (overlay.workspace / ".git").exists()
    assert not (overlay.workspace / ".raiker").exists()
    assert (overlay.git_snapshot / "HEAD").is_file()
    assert baseline.digest


def test_overlay_delta_names_creates_changes_and_deletes_without_content(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "change.txt").write_text("before", encoding="utf-8")
    (workspace / "delete.txt").write_text("delete", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()

    (overlay.workspace / "change.txt").write_text("after", encoding="utf-8")
    (overlay.workspace / "delete.txt").unlink()
    (overlay.workspace / "create.txt").write_text("created", encoding="utf-8")
    delta = overlay.delta(baseline)

    assert delta.created == ("create.txt",)
    assert delta.changed == ("change.txt",)
    assert delta.deleted == ("delete.txt",)
    assert delta.mergeable is True
    assert "before" not in repr(delta) and "after" not in repr(delta)


def test_overlay_rejects_symlink_and_hardlink_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("safe", encoding="utf-8")
    try:
        (workspace / "link.txt").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging-link").create()

    (workspace / "link.txt").unlink()
    try:
        os.link(target, workspace / "hard.txt")
    except OSError:
        pytest.skip("hardlink creation unavailable")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging-hard").create()
