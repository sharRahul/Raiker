from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    DependencyEdge,
    ProjectGraph,
    SkillCandidate,
    SymbolNode,
    VectorRecord,
)
from raiker.graph.indexer import GraphIndexer
from raiker.graph.project_graph import ProjectGraphExtractor
from raiker.skills import SkillCandidateStore
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import VectorIndex


@pytest.fixture
def workspace() -> Path:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


# ── RAIKER-9001: Vector Index ──


def test_vector_index_upsert_and_search() -> None:
    idx = VectorIndex(dimensions=3)
    idx.upsert("v1", [1.0, 0.0, 0.0], {"text": "hello"})
    idx.upsert("v2", [0.0, 1.0, 0.0], {"text": "world"})
    idx.upsert("v3", [0.0, 0.0, 1.0], {"text": "foo"})
    results = idx.search([1.0, 0.1, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0]["vector_id"] == "v1"
    assert results[0]["score"] > 0.9


def test_vector_index_empty_search() -> None:
    idx = VectorIndex(dimensions=3)
    assert idx.search([1.0, 0.0, 0.0]) == []


def test_vector_index_chunk_text() -> None:
    chunks = VectorIndex.chunk_text("hello world how are you", chunk_size=10, overlap=3)
    assert len(chunks) >= 2


def test_vector_index_content_hash() -> None:
    h = VectorIndex.compute_content_hash("test content")
    assert len(h) == 64


def test_vector_index_flush() -> None:
    idx = VectorIndex(dimensions=2)
    idx.upsert("v1", [1.0, 0.0])
    snapshot = idx.flush()
    assert len(snapshot["vectors"]) == 1
    assert idx.count() == 0


def test_vector_record_sqlite_crud(store: SQLiteStore) -> None:
    now = utc_now()
    r = VectorRecord(
        vector_id=new_id("vec_"),
        content_hash="abc123",
        content_preview="test embedding",
        embedding_model="text-embedding-3-small",
        dimensions=384,
        scope="project",
        sensitivity="public",
        created_at=now,
    )
    store.insert_vector_record(r)
    records = store.list_vector_records()
    assert len(records) == 1
    assert records[0]["dimensions"] == 384


# ── RAIKER-9101: Graph Index (AST Extraction) ──


def test_graph_indexer_extracts_symbols(workspace: Path) -> None:
    src = workspace / "sample.py"
    src.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "class MyClass:\n"
        "    def method(self):\n"
        "        pass\n\n"
        "def my_function():\n"
        "    pass\n\n"
        "x = 42\n"
    )
    indexer = GraphIndexer(workspace)
    indexer.index_python_file(src)
    assert len(indexer.symbols) >= 4
    names = {s.name for s in indexer.symbols}
    assert "MyClass" in names
    assert "my_function" in names
    assert "x" in names


def test_graph_indexer_detects_imports(workspace: Path) -> None:
    src = workspace / "importer.py"
    src.write_text("import os\nfrom pathlib import Path\n")
    indexer = GraphIndexer(workspace)
    indexer.index_python_file(src)
    assert len(indexer.dependencies) >= 2


def test_graph_indexer_summary(workspace: Path) -> None:
    src = workspace / "mod.py"
    src.write_text("def foo(): pass\nclass Bar: pass\n")
    indexer = GraphIndexer(workspace)
    indexer.index_python_file(src)
    s = indexer.summary()
    assert s["symbol_count"] >= 2
    assert "function" in s["symbol_kinds"]


def test_graph_indexer_skips_non_python(workspace: Path) -> None:
    txt = workspace / "readme.txt"
    txt.write_text("not python")
    indexer = GraphIndexer(workspace)
    indexer.index_python_file(txt)
    assert len(indexer.symbols) == 0


def test_symbol_node_sqlite_crud(store: SQLiteStore) -> None:
    now = utc_now()
    n = SymbolNode(
        symbol_id=new_id("sym_"),
        name="my_func",
        kind="function",
        file_path="src/main.py",
        line_number=10,
        module="src.main",
        parent_symbol_id=None,
        doc_preview="Does something",
        created_at=now,
    )
    store.insert_symbol_node(n)
    symbols = store.list_symbol_nodes(kind="function")
    assert len(symbols) >= 1
    assert symbols[0]["name"] == "my_func"


def test_dependency_edge_sqlite_crud(store: SQLiteStore) -> None:
    now = utc_now()
    e = DependencyEdge(
        edge_id=new_id("dep_"),
        source_symbol_id="sym_a",
        target_symbol_id="sym_b",
        dep_type="import",
        file_path="src/a.py",
        line_number=1,
        created_at=now,
    )
    store.insert_dependency_edge(e)
    assert e.edge_id.startswith("dep_")


# ── RAIKER-9201: Project Graph ──


def test_project_graph_extractor_module_map(workspace: Path) -> None:
    (workspace / "mymod").mkdir()
    (workspace / "mymod" / "__init__.py").write_text("from . import core\n")
    (workspace / "mymod" / "core.py").write_text("import os\n")
    extractor = ProjectGraphExtractor(workspace)
    modules = extractor.extract_module_map()
    assert len(modules) >= 2
    core_key = next(k for k in modules if "core" in k)
    assert modules[core_key]["import_count"] >= 1


def test_project_graph_build_dependency_graph(workspace: Path) -> None:
    (workspace / "pkg").mkdir()
    (workspace / "pkg" / "__init__.py").write_text("")
    (workspace / "pkg" / "a.py").write_text("import pkg.b\n")
    (workspace / "pkg" / "b.py").write_text("")
    extractor = ProjectGraphExtractor(workspace)
    graph = extractor.build_dependency_graph()
    assert graph["module_count"] >= 2


def test_project_graph_suggest_skill_candidates(workspace: Path) -> None:
    (workspace / "heavy").mkdir()
    (workspace / "heavy" / "__init__.py").write_text("import os\nimport sys\nimport json\nimport re\n")
    extractor = ProjectGraphExtractor(workspace)
    candidates = extractor.suggest_skill_candidates(min_dependencies=1)
    assert len(candidates) >= 1


def test_project_graph_sqlite_crud(store: SQLiteStore) -> None:
    now = utc_now()
    g = ProjectGraph(
        graph_id=new_id("pg_"),
        workspace_root="/test",
        module_count=10,
        dependency_count=25,
        built_at=now,
    )
    store.insert_project_graph(g)
    graphs = store.list_project_graphs()
    assert len(graphs) == 1
    assert graphs[0]["module_count"] == 10


# ── RAIKER-9301: Skill Candidates ──


def test_skill_candidate_store_propose_and_list() -> None:
    store = SkillCandidateStore()
    c = store.propose("test_skill", "A test skill", {"steps": ["read", "analyze"]}, ["read_file", "grep"], "test_provenance")
    assert c["status"] == "proposed"
    assert c["candidate_id"].startswith("skc_")
    assert len(store.list_candidates()) == 1
    assert len(store.list_candidates(status_filter="proposed")) == 1
    assert len(store.list_candidates(status_filter="approved")) == 0


def test_skill_candidate_store_review() -> None:
    store = SkillCandidateStore()
    c = store.propose("test", "desc", {}, [], "prov")
    assert store.review(c["candidate_id"], "approved") is not None
    assert store.list_candidates(status_filter="approved")[0]["candidate_id"] == c["candidate_id"]
    assert store.review("nonexistent", "approved") is None


def test_skill_candidate_generate_from_pattern() -> None:
    result = SkillCandidateStore.generate_from_pattern("Code Review", ["read_file", "grep", "diff_files"], [".py"], 5)
    assert result["name"] == "code_review_skill"
    assert "read_file" in result["suggested_tools"]


def test_skill_candidate_sqlite_crud(store: SQLiteStore) -> None:
    now = utc_now()
    c = SkillCandidate(
        candidate_id=new_id("skc_"),
        name="auto-review",
        description="Automated code review skill",
        source_workflow_json=json.dumps({"steps": ["review", "summarize"]}),
        suggested_tools_json=json.dumps(["read_file", "grep"]),
        provenance="observed_workflow",
        status="proposed",
        created_by="system",
        created_at=now,
    )
    store.insert_skill_candidate(c)
    candidates = store.list_skill_candidates()
    assert len(candidates) == 1
    assert candidates[0]["name"] == "auto-review"
    proposed = store.list_skill_candidates(status="proposed")
    assert len(proposed) == 1
    assert store.list_skill_candidates(status="approved") == []
