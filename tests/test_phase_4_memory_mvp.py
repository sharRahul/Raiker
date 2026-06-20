from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.memory.store import (
    forget_memory,
    get_memory,
    list_memory,
    memory_status,
    search_memory,
    write_memory,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.memory_tools import memory_forget, memory_search, memory_write


@pytest.fixture
def workspace() -> Path:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = Path(d)
        (path / ".raiker").mkdir(parents=True, exist_ok=True)
        yield path


def test_write_and_read_memory(workspace: Path) -> None:
    entry = write_memory("This is a test memory about project Raiker.", workspace_root=workspace)
    assert entry.memory_id.startswith("mem_")
    assert entry.text == "This is a test memory about project Raiker."
    assert entry.scope == "project"

    retrieved = get_memory(entry.memory_id, workspace_root=workspace)
    assert retrieved is not None
    assert retrieved.text == entry.text
    assert retrieved.memory_id == entry.memory_id


def test_write_memory_with_tags(workspace: Path) -> None:
    entry = write_memory(
        "API design notes for the gateway module.",
        workspace_root=workspace,
        scope="project",
        tags=("api", "gateway", "design"),
    )
    assert "api" in entry.tags
    assert "gateway" in entry.tags


def test_search_memory_keyword(workspace: Path) -> None:
    write_memory("The llama.cpp provider is the native default.", workspace_root=workspace)
    write_memory("OpenAI compatible providers use httpx.", workspace_root=workspace)
    write_memory("SQLite is used for metadata storage.", workspace_root=workspace)

    results = search_memory("llama", workspace_root=workspace)
    assert len(results) >= 1
    assert any("llama.cpp" in r.text for r in results)

    results = search_memory("httpx", workspace_root=workspace)
    assert len(results) >= 1
    assert any("httpx" in r.text for r in results)


def test_search_memory_empty_query(workspace: Path) -> None:
    write_memory("Some test content.", workspace_root=workspace)
    results = search_memory("nonexistent_term_xyz", workspace_root=workspace)
    assert len(results) == 0


def test_forget_memory(workspace: Path) -> None:
    entry = write_memory("Temporary note to be removed.", workspace_root=workspace)
    assert get_memory(entry.memory_id, workspace_root=workspace) is not None

    result = forget_memory(entry.memory_id, workspace_root=workspace)
    assert result is True

    assert get_memory(entry.memory_id, workspace_root=workspace) is None


def test_forget_nonexistent_memory(workspace: Path) -> None:
    result = forget_memory("nonexistent_id", workspace_root=workspace)
    assert result is False


def test_list_memory(workspace: Path) -> None:
    write_memory("Memory A", workspace_root=workspace, scope="project")
    write_memory("Memory B", workspace_root=workspace, scope="project")
    write_memory("Personal note", workspace_root=workspace, scope="personal")

    all_entries = list_memory(workspace_root=workspace)
    assert len(all_entries) >= 3

    project_entries = list_memory(workspace_root=workspace, scope="project")
    assert len(project_entries) >= 2
    assert all(e.scope == "project" for e in project_entries)


def test_memory_status(workspace: Path) -> None:
    status = memory_status(workspace_root=workspace)
    assert "approved_memory_count" in status
    assert status["memory_store"] == "markdown_files"

    write_memory("Test memory", workspace_root=workspace, tags=("test",))
    status = memory_status(workspace_root=workspace)
    assert status["approved_memory_count"] >= 1
    assert "test" in status["tags"]


def test_memory_write_policy_blocks_secrets(workspace: Path) -> None:
    result = memory_write(
        workspace,
        "The password=supersecret123! and api_key=abc123def456ghi789jkl",
    )
    assert result["status"] == "denied"
    assert "policy_denied" in str(result)


def test_memory_write_policy_blocks_credentials(workspace: Path) -> None:
    result = memory_write(
        workspace,
        "Bearer token: abcdefghijklmnopqrstuvwxyz123456",
    )
    assert result["status"] == "denied"
    assert "policy_denied" in str(result)


def test_memory_write_policy_allows_normal(workspace: Path) -> None:
    result = memory_write(workspace, "The project uses Python 3.11 with httpx for async HTTP.")
    assert result["status"] == "success"
    assert result["memory_id"].startswith("mem_")


def test_memory_search_via_tool(workspace: Path) -> None:
    memory_write(workspace, "Raiker uses SQLite for metadata persistence.")
    memory_write(workspace, "The agent gateway routes prompts to the model provider.")

    result = memory_search(workspace, "SQLite")
    assert result["status"] == "success"
    assert result["count"] >= 1
    assert any("SQLite" in r["text"] for r in result["results"])


def test_memory_forget_via_tool(workspace: Path) -> None:
    result = memory_write(workspace, "Memory to forget via tool.")
    memory_id = result["memory_id"]

    forget_result = memory_forget(workspace, memory_id)
    assert forget_result["status"] == "success"

    forget_result = memory_forget(workspace, "nonexistent")
    assert forget_result["status"] == "failed"


def test_classify_memory_sensitivity() -> None:
    assert classify_memory_sensitivity("public documentation about the API") == MemorySensitivity.PUBLIC
    assert classify_memory_sensitivity("project raiker workspace repo") == MemorySensitivity.PROJECT
    assert classify_memory_sensitivity("my email is user@example.com") == MemorySensitivity.PERSONAL
    assert classify_memory_sensitivity("-----BEGIN RSA PRIVATE KEY-----") == MemorySensitivity.CREDENTIAL_LIKE
    assert classify_memory_sensitivity("abcdefghijklmnopqrstuvwxyz0123456789abcdefghijklmn") == MemorySensitivity.SECRET_LIKE
    assert classify_memory_sensitivity("") == MemorySensitivity.UNKNOWN


def test_memory_persistence_across_store(workspace: Path) -> None:
    from raiker.tools.memory_tools import memory_write as tool_memory_write
    tool_memory_write(workspace, "This persists in markdown files.")
    store = SQLiteStore(workspace)
    entries = store.list_approved_memory()
    assert len(entries) >= 1
    assert any("persists" in row["text"] for row in entries)


def test_memory_write_empty_denied(workspace: Path) -> None:
    result = memory_write(workspace, "")
    assert result["status"] == "failed"

    result = memory_write(workspace, "   ")
    assert result["status"] == "failed"
