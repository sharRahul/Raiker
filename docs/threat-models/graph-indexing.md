# Threat model — knowledge-graph indexing (`graph_indexing_runtime`)

`graph_indexing_runtime` is the capability behind the `knowledge_graph` tool and
the graph index it reads. It is a **local, read-derived** capability: it reads
files the agent may already read and writes a derived index. It reaches no
network and executes nothing outside the workspace.

It is documented because a derived index is still a *durable artefact built from
the owner's source*, and because the graph is a retrieval path — what enters it
shapes what later turns are told.

## What the capability does

Two things answer to this one gate:

- **Indexing** — `raiker/runtime/executors/tier3_core.py` → `GraphIndexingExecutor`
  runs `GraphIndexer.index_python_directory()`, which walks `*.py` under the
  workspace with `.venv` and `__pycache__` skipped and extracts symbols with
  Python's own `ast`: functions, async functions, classes, nested functions,
  module-level assignments, and their docstrings.
- **Reading** — the `knowledge_graph` tool exposes `entities` and `neighbors`
  over the stored graph, brokered like every other read.

Entity and relationship rows that come from *memory and conversation evidence*
are a separate, reviewed path: approved evidence creates owner-scoped proposals,
and **only accepted proposals reach graph recall** (MEM-06 / FIXED-241).

## Assets

| Asset | Why it matters |
|---|---|
| The derived index | It is a map of the owner's private source tree, held in the encrypted store |
| Docstrings captured as node text | Source comments can contain more than the owner remembers putting there |
| Graph recall | Whatever the graph asserts is fed to later turns as context |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Indexing grants the agent new reach | It does not. The index is derived from files the agent may already read, and reading one at the coordinates the index records still goes through `read_file`, workspace containment and the PolicyEngine | `raiker/tools/filesystem.py` |
| Indexing escapes the workspace | The walk is rooted at the resolved workspace root; `.venv` and `__pycache__` are skipped | `raiker/graph/indexer.py` |
| A malformed source file crashes the turn | Extraction is wrapped; a failure returns `graph_index_failed:<reason>` and the index is unchanged | `tier3_core.py` |
| Unreviewed entities enter recall | Entity/relationship proposals derived from evidence are owner-reviewed; only accepted ones are recalled | `raiker/memory/entity_extraction.py` |
| An edge outlives the evidence that justified it | Every edge carries the approved memory that evidences it; archiving or forgetting the evidence deactivates the projection and removes the edge | `raiker/memory/store.py` |
| Source content leaking into runtime events | Executor artifacts carry the scope only | `tier3_core.py` |

## Residual risk, stated plainly

- **The graph indexer is Python-only.** `index_python_directory` walks `*.py` and
  nothing else. A repository in another language produces an empty graph from
  this path. The multi-language surface is the **code map**, a separate capability
  — see [`code-map-indexing.md`](code-map-indexing.md).
- **There is no size bound on this walk.** Unlike the code map, `GraphIndexer` has
  no file-count, file-size or symbol ceiling, and no `partial` outcome: a very
  large tree is walked to the end. `.gitignore` is not consulted; only `.venv`
  and `__pycache__` are skipped by name.
- **Docstrings are captured verbatim into the index.** A credential written into a
  docstring is indexed as node text. The memory sensitivity classifier
  (`classify_memory_sensitivity`) governs the *memory* write path, not this one.
- **Nothing expires by itself.** `expires_at` is enforced at read time; no
  retention sweep runs, and expired rows are collected only when the owner
  confirms a cleanup (MEM-07).

## Evidence

- `raiker/runtime/executors/tier3_core.py`, `raiker/graph/indexer.py`,
  `raiker/tools/graph_tools.py`
- [`../GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](../GRAPH_MEMORY_AND_CODEMAP_SPEC.md)
- [`../MEMORY_GOVERNANCE_RULES.md`](../MEMORY_GOVERNANCE_RULES.md)
- [`vector-embedding.md`](vector-embedding.md) — the sibling local retrieval path
