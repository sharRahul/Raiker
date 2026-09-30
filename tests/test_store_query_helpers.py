"""OPT-06 stage B — one statement, one transaction, written once."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from raiker.storage.sqlite import SQLiteStore

STORES = Path(__file__).resolve().parents[1] / "raiker" / "storage" / "stores"


def test_rows_row_and_execute_run_in_their_own_committed_transaction(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store._execute("CREATE TABLE IF NOT EXISTS helper_probe (k TEXT PRIMARY KEY, v INTEGER)")  # noqa: SLF001
    assert store._execute("INSERT INTO helper_probe VALUES (?, ?)", ("a", 1)) == 1  # noqa: SLF001
    assert store._execute("UPDATE helper_probe SET v = 2 WHERE k = ?", ("missing",)) == 0  # noqa: SLF001

    row = store._row("SELECT v FROM helper_probe WHERE k = ?", ("a",))  # noqa: SLF001
    assert row is not None and row["v"] == 1
    assert store._row("SELECT v FROM helper_probe WHERE k = ?", ("b",)) is None  # noqa: SLF001
    assert [r["k"] for r in store._rows("SELECT k FROM helper_probe")] == ["a"]  # noqa: SLF001

    # A failing statement rolls back and raises; nothing half-written survives.
    with pytest.raises(Exception, match="UNIQUE"):
        store._execute("INSERT INTO helper_probe VALUES (?, ?)", ("a", 3))  # noqa: SLF001
    assert store._row("SELECT v FROM helper_probe WHERE k = 'a'")["v"] == 1  # type: ignore[index]  # noqa: SLF001


def _single_execute_blocks(path: Path) -> list[int]:
    """`with self.connect() as connection:` around one bare `execute` statement."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.With) or len(node.items) != 1 or len(node.body) != 1:
            continue
        context = ast.unparse(node.items[0].context_expr)
        if context != "self.connect()":
            continue
        # A loop, a `try` or a nested block is a transaction with a shape of its
        # own; only a plain statement around one `execute` is the helper's job.
        if not isinstance(node.body[0], (ast.Assign, ast.Return, ast.Expr)):
            continue
        statement = ast.unparse(node.body[0])
        if statement.count("connection.") == 1 and "connection.execute(" in statement:
            found.append(node.lineno)
    return found


def test_no_store_hand_writes_a_single_statement_transaction() -> None:
    offenders = {
        path.name: lines
        for path in STORES.glob("*.py")
        if path.name != "migration_runner.py" and (lines := _single_execute_blocks(path))
    }
    assert not offenders, f"use self._rows / self._row / self._execute: {offenders}"
