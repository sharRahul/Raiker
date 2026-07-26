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

A persisted principal is resolved for each authenticated request. The durable
`runtime_mode_state` and `capability_gate_state` records are the source of
runtime-control state. `/runtime-readiness` reports blockers and available
governance controls.

Requests that propose a mutation are subject to policy, decision mode, and
approval requirements. Approval resolution remains metadata-only unless a
supported action enters its separately governed execution path.

See [contracts](CONTRACTS.md) and [commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md).
