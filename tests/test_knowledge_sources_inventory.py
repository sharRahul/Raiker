"""BUG-305 — one answer to "what can Raiker read", over both kinds of source.

Raiker has two, and they are genuinely different objects. A **managed file** is
bytes Raiker holds, copied into its own storage. A **granted folder** is
somewhere on this machine Raiker may read *in place*. Merging the two stores
would mean either copying a folder nobody asked to copy, or holding an upload as
a path that can move, so they stay two controllers.

What they did not have was one place that answers the owner's question. Memory
listed the copies; the Knowledge Map listed the folders; nothing listed both,
and an owner asking what Raiker can read had to already know the distinction to
find out.

The property that matters most is the last one here, and it is the one the
review row names: revoking a source stops recall and the graph reading it, and
a folder the owner granted is still on disk afterwards. Raiker was given
permission to read it, not ownership of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.knowledge.files import ManagedFileScope, ManagedFileService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _service(ws: Path) -> DashboardService:
    return DashboardService(ws)


def _owner_id(ws: Path) -> str:
    store = SQLiteStore(ws)
    rows = store.list_principals()
    return str(rows[0]["principal_id"])


def _grant_folder(ws: Path, folder: Path) -> str:
    service = _service(ws)
    granted = service.grant_brain_source_folder(str(folder), owner_principal_id=_owner_id(ws))
    return str(granted["root_id"])


def _import_managed_file(ws: Path, name: str = "notes.md") -> str:
    files = ManagedFileService(ws, SQLiteStore(ws))
    record = files.import_file(
        ManagedFileScope(kind="memory", project_id=None),
        name,
        b"# notes\n",
        "text/markdown",
        owner_principal_id=_owner_id(ws),
    )
    return str(record.file_id)


def test_the_inventory_lists_both_kinds_in_one_place(workspace: Path) -> None:
    outside = workspace.parent / "elsewhere"
    outside.mkdir()
    (outside / "paper.md").write_text("# paper\n", encoding="utf-8")
    _import_managed_file(workspace)
    _grant_folder(workspace, outside)

    listing = _service(workspace).knowledge_sources(owner_principal_id=_owner_id(workspace))

    kinds = {entry["kind"] for entry in listing["sources"]}
    assert kinds == {"managed_file", "granted_folder"}
    assert listing["held_count"] == 1
    assert listing["granted_count"] == 1


def test_the_inventory_says_which_bytes_raiker_holds(workspace: Path) -> None:
    """`held` is the whole distinction, and it decides what revoking does."""
    outside = workspace.parent / "elsewhere"
    outside.mkdir()
    _import_managed_file(workspace)
    _grant_folder(workspace, outside)

    by_kind = {
        entry["kind"]: entry
        for entry in _service(workspace).knowledge_sources(
            owner_principal_id=_owner_id(workspace)
        )["sources"]
    }

    assert by_kind["managed_file"]["held"] is True
    assert by_kind["granted_folder"]["held"] is False
    # A folder nobody has indexed yet is granted, not indexed, and says so
    # rather than claiming recall can already read it.
    assert by_kind["granted_folder"]["index_state"] == "granted"
    assert by_kind["granted_folder"]["recall"] is False
    assert by_kind["granted_folder"]["graph"] is False


def test_an_indexed_folder_reports_reaching_recall_and_the_graph(workspace: Path) -> None:
    outside = workspace.parent / "elsewhere"
    outside.mkdir()
    (outside / "paper.md").write_text("# paper\n", encoding="utf-8")
    root_id = _grant_folder(workspace, outside)
    service = _service(workspace)
    service.add_brain_source(f"{root_id}/paper.md", owner_principal_id=_owner_id(workspace))

    entry = next(
        item
        for item in service.knowledge_sources(owner_principal_id=_owner_id(workspace))["sources"]
        if item["kind"] == "granted_folder"
    )

    assert entry["index_state"] == "indexed"
    assert entry["recall"] is True
    assert entry["graph"] is True


def test_revoking_a_folder_stops_recall_and_the_graph_and_keeps_the_file(
    workspace: Path,
) -> None:
    """The review row's own acceptance criterion, in one test.

    Revocation has to suppress both surfaces, and it has to leave the owner's
    file exactly where it was: Raiker was granted permission to read it, not
    ownership of it.
    """
    outside = workspace.parent / "elsewhere"
    outside.mkdir()
    paper = outside / "paper.md"
    paper.write_text("# paper\n", encoding="utf-8")
    owner = _owner_id(workspace)
    root_id = _grant_folder(workspace, outside)
    service = _service(workspace)
    service.add_brain_source(f"{root_id}/paper.md", owner_principal_id=owner)
    assert SQLiteStore(workspace).list_brain_sources(owner) != []

    service.revoke_knowledge_source("granted_folder", root_id, owner_principal_id=owner)

    store = SQLiteStore(workspace)
    # Nothing indexed under that root survives, so neither recall nor the graph
    # can answer from it.
    assert store.list_brain_sources(owner) == []
    assert store.list_brain_source_grants(owner) == []
    listing = service.knowledge_sources(owner_principal_id=owner)
    assert all(entry["kind"] != "granted_folder" for entry in listing["sources"])
    # And the owner's own file is untouched.
    assert paper.exists()
    assert paper.read_text(encoding="utf-8") == "# paper\n"


def test_revoking_a_managed_file_takes_the_copy_raiker_made(workspace: Path) -> None:
    """The other branch, and the reason the two stay two controllers.

    A managed file's bytes are Raiker's own copy, so revoking takes them with
    it. That is the opposite of the folder case above, and getting it the wrong
    way round in either direction is a data-loss bug.
    """
    owner = _owner_id(workspace)
    file_id = _import_managed_file(workspace)
    service = _service(workspace)
    assert any(
        entry["source_id"] == file_id
        for entry in service.knowledge_sources(owner_principal_id=owner)["sources"]
    )

    service.revoke_knowledge_source("managed_file", file_id, owner_principal_id=owner)

    listing = service.knowledge_sources(owner_principal_id=owner)
    assert all(entry["source_id"] != file_id for entry in listing["sources"])


def test_an_unknown_kind_is_refused_rather_than_guessed(workspace: Path) -> None:
    service = _service(workspace)
    with pytest.raises(ValueError, match="unknown_knowledge_source_kind"):
        service.revoke_knowledge_source("something_else", "x", owner_principal_id=_owner_id(workspace))
    with pytest.raises(ValueError, match="knowledge_source_not_named"):
        service.revoke_knowledge_source("managed_file", "  ", owner_principal_id=_owner_id(workspace))
