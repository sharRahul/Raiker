# Threat model — language intelligence (`language_intelligence`)

`language_intelligence` is one gate over three reads of what the repository
*means* rather than what it says: `document_symbols` (one file's outline),
`find_definition` (where an exact name is declared) and `diagnostics` (whether a
file still parses). It is GAP-BUILD B10.

It is **local and derives nothing durable**. It executes nothing outside the
workspace, reaches no network, writes no index — not even a cache — and grants no
authority to the turn that asked for it. Every answer is a parse of a file
`read_file` would already open.

## Why it is not `code_map_indexing`

That gate governs *writing a derived symbol index of the owner's machine*: a
scan that walks the tree and persists what it finds. These three persist nothing.
An owner must be able to have either without the other, and one switch meaning
two postures is the defect this codebase keeps finding — so each capability names
what it governs and nothing else. Both resolve an unset gate the same way
(`UNSET_SHIPPED_DEFAULT_UNSCOPED`), so an owner meets one posture for "read my
repository" rather than two.

`find_definition` reads the code map's stored symbols, so it is the one entry
point whose *usefulness* depends on `code_map_indexing` having run. It says so
rather than failing: with no map built it returns zero definitions and names the
alternative.

## What the capability does

`raiker/runtime/executors/tier3_core.py` → `LanguageIntelligenceExecutor`
supports exactly three operations; anything else fails closed with
`unknown_operation:<op>`.

| Operation | Reads | Returns |
|---|---|---|
| `document_symbols` | One file, from disk | Declarations with line ranges, and the file's imports |
| `find_definition` | The stored code map | Coordinates of exact-name declarations, ranked by proximity |
| `diagnostics` | Up to 50 files, from disk | Parse problems with path, line, column and source |

## Bounds, stated exactly

`raiker/graph/language_service.py`:

| Bound | Value |
|---|---|
| Bytes parsed per file | 512 000 |
| Files per `diagnostics` call | 50 |
| Definitions returned | 10 |
| Symbols returned per file | 500 |

## Assets

| Asset | Why it matters |
|---|---|
| Names, signatures and docstrings from the owner's private repository | Source text enters a tool result the model reads |
| Parser messages | A syntax error message quotes the source it failed on |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| These reads grant the agent new reach | They do not. Every path resolves through the repository root and is re-checked after resolution, so a `..` segment or a symlink cannot walk out; reading a file's *contents* still goes through `read_file` | `language_service.py` |
| A path escapes the repository | Containment is checked on the **resolved** path on every entry point, including each path in a `diagnostics` batch | `language_service.py` |
| A hostile repository exhausts the host | Every dimension is bounded, and a `diagnostics` call over more files than the bound reports `truncated` rather than silently checking fewer | `language_service.py` |
| A clean bill from a check that did not happen | A language this runtime cannot parse is returned under `unsupported`, never as clean. The tool description tells the model to read `checked`, and the UI renders "Not checked" rather than "No problems" | `language_service.py`, `CodeExplorer.svelte` |
| Repository text read as instructions | Every result carries `trust_label: untrusted_repository_data` and says so in its note, exactly as a fetched page does | `language_service.py` |
| The workspace explorer becoming a second, weaker path boundary | The route resolves and contains the path itself, then hands the service that same root, so both answers about one file come from one containment decision | `raiker/api/routes_code_files.py` |
| A long-running language server to supervise, crash, or leak | There is none. BUG-227 was answered by deciding against an LSP client; nothing here outlives the call | `PLUGIN_SYSTEM_SPEC.md` |

## Residual risk, stated plainly

- **Diagnostics are parse-level.** Syntax and structure, not types, imports or
  lint rules. A file that parses can still be wrong, and the tool's own note says
  so.
- **Only Python, JSON, TOML and YAML are parsed.** Everything else — TypeScript,
  Go, Rust and the rest — is reported as `unsupported` and is **not checked**.
  YAML additionally depends on PyYAML being installed; without it those files are
  `unsupported` too, rather than assumed clean.
- **`find_definition` matches by exact name, not by resolved symbol.** A
  same-named class in another module is a real candidate. Proximity ranking makes
  the likely one first; it does not make the others wrong to return.
- **Parser messages are stored verbatim in the tool result.** A syntax error can
  quote the line it failed on, including a secret on that line. The result is
  redacted on the same paths every other tool result is, and is labelled
  untrusted.
- **`document_symbols` reads from disk rather than from the index**, which is
  what makes it correct after an edit — and means it has no `.gitignore`
  awareness of its own. The caller names the file.

## Evidence

- `raiker/graph/language_service.py`, `raiker/tools/language_tools.py`,
  `raiker/runtime/executors/tier3_core.py`, `raiker/api/routes_code_files.py`
- `tests/test_language_intelligence.py`, `tests/test_code_repo_files_api.py`
- [`../plans/GAP_BUILD_CHAT.md`](../plans/GAP_BUILD_CHAT.md) → B10
