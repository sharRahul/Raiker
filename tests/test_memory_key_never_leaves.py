"""MEM-KEY-05 — the workspace key is never stored where memory goes.

The key derives the SQLCipher database key. It must never appear in the memory
database, an export, a log line, a backup or an adapter payload — the runbook in
``docs/guide/memory.md`` promises exactly that.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.auth.app_key import app_key_path
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.adapter import MemoryAdapterPolicy, prepare_adapter_payload
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("bootstrap", "Bootstrap", workspace_root=ws)
    return ws


def _key_forms(workspace: Path) -> list[bytes]:
    raw = app_key_path(workspace).read_bytes().strip()
    derived = hashlib.sha256(raw).hexdigest().encode()
    return [raw, derived]


def test_the_key_appears_in_no_database_export_log_or_adapter_payload(
    workspace: Path, seed_account: Any, caplog: pytest.LogCaptureFixture
) -> None:
    owner, token = seed_account(workspace, "owner")
    store = SQLiteStore(workspace)
    caplog.set_level(logging.DEBUG)
    entry = write_memory(
        "Public docs live at the team wiki.",
        workspace_root=workspace,
        scope="user",
        store=store,
        governance=MemoryGovernance(
            "evt_k", "sess_k", None, "human_correction", 1.0, 1.0, "until_forget", "approved", "owner"
        ),
        owner_principal_id=owner,
    )
    client = TestClient(create_app(workspace))
    exported = client.get("/api/memory/export", headers={"Authorization": f"Bearer {token}"})
    assert exported.status_code == 200, exported.text
    payload = prepare_adapter_payload(
        store.list_approved_memory(owner_principal_id=owner),
        owner_principal_id=owner,
        policy=MemoryAdapterPolicy(
            adapter_id="fake", pinned_version="1", enabled=True,
            allowed_scopes=frozenset({"user"}),
        ),
    )
    assert [item.memory_id for item in payload.items] == [entry.memory_id]

    database = (workspace / ".raiker" / "raiker.db").read_bytes()
    assert not database.startswith(b"SQLite format 3")
    for form in _key_forms(workspace):
        assert form not in database
        assert form.decode() not in exported.text
        assert form.decode() not in caplog.text
        assert all(form.decode() not in value for item in payload.items for value in item.wire().values())
