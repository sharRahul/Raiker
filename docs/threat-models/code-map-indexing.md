# Threat model — repository code map (`code_map_indexing`)

`code_map_indexing` is one gate over the whole code-map feature: the scan that
builds the index **and** the `code_map_search` and `code_map_references` reads
over it. Naming the reads under the same capability is deliberate — an owner who
turns the feature off should not find half of it still answering.

It is local and read-derived. It executes nothing outside the workspace, reaches
no network, and grants no authority to the turn that asked for it.

## What the capability does

`raiker/runtime/executors/tier3_core.py` → `CodeMapIndexExecutor` supports two
operations:

- **`build`** — a full scan producing a symbol index for the repository Build
  points at. Outcome is `indexed` or **`partial`**, and `partial` names the bound
  it hit rather than presenting an incomplete answer as a complete one.
- **`refresh`** — re-parses only the paths an approved change touched. It
  requires `paths`; an empty list fails closed with `missing_argument:paths`.
  A refresh runs once, at the single point an approved file mutation is known to
  have landed (in the approval relay), and is **best-effort**: a refresh that
  fails changes nothing about the write that already succeeded.

Any other operation fails closed with `unknown_operation:<op>`.

## Bounds, stated exactly

`raiker/graph/codemap.py`:

| Bound | Value |
|---|---|
| Files scanned | 20 000 |
| Bytes per file | 512 000 |
| Symbols | 200 000 |
| Edges | 200 000 |
| Directory depth | 24 |

`raiker/graph/codemap_service.py`, for the reads:

| Bound | Value |
|---|---|
| Search terms | 8 |
| Search results | 25 |
| Context files | 10 |
| Files scanned for references | 1 500 |
| Bytes per file for references | 512 000 |
| Characters kept per matched line | 240 |

Directories never walked: every dot-directory (so `.git`, `.raiker`, `.venv` and
every cache), plus `node_modules`, `__pycache__`, `venv`, `site-packages`,
`dist`, `build`, `target`, `coverage`, `htmlcov`, `vendor`, `bower_components`
and `Pods`.

Thirty suffixes map to eighteen languages. **Python is parsed with a real
parser** (`python_ast`, falling back to `python_ast_unparsed`); **fifteen**
languages are matched with bounded regular expressions (`regex`); Markdown and
SQL get path and title only (`none`). Each file records **which extractor
produced it**, so the map never implies a precision it does not have.

## Assets

| Asset | Why it matters |
|---|---|
| The symbol index | A structural map of the owner's private repository, held in the encrypted store |
| Signatures and leading docstrings captured as titles | Source text enters a durable index |
| `@`-mention completion | It completes against this index, so what it holds is visible in the composer |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Indexing grants the agent new reach | It does not. The map is derived from files the agent may already read; reading one at the coordinates it records still goes through `read_file`, workspace containment and the PolicyEngine | `raiker/tools/filesystem.py` |
| A scan escapes the workspace or descends into secrets | Rooted at the workspace; `.raiker` and `.git` are dot-directories and therefore never walked; depth capped at 24 | `raiker/graph/codemap.py` |
| A hostile repository exhausts the host | Every dimension is bounded, and hitting a bound yields `partial` with the bound named | `raiker/graph/codemap.py` |
| A stale index sends the next turn to a line that has moved | Refresh runs at the one point an approved mutation is known to have landed, re-parsing only the touched paths | `raiker/runtime/executors/tier1_approval.py` |
| A failed refresh rolls back the owner's approved change | It cannot — refresh is best-effort and strictly after the write | `tier1_approval.py` |
| `find references` implying a resolved call graph | It is textual, word-boundary matching over files the map already accepted, excluding the declaration itself, and it says so | `codemap_service.py` |
| Index content leaking into runtime events | Artifacts are counts and status; the `refresh` artifact drops `paths` | `tier3_core.py` |

## Residual risk, stated plainly

- **It matches text; it does not resolve symbols.** A same-named symbol from
  another module matches. There is no call graph and no embeddings over the tree.
- **A regex extractor misses unusual declarations.** Fifteen of the eighteen
  languages are pattern-matched. `extractor` on each file is how a reader tells
  which kind of answer they are getting.
- **`.gitignore` is not consulted.** Exclusion is by the fixed directory list and
  the dot-directory rule above. A generated or vendored tree outside that list is
  indexed.
- **Signatures and leading docstrings are stored verbatim** (bounded to 200 and
  240 characters). A secret on the first line of a file can enter the index. The
  index lives in the encrypted store and is not emitted into events, but it is not
  scanned for credentials.

## Evidence

- `raiker/runtime/executors/tier3_core.py`, `raiker/graph/codemap.py`,
  `raiker/graph/codemap_service.py`, `raiker/tools/codemap_tools.py`
- [`../GRAPH_MEMORY_AND_CODEMAP_SPEC.md`](../architecture/GRAPH_MEMORY_AND_CODEMAP_SPEC.md)
- [`../BUILD_WORKSPACE_SPEC.md`](../architecture/BUILD_WORKSPACE_SPEC.md)
