"""Wave 0 — the LOC baseline is taken the same way every time.

The optimisation review's rules only mean something if a line moved between
two handwritten files scores nothing, a test is not product, and comments are
counted apart. These pin the classification the CI artifact is built from.
"""

from __future__ import annotations

from scripts.measure_loc import (
    c_like_comment_lines,
    classify,
    measure,
    python_comment_lines,
    summarise,
)


def test_paths_land_in_the_bucket_the_review_needs() -> None:
    assert classify("raiker/storage/sqlite.py") == "production"
    assert classify("web/src/lib/api.ts") == "production"
    assert classify("tests/test_storage_sqlite.py") == "test"
    assert classify("web/src/lib/format.test.ts") == "test"
    assert classify("web/e2e/workbench-live.spec.ts") == "test"
    assert classify(".github/workflows/ci.yml") == "workflow"
    # Documentation is not source, however many lines it has.
    assert classify("docs/plans/FIXED_ITEMS.md") is None


def test_python_comments_and_docstrings_are_counted_apart_from_code() -> None:
    source = '"""Module doc."""\n\n# why\nvalue = 1  # trailing\n\ndef f() -> None:\n    """Doc."""\n    return None\n'
    assert python_comment_lines(source) == {1, 3, 7}


def test_block_and_line_comments_in_typescript() -> None:
    source = "/**\n * doc\n */\nconst a = 1;\n// note\nconst b = 2;\n"
    assert c_like_comment_lines(source) == {1, 2, 3, 5}


def test_the_report_measures_this_repository() -> None:
    summary = summarise(measure())
    totals = summary["totals"]
    assert isinstance(totals, dict)
    assert totals["production"]["code"] > 0
    assert totals["test"]["code"] > 0
    assert summary["schema"] == "raiker-loc/1"
