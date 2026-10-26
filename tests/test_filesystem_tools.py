from __future__ import annotations

import pytest

from raiker.tools.filesystem import (
    FilesystemSafetyError,
    apply_patch_content,
    glob_paths,
    grep_files,
    list_directory,
    proposed_patch_snapshot,
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


def test_unified_patch_uses_hunk_location_to_resolve_repeated_context(tmp_path) -> None:  # type: ignore[no-untyped-def]
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

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "one\nchanged\nthree\none\ntwo\nthree\n"


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


def test_unified_patch_supports_context_offset_and_empty_insertion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "note.txt"
    target.write_text("preface\none\ntwo\n", encoding="utf-8")
    patch = (
        "--- a/note.txt\n+++ b/note.txt\n"
        "@@ -1,2 +1,2 @@\n one\n-two\n+changed\n"
        "@@ -4,0 +4,1 @@\n+tail\n"
    )

    result = apply_patch_content(tmp_path, "note.txt", patch)

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "preface\none\nchanged\ntail\n"


def test_unified_patch_supports_create_delete_and_no_newline_marker(tmp_path) -> None:  # type: ignore[no-untyped-def]
    create = (
        "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1,1 @@\n+without newline\n"
        "\\ No newline at end of file\n"
    )
    created = apply_patch_content(tmp_path, "new.txt", create)
    assert created["operation"] == "create"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "without newline"

    delete = (
        "--- a/new.txt\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-without newline\n"
        "\\ No newline at end of file\n"
    )
    deleted = apply_patch_content(tmp_path, "new.txt", delete)
    assert deleted["operation"] == "delete"
    assert not (tmp_path / "new.txt").exists()


def test_unified_patch_updates_multiple_files_as_one_change_set(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "one.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two\n", encoding="utf-8")
    patch = (
        "--- a/one.txt\n+++ b/one.txt\n@@ -1 +1 @@\n-one\n+ONE\n"
        "--- a/two.txt\n+++ b/two.txt\n@@ -1 +1 @@\n-two\n+TWO\n"
    )

    result = apply_patch_content(tmp_path, None, patch)

    assert result["status"] == "success"
    assert result["paths"] == ["one.txt", "two.txt"]
    assert (tmp_path / "one.txt").read_text(encoding="utf-8") == "ONE\n"
    assert (tmp_path / "two.txt").read_text(encoding="utf-8") == "TWO\n"


def test_three_file_patch_preview_binds_every_path_and_exact_content(tmp_path) -> None:  # type: ignore[no-untyped-def]
    for name in ("one", "two", "three"):
        (tmp_path / f"{name}.txt").write_text(f"{name}\n", encoding="utf-8")
    patch = "".join(
        f"--- a/{name}.txt\n+++ b/{name}.txt\n@@ -1 +1 @@\n-{name}\n+{name.upper()}\n"
        for name in ("one", "two", "three")
    )

    proposal = proposed_patch_snapshot(tmp_path, None, patch)

    assert proposal["paths"] == ["one.txt", "two.txt", "three.txt"]
    assert [change["before_snapshot"] for change in proposal["changes"]] == [
        "one\n", "two\n", "three\n"
    ]
    assert [change["proposed_text"] for change in proposal["changes"]] == [
        "ONE\n", "TWO\n", "THREE\n"
    ]


def test_unified_patch_rejects_multi_file_change_before_any_write(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "one.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two\n", encoding="utf-8")
    patch = (
        "--- a/one.txt\n+++ b/one.txt\n@@ -1 +1 @@\n-one\n+ONE\n"
        "--- a/two.txt\n+++ b/two.txt\n@@ -1 +1 @@\n-stale\n+TWO\n"
    )

    result = apply_patch_content(tmp_path, None, patch)

    assert result["status"] == "failed"
    assert (tmp_path / "one.txt").read_text(encoding="utf-8") == "one\n"
    assert (tmp_path / "two.txt").read_text(encoding="utf-8") == "two\n"


def test_grep_regex_case_and_context(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TOOL-02 — regex, ignore_case and context lines, each opt-in."""
    (tmp_path / "a.py").write_text("one\ndef Alpha():\n    pass\nfour\n", encoding="utf-8")
    plain = grep_files(tmp_path, "def alpha", ".")
    assert plain["matches"] == []
    folded = grep_files(tmp_path, "def alpha", ".", ignore_case=True)
    assert [m["line"] for m in folded["matches"]] == [2]
    assert "before" not in folded["matches"][0]
    pattern = grep_files(tmp_path, r"^def \w+\(", ".", regex=True, context=1)
    match = pattern["matches"][0]
    assert match["line"] == 2
    assert match["before"] == ["one"]
    assert match["after"] == ["    pass"]
    # A literal search does not interpret regex syntax.
    assert grep_files(tmp_path, r"\w+", ".")["matches"] == []
    # Context is capped.
    wide = grep_files(tmp_path, "pass", ".", context=50)
    assert wide["matches"][0]["before"] == ["one", "def Alpha():"]


def test_grep_refuses_bad_and_catastrophic_patterns(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.txt").write_text("aaaa\n", encoding="utf-8")
    assert grep_files(tmp_path, "(", ".", regex=True)["error"]["type"] == "pattern_invalid"
    assert grep_files(tmp_path, "(a+)+$", ".", regex=True)["error"]["type"] == "pattern_nested_quantifier"
    assert grep_files(tmp_path, "x" * 501, ".", regex=True)["error"]["type"] == "pattern_too_long"
    assert grep_files(tmp_path, "", ".")["error"]["type"] == "query_empty"


def test_edit_replace_all_and_insert_line(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TOOL-02 replace_all and TOOL-99 insert_line, through preview and write."""
    from raiker.tools.filesystem import edit_file_content, edit_options, proposed_edit_snapshot

    target = tmp_path / "a.txt"
    target.write_text("x = 1\ny = x\nz = x\n", encoding="utf-8")
    # Without replace_all, an ambiguous match is still refused.
    assert proposed_edit_snapshot(tmp_path, "a.txt", "x", "w")["error"]["type"] == "old_text_not_unique"
    preview = proposed_edit_snapshot(tmp_path, "a.txt", "x", "w", **edit_options({"replace_all": True}))
    assert preview["proposed_text"] == "w = 1\ny = w\nz = w\n"
    assert target.read_text(encoding="utf-8") == "x = 1\ny = x\nz = x\n"
    assert edit_file_content(tmp_path, "a.txt", "nope", "w", replace_all=True)["error"]["type"] == "old_text_not_found"
    edit_file_content(tmp_path, "a.txt", "", "# header", insert_line=0)
    assert target.read_text(encoding="utf-8").startswith("# header\nx = 1\n")
    edit_file_content(tmp_path, "a.txt", "", "tail", **edit_options({"insert_line": "4"}))
    assert target.read_text(encoding="utf-8").endswith("z = x\ntail\n")
    assert edit_file_content(tmp_path, "a.txt", "", "t", insert_line=99)["error"]["type"] == "insert_line_out_of_range"
    assert edit_file_content(tmp_path, "a.txt", "x", "t", insert_line=1)["error"]["type"] == "insert_line_with_old_text"
    assert edit_options({"insert_line": True}) == {"replace_all": False, "insert_line": None, "cell": None}
    assert edit_options({"replace_all": "yes"})["replace_all"] is False


def test_read_file_line_range(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TOOL-02 — a long file read in parts."""
    from raiker.tools.filesystem import read_file

    (tmp_path / "a.txt").write_text("".join(f"line {n}\n" for n in range(1, 11)), encoding="utf-8")
    whole = read_file(tmp_path, "a.txt")
    assert "line_start" not in whole and whole["truncated"] is False
    part = read_file(tmp_path, "a.txt", offset=3, limit=2)
    assert part["text"] == "line 3\nline 4\n"
    assert (part["line_start"], part["line_end"], part["line_count"]) == (3, 4, 10)
    assert part["truncated"] is True
    tail = read_file(tmp_path, "a.txt", offset=9)
    assert tail["text"] == "line 9\nline 10\n" and tail["truncated"] is False
    assert read_file(tmp_path, "a.txt", offset=50)["error"]["type"] == "offset_out_of_range"
    assert read_file(tmp_path, "a.txt", pages="1")["error"]["type"] == "pages_only_for_pdf"


def test_read_file_pdf_pages(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TOOL-02 — a PDF's pages come back as text, a bounded span per call."""
    from pypdf import PdfWriter

    from raiker.tools.filesystem import read_file

    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    with (tmp_path / "doc.pdf").open("wb") as handle:
        writer.write(handle)
    result = read_file(tmp_path, "doc.pdf", pages="2-3")
    assert result["status"] == "success"
    assert result["pages"] == "2-3" and result["page_count"] == 3
    assert "--- Page 2 ---" in result["text"] and "--- Page 1 ---" not in result["text"]
    assert read_file(tmp_path, "doc.pdf")["pages"] == "1-3"
    assert read_file(tmp_path, "doc.pdf", pages="5")["error"]["type"] == "pages_out_of_range"
    assert read_file(tmp_path, "doc.pdf", pages="1-30")["error"]["type"] == "pages_too_many"
    assert read_file(tmp_path, "doc.pdf", pages="x")["error"]["type"] == "pages_invalid"
    import raiker.tools.filesystem as filesystem

    original = filesystem.MAX_READ_PDF_BYTES
    filesystem.MAX_READ_PDF_BYTES = 10
    try:
        assert read_file(tmp_path, "doc.pdf")["error"]["type"] == "pdf_too_large"
    finally:
        filesystem.MAX_READ_PDF_BYTES = original


def test_notebook_read_as_cells_and_edited_by_cell(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json as _json

    from raiker.tools.filesystem import edit_file_content, proposed_edit_snapshot, read_file

    notebook = {
        "cells": [
            {"cell_type": "markdown", "id": "intro", "metadata": {}, "source": ["# Title\n"]},
            {"cell_type": "code", "id": "calc", "metadata": {}, "execution_count": 1,
             "outputs": [{"output_type": "stream", "text": ["2\n"]}], "source": ["x = 1\n", "print(x + 1)"]},
        ],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
    }
    path = tmp_path / "a.ipynb"
    path.write_text(_json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    shown = read_file(tmp_path, "a.ipynb")
    assert shown["notebook"] is True
    assert "[cell 1 · code · id calc]\nx = 1\nprint(x + 1)\n(outputs: 1 — stream)" in shown["text"]
    preview = proposed_edit_snapshot(tmp_path, "a.ipynb", "x = 1", "x = 2", cell="calc")
    assert preview["status"] == "proposal"
    assert edit_file_content(tmp_path, "a.ipynb", "x = 1", "x = 2", cell="1")["status"] == "success"
    edited = _json.loads(path.read_text(encoding="utf-8"))
    assert edited["cells"][1]["source"] == ["x = 2\n", "print(x + 1)"]
    assert edited["cells"][1]["outputs"] == notebook["cells"][1]["outputs"]
    # Only the cell changed: the rest of the file is byte for byte what it was.
    assert path.read_text(encoding="utf-8") == (_json.dumps(edited, indent=1) + "\n")
    assert edit_file_content(tmp_path, "a.ipynb", "", "y = 0", cell="calc", insert_line=0)["status"] == "success"
    assert _json.loads(path.read_text())["cells"][1]["source"][0] == "y = 0\n"
    assert edit_file_content(tmp_path, "a.ipynb", "x", "z", cell="9")["error"]["type"] == "cell_not_found"
    assert edit_file_content(tmp_path, "a.ipynb", "x", "z", cell="calc")["error"]["type"] == "old_text_ambiguous"
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    assert edit_file_content(tmp_path, "b.py", "x", "z", cell="0")["error"]["type"] == "cell_needs_a_notebook"
