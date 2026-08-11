"""Matching that survives whitespace, without loosening what "one match" means.

The README's known limit said Build patching is "strict about matching": an
exact edit needed exactly one `old_text` match and every hunk had to match its
context exactly. The strictness that mattered was *uniqueness*; the strictness
that only cost work was *whitespace*, because a model that re-indents a quoted
line has still named the right code.
"""
from __future__ import annotations

from pathlib import Path

from raiker.tools.filesystem import proposed_edit_snapshot, proposed_patch_snapshot


def test_an_exact_match_is_unchanged(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("alpha\nbeta\n")
    result = proposed_edit_snapshot(tmp_path, "a.py", "beta", "gamma")
    assert result["proposed_text"] == "alpha\ngamma\n"


def test_a_tab_indented_line_matches_a_space_indented_quote(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f():\n\treturn 1\n")
    result = proposed_edit_snapshot(tmp_path, "a.py", "    return 1", "    return 2")
    assert result["proposed_text"] == "def f():\n    return 2\n"


def test_trailing_whitespace_in_the_quote_does_not_block_the_edit(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("value = 1\n")
    result = proposed_edit_snapshot(tmp_path, "a.py", "value = 1   ", "value = 2")
    assert result["proposed_text"] == "value = 2\n"


def test_a_multi_line_quote_tolerates_re_indentation(tmp_path: Path) -> None:
    """And the file keeps its own indentation — the quote does not de-indent it."""
    (tmp_path / "a.py").write_text("class C:\n    def f(self):\n        return 1\n")
    result = proposed_edit_snapshot(
        tmp_path, "a.py", "def f(self):\n    return 1", "def f(self):\n    return 2"
    )
    assert result["proposed_text"] == "class C:\n    def f(self):\n        return 2\n"


def test_interior_spacing_is_still_a_mismatch(tmp_path: Path) -> None:
    """`a + b` and `a+b` are different text — tolerance is whitespace at the edges."""
    (tmp_path / "a.py").write_text("x = a + b\n")
    result = proposed_edit_snapshot(tmp_path, "a.py", "x = a+b", "x = c")
    assert result["error"]["type"] == "old_text_not_found"


def test_a_relaxed_match_that_hits_twice_is_still_refused(tmp_path: Path) -> None:
    """The strictness that mattered. Tolerance must never make an edit land twice."""
    (tmp_path / "a.py").write_text("  pass  \n\n  pass\n")
    result = proposed_edit_snapshot(tmp_path, "a.py", "pass", "return")
    assert result["error"]["type"] == "old_text_not_unique"


def test_an_exact_duplicate_is_still_refused(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("pass\npass\n")
    assert proposed_edit_snapshot(tmp_path, "a.py", "pass", "x")["error"]["type"] == (
        "old_text_not_unique"
    )


def test_text_that_is_genuinely_absent_still_fails(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("alpha\n")
    assert proposed_edit_snapshot(tmp_path, "a.py", "omega", "x")["error"]["type"] == (
        "old_text_not_found"
    )


def test_a_patch_hunk_tolerates_the_same_whitespace_drift(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f():\n\treturn 1\n\nprint(f())\n")
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    result = proposed_patch_snapshot(tmp_path, "a.py", patch)
    assert result["proposed_text"] == "def f():\n    return 2\n\nprint(f())\n"


def test_a_patch_hunk_that_matches_nothing_still_fails(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("alpha\n")
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,1 @@\n-omega\n+beta\n"
    assert proposed_patch_snapshot(tmp_path, "a.py", patch)["error"]["type"] == (
        "hunk_context_mismatch"
    )


def test_an_exactly_matching_patch_is_unaffected_by_the_relaxed_pass(tmp_path: Path) -> None:
    """The relaxed pass runs only when the exact one found nothing."""
    (tmp_path / "a.py").write_text("alpha\nbeta\n")
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n alpha\n-beta\n+gamma\n"
    assert proposed_patch_snapshot(tmp_path, "a.py", patch)["proposed_text"] == "alpha\ngamma\n"
