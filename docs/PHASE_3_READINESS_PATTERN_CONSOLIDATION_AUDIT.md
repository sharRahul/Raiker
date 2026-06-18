# Phase 3 Readiness Pattern Consolidation Audit

Date: 2026-06-18
Baseline: PR #46 merged Slice O on merge commit `1200184d3e2fddff5016072681f61e11af749a17`.

## Current baseline after Slice O

- Phase 3 remains incomplete.
- Phase 4 remains blocked for runtime activation work.
- Runtime execution remains disabled across readiness surfaces.
- Slice P is not implemented.
- Slices J through O are present as metadata-only readiness slices:
  - Slice J: graph/codemap indexing readiness.
  - Slice K: semantic memory write readiness.
  - Slice L: approval-preview persistence readiness.
  - Slice M: storage cleanup execution readiness.
  - Slice N: plugin/server startup readiness.
  - Slice O: external channels/notifications readiness.

## Readiness slices reviewed

The audit reviewed the readiness contracts, registries, SQLite migrations, CLI command routing, workspace inspection/view summaries, documentation, and focused tests for Slices J through O:

- `raiker/graph/readiness.py` and `raiker/graph/readiness_registry.py`
- `raiker/memory/readiness.py` and `raiker/memory/readiness_registry.py`
- `raiker/approvals/readiness.py` and `raiker/approvals/readiness_registry.py`
- `raiker/storage/cleanup_readiness.py` and `raiker/storage/cleanup_readiness_registry.py`
- `raiker/plugins/readiness.py` and `raiker/plugins/readiness_registry.py`
- `raiker/channels/readiness.py` and `raiker/channels/readiness_registry.py`
- `raiker/cli/commands.py`
- `raiker/storage/migrations.py`
- `raiker/storage/sqlite.py`
- `raiker/workspace/inspection.py`
- `raiker/workspace/views.py`
- Readiness-focused tests for Slices J, K, L, M, N, and O.

## Repeated patterns found

The six readiness slices now repeat a common metadata-only readiness pattern:

1. Deterministic readiness IDs are derived from canonical JSON with `sort_keys=True`, a SHA-256 digest truncated to 16 hex characters, and a slice-specific prefix.
2. Each contract has a slice-specific target capability, slice ID, readiness version, required gates, blockers, disabled reason, disabled runtime flags, and readiness boolean that always returns `False`.
3. Contract validation requires non-empty identity strings and tuple-based gate/blocker collections containing non-empty strings.
4. Metadata is recursively JSON-safe: dictionaries require string keys; nested dict, list, tuple, scalar, boolean, and null values are accepted; arbitrary Python objects are rejected.
5. Serialization is deterministic by sorting metadata keys and by emitting JSON with sorted keys where a `to_json()` helper exists.
6. Registries maintain in-memory records, optionally persist metadata-only records to SQLite, list records deterministically, expose get-by-ID lookup, produce summary dictionaries, and render text summaries.
7. CLI surfaces support default text rendering, `--summary`, `--json`, and usage-only rejection for unsafe or invalid arguments.
8. Workspace inspection and workspace view summaries expose the same metadata-only disabled-runtime state to equal primary clients.
9. Tests assert deterministic IDs, disabled runtime flags, JSON-safe metadata rejection, registry create/list/get/summary behavior, SQLite table creation, CLI modes, workspace surfaces, and phase safety language.

## Drift found

The audit found two small drift items:

- Slice J graph/codemap readiness did not reject an empty blocker set while the disabled runtime readiness boolean still returned `False`. Later slices K through O reject unblocked disabled-runtime contracts. This was a validation drift, not a runtime activation bug.
- Slice J did not expose the deterministic `to_json()` helper that slices K through O expose. This was a serialization utility drift.

Both drift items were fixed with minimal, behavior-preserving safety alignment: Slice J now rejects empty blockers while graph/codemap indexing is disabled and exposes deterministic JSON serialization. No runtime behavior was enabled.

The audit also found documentation lag in the README current status summary: Slice N and Slice O were already merged but the status paragraph still stopped at Slice M. The README was updated to include Slice N and Slice O without changing implementation status.

No inconsistent ID generation, metadata recursion, summary semantics, CLI mode handling, workspace summary disabled flags, catalog/event language, or missing focused readiness tests were found beyond the Slice J drift described above. SQLite table shape is intentionally not fully uniform: Slice J uses its original table columns, while Slices K through O use a compact shared shape. That difference is backward-compatible drift risk, not a current bug.

## Duplication risk

Duplication is now significant. Most readiness contract, registry, CLI, workspace-summary, and SQLite persistence code repeats the same implementation shape with slice-specific constants. The risk increases with each additional Phase 3 slice because a safety invariant can be omitted in one slice without being caught by shared code. The Slice J blocker validation drift demonstrates this risk.

## Consolidation recommendation

A shared internal readiness foundation is recommended before Slice P unless maintainers intentionally want one more metadata-only slice before consolidating. Consolidation should be internal and backward-compatible, and it should not enable runtime behavior.

### Proposed shared modules

- `raiker/readiness/contracts.py`
  - Shared JSON-safe metadata validation.
  - Shared deterministic ID payload construction and digest generation.
  - Shared disabled-runtime blocker validation.
  - Shared deterministic `to_dict()`/`to_json()` helpers.
- `raiker/readiness/registry.py`
  - Shared in-memory create/list/get/summary/render behavior parameterized by slice descriptor.
  - Shared deterministic sorting and latest-record selection.
- `raiker/readiness/sqlite.py`
  - Shared metadata-only persistence helper for the compact table shape used by Slices K through O.
  - Backward-compatible adapter for Slice J's original table shape, or a non-destructive migration if maintainers choose to normalize later.
- `raiker/readiness/cli.py`
  - Shared `--summary`, `--json`, default render, and invalid-usage behavior.
- `raiker/readiness/workspace.py`
  - Shared workspace summary construction for metadata-only readiness surfaces.

### What can be centralized safely

- JSON-safe metadata recursion and ValueError messages.
- Deterministic readiness ID hashing mechanics while preserving existing prefixes and payload fields.
- Non-empty blocker enforcement while runtime remains disabled.
- Deterministic serialization and metadata key ordering.
- Registry create/list/get/summary/render boilerplate.
- CLI mode parsing for readiness commands.
- Disabled runtime flag inclusion in summaries.
- Common test fixtures for readiness invariants.

### What must remain slice-specific

- Readiness ID prefixes.
- Target capability names.
- Slice IDs and disabled reasons.
- Required gate names and ordering.
- Slice-specific ready field names such as `ready_for_indexing`, `ready_for_memory_writes`, and `ready_for_external_channels`.
- Disabled runtime flag names.
- User-facing command names and render headings.
- SQLite table names and any backward-compatible legacy column choices.
- Documentation language that ties a readiness surface to its phase slice.

### Migration and backward-compatibility impact

The consolidation should preserve existing public imports, function names, dataclass names, readiness IDs, CLI commands, summary keys, workspace keys, and SQLite table names. The safest path is to add internal shared helpers and have existing slice modules delegate to them. Existing table shapes should be preserved at first; any schema normalization should be an explicit later migration with compatibility tests.

### Test strategy

- Keep all existing focused readiness tests for Slices J through O.
- Add shared invariant tests that parameterize over every readiness slice.
- Assert all runtime-enabled flags remain `False`.
- Assert all disabled readiness contracts reject empty blockers.
- Assert deterministic IDs do not change for representative default contracts.
- Assert CLI invalid arguments never execute runtime behavior.
- Assert workspace inspection/view summaries preserve existing keys.
- Assert SQLite table names and persisted JSON remain backward-compatible.
- Continue docs/catalog/status validation through `scripts/validate_phase_status.py`.

### Risks

- Over-consolidation could obscure slice-specific safety language and make future slices too generic.
- Any accidental change to readiness ID payloads could break persisted references.
- Normalizing SQLite too early could create unnecessary migration churn.
- Shared CLI helpers must not relax invalid-argument handling or introduce execution verbs.

## Runtime safety boundaries

This audit and its small validation fix do not enable any runtime behavior:

- Graph/codemap indexing remains disabled.
- Semantic/vector/embedding writes remain disabled.
- Approval execution, relay runtime, and durable approval queues remain disabled.
- Cleanup, deletion, purge, tombstone, and rollback execution remain disabled.
- Plugin/server startup and plugin execution remain disabled.
- External channels, notifications, webhooks, transports, and relays remain disabled.
- Workers, schedulers, file watchers, daemons, and runtime execution remain disabled.

## Recommendation before Slice P

Implement a shared internal readiness foundation before Slice P if maintainers expect more metadata-only readiness slices. The foundation should be small, incremental, and test-backed. It should centralize invariants and boilerplate while preserving all existing public behavior and slice-specific language.

Do not implement Slice P until maintainers decide whether readiness consolidation should happen first.
