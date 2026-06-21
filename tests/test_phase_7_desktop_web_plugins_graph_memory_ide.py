from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    GraphIndexRecord,
    PluginExecutionRecord,
    SemanticMemoryWriteRecord,
)
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


# ── RAIKER-7401: Plugin Runtime Execution ──


def test_plugin_execution_record_crud(store: SQLiteStore) -> None:
    r = PluginExecutionRecord(
        execution_id=new_id("plgex_"),
        plugin_id="com.example.safe",
        version="1.0.0",
        trust_level="local_dev",
        permissions_json='["tool:read_file"]',
        entrypoint="commands/run.sh",
        status="planned",
        started_at=None,
        completed_at=None,
        created_by="admin",
    )
    store.insert_plugin_execution_record(r)
    records = store.list_plugin_execution_records()
    assert len(records) == 1
    assert records[0]["plugin_id"] == "com.example.safe"


def test_plugin_execution_denied_by_default(store: SQLiteStore) -> None:
    r = PluginExecutionRecord(
        execution_id=new_id("plgex_"),
        plugin_id="com.example.untrusted",
        version="1",
        trust_level="untrusted",
        permissions_json='["tool:shell"]',
        entrypoint="evil.sh",
        status="denied",
        started_at=None,
        completed_at=None,
        created_by="admin",
    )
    store.insert_plugin_execution_record(r)
    records = store.list_plugin_execution_records()
    assert records[0]["status"] == "denied"


# ── RAIKER-7501: Graph/Codemap Runtime Indexing ──


def test_graph_index_record_crud(store: SQLiteStore, workspace: Path) -> None:
    r = GraphIndexRecord(
        index_id=new_id("gix_"),
        workspace_root=str(workspace),
        status="requested",
        nodes_count=0,
        edges_count=0,
        started_at=None,
        completed_at=None,
        created_by="admin",
    )
    store.insert_graph_index_record(r)
    records = store.list_graph_index_records()
    assert len(records) == 1
    assert records[0]["status"] == "requested"


def test_graph_index_persists(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_graph_index_record(GraphIndexRecord(new_id("gix_"), str(workspace), "completed", 15, 42, utc_now(), utc_now(), "admin"))
    store2 = SQLiteStore(workspace)
    assert len(store2.list_graph_index_records()) == 1


# ── RAIKER-7601: Semantic/Vector Memory Writes ──


def test_semantic_memory_write_crud(store: SQLiteStore) -> None:
    now = utc_now()
    r = SemanticMemoryWriteRecord(
        write_id=new_id("smw_"),
        content_summary="example code patterns",
        embedding_model="text-embedding-3-small",
        vector_count=5,
        status="requested",
        approved_by=None,
        created_at=now,
    )
    store.insert_semantic_memory_write(r)
    records = store.list_semantic_memory_writes()
    assert len(records) == 1
    assert records[0]["embedding_model"] == "text-embedding-3-small"


def test_semantic_memory_write_requires_approval() -> None:
    r = SemanticMemoryWriteRecord(
        write_id=new_id("smw_"),
        content_summary="sensitive data",
        embedding_model="test-model",
        vector_count=1,
        status="requested",
        approved_by=None,
        created_at=utc_now(),
    )
    assert r.approved_by is None  # not yet approved


# ── RAIKER-7001: Desktop App ──


def test_desktop_app_session_model() -> None:
    from raiker.contracts.models import DesktopAppSession
    now = utc_now()
    d = DesktopAppSession(session_id=new_id("dsk_"), app_version="1.0.0", window_state="normal", connected_at=now, last_active_at=now)
    assert d.session_id.startswith("dsk_")


# ── RAIKER-7101: Web API ──


def test_web_api_session_model() -> None:
    from raiker.contracts.models import WebApiSession
    s = WebApiSession(token_id=new_id("web_"), session_id="sess_test", client_type="web_ui", created_at=utc_now(), expires_at=utc_now())
    assert s.token_id.startswith("web_")


# ── RAIKER-7701: IDE Extension ──


def test_ide_extension_session_model() -> None:
    from raiker.contracts.models import IdeExtensionSession
    s = IdeExtensionSession(session_id=new_id("ide_"), extension_version="0.1.0", ide_type="vscode", connected_at=utc_now())
    assert s.session_id.startswith("ide_")
