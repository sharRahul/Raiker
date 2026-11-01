from __future__ import annotations

import os
import subprocess
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pytest

from raiker.execution.commands import credential_overlay
from raiker.execution.commands.credential_overlay import CredentialOverlay, manifest


def test_overlay_refuses_staging_inside_the_original_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "original.txt").write_text("owner data", encoding="utf-8")
    overlay = CredentialOverlay(workspace, workspace / "staging")
    with pytest.raises(ValueError, match="credential_overlay_overlapping_roots"):
        overlay.create()
    assert not (workspace / "staging").exists()
    assert (workspace / "original.txt").read_text(encoding="utf-8") == "owner data"


def test_overlay_excludes_protected_directory_names_case_insensitively(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    (workspace / ".RaIkEr").mkdir(parents=True)
    (workspace / ".RaIkEr" / "secret").write_text("private", encoding="utf-8")
    (workspace / "app.py").write_text("safe", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    overlay.create()
    assert (overlay.workspace / "app.py").is_file()
    assert not (overlay.workspace / ".RaIkEr").exists()


def test_overlay_rejects_a_hard_link_without_relying_on_symlink_privileges(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    target = workspace / "target"
    target.write_text("owner data", encoding="utf-8")
    os.link(target, workspace / "hardlink")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging").create()


def test_overlay_refuses_a_file_replaced_between_inspection_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    source = workspace / "file"
    source.write_text("original", encoding="utf-8")
    replacement = tmp_path / "replacement"
    replacement.write_text("new content", encoding="utf-8")
    original = credential_overlay._no_follow_opener

    def replace_then_open(path: str, flags: int) -> int:
        os.replace(replacement, source)
        return original(path, flags)

    monkeypatch.setattr(credential_overlay, "_no_follow_opener", replace_then_open)
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging").create()
    assert not (tmp_path / "staging").exists()


def test_overlay_refuses_a_source_modified_during_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    source = workspace / "file"
    source.write_bytes(b"original")
    copy = credential_overlay._copy_bounded

    def modify_after_copy(reader: BinaryIO, writer: BinaryIO, size: int) -> None:
        copy(reader, writer, size)
        source.write_bytes(b"owner modified this file")

    monkeypatch.setattr(credential_overlay, "_copy_bounded", modify_after_copy)
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging").create()
    assert source.read_bytes() == b"owner modified this file"
    assert not (tmp_path / "staging").exists()


def test_overlay_refuses_same_size_change_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    source = workspace / "file"
    source.write_bytes(b"original")
    opener = credential_overlay._no_follow_opener

    def modify_then_open(path: str, flags: int) -> int:
        old = source.stat().st_mtime_ns
        source.write_bytes(b"modified")
        os.utime(source, ns=(old + 2_000_000_000, old + 2_000_000_000))
        return opener(path, flags)

    monkeypatch.setattr(credential_overlay, "_no_follow_opener", modify_then_open)
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        CredentialOverlay(workspace, tmp_path / "staging").create()
    assert source.read_bytes() == b"modified"
    assert not (tmp_path / "staging").exists()


def test_overlay_refuses_large_source_before_completing_a_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "data").write_bytes(b"123456")
    monkeypatch.setattr(credential_overlay, "_MAX_SNAPSHOT_BYTES", 5)
    with pytest.raises(ValueError, match="credential_overlay_size_limit_exceeded"):
        CredentialOverlay(workspace, tmp_path / "staging").create()
    assert (workspace / "data").read_bytes() == b"123456"
    assert not (tmp_path / "staging").exists()


def test_overlay_refuses_too_many_source_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "one").write_bytes(b"1")
    (workspace / "two").write_bytes(b"2")
    monkeypatch.setattr(credential_overlay, "_MAX_SNAPSHOT_ENTRIES", 1)
    with pytest.raises(ValueError, match="credential_overlay_entry_limit_exceeded"):
        CredentialOverlay(workspace, tmp_path / "staging").create()
    assert not (tmp_path / "staging").exists()


@pytest.mark.parametrize("content, expected_size", [(b"abc", 2), (b"a", 2)])
def test_bounded_copy_refuses_growing_or_truncated_input(content: bytes, expected_size: int) -> None:
    output = BytesIO()
    with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
        credential_overlay._copy_bounded(BytesIO(content), output, expected_size)
    assert len(output.getvalue()) <= expected_size


@pytest.mark.skipif(os.name != "nt", reason="Windows junction enforcement test")
def test_overlay_refuses_a_windows_junction(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private").write_text("owner data", encoding="utf-8")
    junction = workspace / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        with pytest.raises(ValueError, match="credential_overlay_unsafe_source"):
            CredentialOverlay(workspace, tmp_path / "staging").create()
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction enforcement test")
def test_overlay_delta_does_not_traverse_a_windows_junction(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private").write_text("owner data", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    junction = overlay.workspace / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        delta = overlay.delta(baseline)
        assert not delta.mergeable
        assert "junction" in delta.unsafe
        assert "junction/private" not in delta.created
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction enforcement test")
def test_overlay_delta_refuses_a_replaced_workspace_root_junction(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private").write_text("owner data", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    overlay.workspace.rename(overlay.staging_root / "old-workspace")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(overlay.workspace), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        with pytest.raises(ValueError, match="credential_overlay_unsafe_root"):
            overlay.delta(baseline)
        assert (outside / "private").read_text(encoding="utf-8") == "owner data"
    finally:
        overlay.workspace.rmdir()


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


def test_overlay_delta_refuses_a_modified_baseline_manifest(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "file").write_bytes(b"original")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    baseline.entries.clear()
    with pytest.raises(ValueError, match="credential_overlay_invalid_baseline"):
        overlay.delta(baseline)


def test_promotion_preflight_detects_owner_edits_but_allows_unrelated_edits(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "shared").write_text("before", encoding="utf-8")
    (workspace / "other").write_text("before", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "shared").write_text("agent", encoding="utf-8")
    (workspace / "other").write_text("owner", encoding="utf-8")
    assert overlay.promotion_conflicts(baseline) == ()
    (workspace / "shared").write_text("owner edit", encoding="utf-8")
    assert overlay.promotion_conflicts(baseline) == ("shared",)
    assert (workspace / "shared").read_text(encoding="utf-8") == "owner edit"


def test_promotion_preflight_detects_new_owner_file_in_a_deleted_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    (workspace / "dir").mkdir(parents=True)
    (workspace / "dir" / "old").write_bytes(b"before")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "dir" / "old").unlink()
    (overlay.workspace / "dir").rmdir()
    (workspace / "dir" / "new").write_bytes(b"owner data")
    assert "dir" in overlay.promotion_conflicts(baseline)
    assert (workspace / "dir" / "new").read_bytes() == b"owner data"


def test_promotion_preflight_detects_case_collisions(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "Readme").write_bytes(b"agent")
    (workspace / "README").write_bytes(b"owner")
    assert overlay.promotion_conflicts(baseline) == ("Readme",)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission preservation")
def test_promotion_preflight_preserves_private_file_and_directory_modes(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    (workspace / "private").mkdir(parents=True)
    (workspace / "private" / "file").write_bytes(b"original")
    (workspace / "private").chmod(0o700)
    (workspace / "private" / "file").chmod(0o600)
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "private" / "file").write_bytes(b"agent")
    assert overlay.promotion_conflicts(baseline) == ()
    assert (overlay.workspace / "private").stat().st_mode & 0o777 == 0o700
    assert (overlay.workspace / "private" / "file").stat().st_mode & 0o777 == 0o600


def test_promotion_preflight_never_reads_internal_directories(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    (workspace / ".git").mkdir(parents=True)
    (workspace / ".raiker").mkdir()
    (workspace / "file").write_bytes(b"before")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "file").write_bytes(b"agent")
    (workspace / ".git" / "ignored").write_bytes(b"secret")
    (workspace / ".raiker" / "ignored").write_bytes(b"secret")
    os.link(workspace / ".git" / "ignored", workspace / ".git" / "hardlink")
    os.link(workspace / ".raiker" / "ignored", workspace / ".raiker" / "hardlink")
    assert overlay.promotion_conflicts(baseline) == ()


def test_promotion_preflight_refuses_unsafe_original_and_delta(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    (workspace / "file").write_bytes(b"owner")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / "file").write_bytes(b"agent")
    os.link(workspace / "file", workspace / "owner-hardlink")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_original"):
        overlay.promotion_conflicts(baseline)
    (workspace / "owner-hardlink").unlink()
    os.link(overlay.workspace / "file", overlay.workspace / "agent-hardlink")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_delta"):
        overlay.promotion_conflicts(baseline)


def test_artifact_manifest_refuses_too_many_entries_without_truncating(tmp_path: Path) -> None:
    (tmp_path / "one").write_bytes(b"1")
    (tmp_path / "two").write_bytes(b"2")
    with pytest.raises(ValueError, match="credential_overlay_entry_limit_exceeded"):
        manifest(tmp_path, max_entries=1)
    assert len(manifest(tmp_path, max_entries=2).entries) == 2


def test_artifact_manifest_refuses_an_oversized_snapshot(tmp_path: Path) -> None:
    (tmp_path / "one").write_bytes(b"123")
    (tmp_path / "two").write_bytes(b"456")
    with pytest.raises(ValueError, match="credential_overlay_size_limit_exceeded"):
        manifest(tmp_path, max_bytes=5)
    assert len(manifest(tmp_path, max_bytes=6).entries) == 2


@pytest.mark.parametrize("protected", [".RaIkEr", ".GiT"])
def test_overlay_delta_rejects_case_variants_of_protected_paths(
    tmp_path: Path, protected: str
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    (overlay.workspace / protected).mkdir()
    (overlay.workspace / protected / "data").write_text("untrusted", encoding="utf-8")
    delta = overlay.delta(baseline)
    assert not delta.mergeable
    assert protected in delta.unsafe
    assert f"{protected}/data" in delta.unsafe


def test_overlay_delta_marks_a_replaced_output_file_unsafe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    output = overlay.workspace / "output"
    output.write_text("first", encoding="utf-8")
    replacement = tmp_path / "replacement"
    replacement.write_text("different", encoding="utf-8")
    original = credential_overlay._no_follow_opener

    def replace_then_open(path: str, flags: int) -> int:
        os.replace(replacement, output)
        return original(path, flags)

    monkeypatch.setattr(credential_overlay, "_no_follow_opener", replace_then_open)
    delta = overlay.delta(baseline)
    assert not delta.mergeable
    assert "output" in delta.unsafe


def test_overlay_delta_rejects_same_size_change_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    output = overlay.workspace / "output"
    output.write_bytes(b"original")
    opener = credential_overlay._no_follow_opener

    def modify_then_open(path: str, flags: int) -> int:
        old = output.stat().st_mtime_ns
        output.write_bytes(b"modified")
        os.utime(output, ns=(old + 2_000_000_000, old + 2_000_000_000))
        return opener(path, flags)

    monkeypatch.setattr(credential_overlay, "_no_follow_opener", modify_then_open)
    delta = overlay.delta(baseline)
    assert not delta.mergeable
    assert "output" in delta.unsafe


def test_overlay_delta_marks_a_file_linked_during_hashing_unsafe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    baseline = overlay.create()
    output = overlay.workspace / "output"
    output.write_bytes(b"generated")
    hash_factory = credential_overlay.hashlib.sha256
    linked = False

    class LinkOnUpdate:
        def __init__(self) -> None:
            self.inner = hash_factory()

        def update(self, content: bytes) -> None:
            nonlocal linked
            if not linked:
                os.link(output, tmp_path / "new-hardlink")
                linked = True
            self.inner.update(content)

        def hexdigest(self) -> str:
            return self.inner.hexdigest()

    def hash_with_link(content: bytes = b"") -> object:
        if content:
            return hash_factory(content)
        return LinkOnUpdate()

    monkeypatch.setattr(credential_overlay.hashlib, "sha256", hash_with_link)
    delta = overlay.delta(baseline)
    assert not delta.mergeable
    assert "output" in delta.unsafe


def test_overlay_discard_removes_read_only_git_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    (workspace / ".git").mkdir(parents=True)
    (workspace / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    overlay = CredentialOverlay(workspace, tmp_path / "staging")
    overlay.create()

    overlay.discard()

    assert not overlay.staging_root.exists()


def test_discard_cannot_remove_an_unowned_staging_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "owner-data").write_text("keep", encoding="utf-8")
    overlay = CredentialOverlay(workspace, staging)
    with pytest.raises(ValueError, match="credential_overlay_not_owned"):
        overlay.discard()
    assert (staging / "owner-data").read_text(encoding="utf-8") == "keep"


def test_discard_refuses_a_replaced_staging_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "source"
    workspace.mkdir()
    staging = tmp_path / "staging"
    overlay = CredentialOverlay(workspace, staging)
    overlay.create()
    staging.rename(tmp_path / "original-staging")
    staging.mkdir()
    (staging / "owner-data").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="credential_overlay_not_owned"):
        overlay.discard()
    assert (staging / "owner-data").read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction enforcement test")
def test_cleanup_retry_refuses_a_junction_to_owner_data(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
        check=True,
        capture_output=True,
        text=True,
    )
    called = False

    def remove(_path: str) -> None:
        nonlocal called
        called = True

    try:
        error = PermissionError("test")
        with pytest.raises(ValueError, match="credential_overlay_unsafe_cleanup"):
            credential_overlay._make_writable_and_retry(
                root, remove, str(link), (PermissionError, error, None)
            )
        assert not called
        assert outside.is_dir()
    finally:
        link.rmdir()


def test_cleanup_retry_never_chmods_the_parent_of_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    changed: list[Path] = []
    monkeypatch.setattr(Path, "chmod", lambda path, _mode: changed.append(path))
    error = PermissionError("test")
    credential_overlay._make_writable_and_retry(
        root, lambda _path: None, str(root), (PermissionError, error, None)
    )
    assert changed == [root]


def test_cleanup_retry_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    outside = tmp_path / "owner-file"
    outside.write_bytes(b"owner")
    error = PermissionError("test")
    with pytest.raises(ValueError, match="credential_overlay_unsafe_cleanup"):
        credential_overlay._make_writable_and_retry(
            root, lambda _path: None, str(root / ".." / "owner-file"),
            (PermissionError, error, None),
        )
    assert outside.read_bytes() == b"owner"


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
