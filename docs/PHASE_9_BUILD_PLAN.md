# Phase 9 Build Plan — Advanced Memory and Graph

Phase 9 activates the advanced memory and graph runtime features: vector index, graph/codemap runtime index, project-level graph extraction, and procedural memory to skill candidate conversion.

Phase 9 builds on the data contracts established in Phase 7 (GraphIndexRecord, SemanticMemoryWriteRecord) and the memory/governance foundations from earlier phases.

---

## Dependency Graph

```text
RAIKER-9001 vector index and semantic memory runtime
  -> RAIKER-9101 graph/codemap runtime index (AST extraction)
  -> RAIKER-9201 project-level graph extraction
  -> RAIKER-9301 procedural memory → skill candidate conversion
```

---

## Tasks

| Task ID | Scope | Contracts/events/storage | Policy | Tests | Acceptance criteria |
|---|---|---|---|---|---|
| RAIKER-9001 | Vector index and semantic memory runtime | VectorIndex, EmbeddingRecord, vector search | Sensitivity filters; approval for writes | Vector index tests | Vector index stores embeddings and returns similarity search results. |
| RAIKER-9101 | Graph/codemap runtime index | SymbolNode, DependencyEdge, AST extraction | Policy-gated; no destructive writes | Graph index tests | Graph index extracts symbols and dependencies from Python source files. |
| RAIKER-9201 | Project graph extraction | ProjectGraph, module-level dependency graph | Read-only by default | Project graph tests | Project graph provides module dependency and import map. |
| RAIKER-9301 | Procedural memory → skill candidate | SkillCandidate, skill proposal from repeated workflows | Approval required | Skill candidate tests | Repeated verified workflows generate skill candidate proposals. |

---

## Storage requirements

Allowed Phase 9 storage categories:

- vector/embedding records with content hash and metadata;
- graph symbol nodes and dependency edges;
- project-level module dependency map;
- skill candidate records with provenance.

## Validation requirements

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
```

Phase 9 tests must prove:

- vector index stores embeddings and returns results by similarity;
- graph index extracts Python symbols (functions, classes, imports);
- project graph maps module dependencies;
- skill candidates are created from verified repeated patterns only;
- all features respect policy and approval gates.

---

## Completion rule

Phase 9 is not complete until vector index, graph index, project graph, and skill candidate features are implemented, tested, and documented.
