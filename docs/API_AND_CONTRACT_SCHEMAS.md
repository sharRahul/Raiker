# API and contract schemas

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

`raiker-web` is a local loopback API. It is a client of the same governed
backend as the terminal; it adds no direct tool authority.

## Core API areas

| Area | Purpose |
|---|---|
| Authentication | Creates a local, in-memory session token for a human principal |
| Prompts and turns | Submits a governed turn and returns safe response metadata |
| Models | Lists profiles and exposes governed selection/readiness |
| Runtime control | Reads or changes runtime mode and capability gates through RuntimeAuthority |
| Audit views | Reads sessions, events, checkpoints, approvals, and diagnostics |
| Code repositories | Lists, connects, selects, and forgets the repository *references* the Build workspace points a coding chat at |

### Code repositories

`GET/POST /api/code/repos`, `PUT /api/code/repos/selection`, and
`DELETE /api/code/repos/{repo_id}` manage account-scoped repository references
for the Build workspace. A reference stores no credential and grants no
capability:

- `kind: "local"` requires a `path` that resolves inside the workspace. Anything
  resolving outside it, or that is absent or not a directory, is refused
  (`repo_outside_workspace`, `repo_not_found`, `repo_not_a_directory`) — the same
  containment check every other workspace path read uses.
- `kind: "github"` records an `owner`/`repo` coordinate and optional `branch`
  after strict local validation. The route performs **no network call**. Content
  reaches a turn only through the brokered `github_read` tool, which stays
  subject to the `connector_github_runtime` capability gate and its decision
  mode; a disabled gate fails closed regardless of what is connected here. The
  listing reports `github_gate_state`, `github_decision_mode`, and
  `github_token_configured` so a client can state that posture rather than imply
  access.

Connecting and disconnecting append `code_repo_connected` /
`code_repo_disconnected` audit events. Every route is account-scoped: one
account cannot read, select, or delete another's references.

`POST /api/tasks` accepts a `recurrence` of `background`, `continuous`,
`hourly`, `daily`, or `weekly`. An unrecognised cadence is refused with
`invalid_recurrence:<value>` rather than stored as a one-shot. Recurring
schedules re-arm after each governed cycle; each cycle is one discrete governed
turn, so policy, gates, and approvals apply to every one of them.

`POST /api/tasks/{task_id}/resume` continues one parked scheduled run whose
approval has been granted. It is the owner's retry for the host's own automatic
pass, runs the same governed path, and is owner-scoped: another account's task
answers `task_not_found`, as does a missing one. Exactly-once resumption remains
the store's atomic `suspended → resuming` claim, so this can never replay a turn
that already ran.

`GET /api/sessions/{session_id}/attachments/{attachment_id}/download` returns
the bytes of one authorised file for saving. Authorisation is the same stored
session/attachment/owner reference the preview routes use, so a download can
never reach a file the same person could not already open. The response is
always `application/octet-stream` with an attachment disposition, `nosniff` and
`no-store`, and the filename is rebuilt from the stored name rather than echoed.
Every download appends `attachment_downloaded` carrying metadata only.

`GET /api/memory/{memory_id}/source` and
`GET /api/sessions/{session_id}/attachments/{attachment_id}/provenance` resolve
stored source coordinates into a bounded plain-text excerpt plus the offsets of
the passage inside it. `status` is the contract: only `resolved` carries a
located passage; `no_provenance`, `source_deleted`, `source_changed`,
`unsupported_source` and `not_authorized` are each a stated answer rather than
an error. Authorisation is re-checked against the caller at read time — owning a
memory is not owning its source — and `not_authorized` reveals nothing about
whether the source exists.

A persisted principal is resolved for each authenticated request. The durable
`runtime_mode_state` (one runtime, `raiker_runtime`, whose `status` is `active`
or `disabled`) and `capability_gate_state` records are the source of
runtime-control state. `/runtime-readiness` reports blockers and available
governance controls.

Requests that propose a mutation are subject to policy, decision mode, and
approval requirements. Approval resolution remains metadata-only unless a
supported action enters its separately governed execution path.

See [contracts](CONTRACTS.md) and [commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md).
