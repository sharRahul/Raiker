from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import raiker.storage.sqlite as sqlite_module
from raiker.storage.sqlite import SQLiteStore, invalidate_workspace_connections


def test_worker_reuses_one_keyed_connection_for_a_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalidate_workspace_connections(tmp_path)
    real_connect = sqlite_module.sqlite3.connect
    opened = 0

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting_connect)

    first = SQLiteStore(tmp_path)
    second = SQLiteStore(tmp_path)
    assert first.table_names()
    assert second.table_names()

    assert opened == 1


def test_workspace_invalidation_closes_and_rekeys_on_next_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalidate_workspace_connections(tmp_path)
    real_connect = sqlite_module.sqlite3.connect
    opened = 0

    def counting_connect(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting_connect)
    store = SQLiteStore(tmp_path)
    assert store.table_names()
    assert opened == 1

    invalidate_workspace_connections(tmp_path)
    assert store.table_names()
    assert opened == 2
