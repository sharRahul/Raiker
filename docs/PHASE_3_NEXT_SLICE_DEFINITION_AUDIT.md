# Phase 3 Next Slice Definition Audit

Status: `planning_only`

This audit is the next safe action after the post-merge Phase 3 Slice I stabilization pass. It does not define or implement a new slice. It only identifies candidate Phase 3 capability areas that maintainers may use to name and scope the next slice.

## Findings

- Phase 3 remains incomplete.
- Phase 4 must not start as a substitute for completing Phase 3 scope.
- No named `Slice J` definition was found in the repository documentation during this audit.
- Maintainers should define the next named Phase 3 slice before any implementation begins.
- Any next slice must preserve the disabled-runtime boundaries listed below until its own policy, storage, events, lifecycle, approval, rollback, documentation, and acceptance tests explicitly authorize a narrow change.

## Candidate next capabilities

| Candidate area | Existing source signals | Why it may be next | Required maintainer decision before implementation | Boundary to preserve |
| --- | --- | --- | --- | --- |
| Durable approval-preview persistence governance | Phase 3 docs describe approval previews while README states durable approval-preview persistence remains disabled. | Slice E/F/G/H/I built preview, rollback, storage-lifecycle, retention, and evidence surfaces; persistence may need a named governance slice before runtime activation. | Decide whether the next named slice is only metadata/persistence planning or a tightly scoped durable persistence implementation. | No approval-preview execution and no runtime approval relay. |
| Graph/codemap indexing activation readiness | Graph/codemap docs and CLI expose dry-run planning while runtime indexing and graph writes remain disabled. | A future slice may need readiness evidence, approval gates, and rollback criteria before any indexer can run. | Decide whether to define a readiness-only slice, not an indexing implementation. | No graph/codemap indexing jobs, graph writes, schedulers, daemons, or watchers. |
| Semantic memory write readiness | Semantic memory review queue exists while semantic/vector writes, embeddings, and vector records remain disabled. | A future slice may need governance, redaction, retention, and rollback evidence before durable writes. | Decide whether to define a readiness-only slice before any semantic/vector write path. | No semantic memory writes, vector writes, embeddings, or embedding storage. |
| Plugin component/server startup readiness | Plugin manifest planning exists while plugin execution, MCP/LSP/plugin server startup, monitors, and marketplace behavior remain disabled. | Plugin docs mention planned components that require trust and approval gates before startup. | Decide whether to define a planning/audit slice for component startup prerequisites. | No plugin execution, MCP server startup, LSP server startup, monitor daemons, marketplace installs, or hosted routines. |
| Workspace/client parity gap audit | Workspace inspection/view docs require equal-interface parity and preview-safe read-only surfaces. | A planning slice may identify parity gaps across terminal, desktop, web, dashboard, IDE, and mobile docs without building clients. | Decide whether parity auditing is the next slice and which surfaces are in scope. | No external channels, push notifications, share links, or client transport activation. |
| Storage lifecycle next-step governance | Slices G/H/I added metadata lifecycle, retention, cleanup previews, handoff planning, evidence bundles, and simulations. | A future slice may need acceptance criteria for moving from evidence to readiness without executing cleanup. | Decide whether lifecycle governance needs another metadata-only slice. | No cleanup execution, rollback execution, workers, runtime jobs, queues, or schedulers. |

## Explicit non-goals

This audit must not be used as permission to implement:

- cleanup execution;
- graph/codemap indexing;
- graph writes;
- semantic memory writes;
- vector writes;
- embedding creation or embedding storage;
- rollback execution;
- plugin execution;
- MCP, LSP, or plugin server startup;
- monitor daemons;
- external channels;
- approval relay;
- subagents or teams;
- remote execution;
- container execution;
- cloud execution;
- hosted routines;
- marketplace installs;
- push notifications;
- share links.

## Recommended maintainer action

Maintainers should open a planning issue or PR that names the next Phase 3 slice and states:

1. the exact capability being advanced;
2. whether it is planning-only, metadata-only, preview-only, or implementation-scoped;
3. the source documents that authorize the scope;
4. the disabled runtime boundaries that remain unchanged;
5. the acceptance tests required before merge;
6. a clear statement that Phase 3 remains incomplete and Phase 4 must not start.
