from __future__ import annotations

import pytest

from raiker.tools.filesystem import (
    FilesystemSafetyError,
    apply_patch_content,
    glob_paths,
    grep_files,
    list_directory,
    proposed_write_snapshot,
    read_file,
    replace_text_content,
    write_file_content,
)


def test_read_file_success_missing_binary_and_denial(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"a\x00b")
    assert read_file(tmp_path, "a.txt")["text"] == "hello"
    assert read_file(tmp_path, "missing.txt")["error"]["type"] == "not_found"
    assert read_file(tmp_path, "bin.dat")["error"]["type"] == "binary_file"
    with pytest.raises(FilesystemSafetyError):
        read_file(tmp_path, "../outside.txt")


def test_list_directory_sorted_and_denial(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a").mkdir()
    assert list_directory(tmp_path, ".")["entries"] == ["a/", "b.txt"]
    with pytest.raises(FilesystemSafetyError):
        list_directory(tmp_path, "../")


def test_glob_and_grep_bounded(tmp_path) -> None:  # type: ignore[no-untyped-def]
    for index in range(5):
        (tmp_path / f"f{index}.txt").write_text(f"needle {index}\n", encoding="utf-8")
    assert glob_paths(tmp_path, "*.txt", max_results=2)["truncated"] is True
    result = grep_files(tmp_path, "needle", ".", max_results=3)
    assert len(result["matches"]) == 3
    assert result["truncated"] is True


def test_writes_are_refused_inside_the_governance_directories(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """BUG-06 — workspace confinement is not enough once a write really runs.

    `.raiker/` holds the encrypted store, the audit log, the vault key and the
    hook definitions (which run commands); `.git/` holds hooks that run on the
    next commit. Both sit *inside* the workspace, so `resolve_workspace_path`
    would happily hand them over. Reads stay unaffected.
    """
    for protected in (".raiker/hooks.json", ".git/hooks/pre-commit", ".raiker"):
        with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
            write_file_content(tmp_path, protected, "owned")
        with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
            apply_patch_content(tmp_path, protected, "owned")
        # Refused at proposal time too, so no un-executable approval is parked.
        with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
            proposed_write_snapshot(tmp_path, protected, "owned")
        assert not (tmp_path / protected).is_file()

    # A merely similar name is not protected — the guard matches path segments.
    assert write_file_content(tmp_path, ".raikerish/notes.md", "ok")["status"] == "success"
    assert write_file_content(tmp_path, "docs/.raiker.md", "ok")["status"] == "success"


def test_reading_the_governance_directory_is_still_allowed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".raiker").mkdir()
    (tmp_path / ".raiker" / "notes.txt").write_text("readable", encoding="utf-8")
    assert read_file(tmp_path, ".raiker/notes.txt")["text"] == "readable"


def test_exact_edit_replaces_one_unique_match(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("before\nneedle\nafter\n", encoding="utf-8")

    result = replace_text_content(tmp_path, "note.txt", "needle\n", "changed\n")

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "before\nchanged\nafter\n"


def test_exact_edit_refuses_zero_or_multiple_matches_without_mutating(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("repeat\nrepeat\n", encoding="utf-8")

    missing = replace_text_content(tmp_path, "note.txt", "missing", "x")
    ambiguous = replace_text_content(tmp_path, "note.txt", "repeat", "x")

    assert missing["error"]["type"] == "old_text_not_found"
    assert ambiguous["error"]["type"] == "old_text_not_unique"
    assert target.read_text(encoding="utf-8") == "repeat\nrepeat\n"


def test_unified_patch_applies_a_unique_context_anchored_hunk(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("heading\none\ntwo\nthree\n", encoding="utf-8")
    patch = (
        "--- a/note.txt\n"
        "+++ b/note.txt\n"
        "@@ -2,3 +2,3 @@\n"
        " one\n"
        "-two\n"
        "+changed\n"
        " three\n"
    )

    result = apply_patch_content(tmp_path, "note.txt", patch)

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "heading\none\nchanged\nthree\n"


def test_unified_patch_rejects_unmatched_or_ambiguous_context_without_writing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("one\ntwo\nthree\none\ntwo\nthree\n", encoding="utf-8")
    patch = (
        "--- a/note.txt\n"
        "+++ b/note.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " one\n"
        "-two\n"
        "+changed\n"
        " three\n"
    )

    result = apply_patch_content(tmp_path, "note.txt", patch)

    assert result["error"]["type"] == "hunk_context_not_unique"
    assert result["rejected_hunks"] == [1]
    assert target.read_text(encoding="utf-8") == "one\ntwo\nthree\none\ntwo\nthree\n"


def test_unified_patch_rejects_a_later_hunk_without_partially_writing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    patch = (
        "--- a/note.txt\n"
        "+++ b/note.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " one\n"
        "-two\n"
        "+changed\n"
        "@@ -3,2 +3,2 @@\n"
        " three\n"
        "-absent\n"
        "+also-changed\n"
    )

    result = apply_patch_content(tmp_path, "note.txt", patch)

    assert result["error"]["type"] == "hunk_context_mismatch"
    assert result["rejected_hunks"] == [2]
    assert target.read_text(encoding="utf-8") == "one\ntwo\nthree\nfour\n"
