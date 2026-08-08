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

### Machine identity attribution

Agentic turn, event, and approval views use a redacted `IdentityView`:

```text
principal_id, principal_type, display_name, subject, turn_id,
key_id, issued_at, expires_at, state
```

`subject` is the SPIFFE-style public locator, not a bearer credential. Approval
responses additionally expose `proposed_by`, `approved_by`, and
`machine_identity`: the proposer is the verified turn machine, while the
authorizer is the human who resolved the decision. Event views may include the
correlated `machine_identity`. These contracts never return the signed token,
signature, private key, token fingerprint, provider key, or raw credential.

At execution time the internal `ToolExecutionContext` keeps
`acting_principal_id` separate from `owner_principal_id`. The former is the
verified machine actor; the latter is the authenticated account scope used for
resources and credential references. Clients cannot supply or replace either
value through model tool arguments.

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
the passage inside it. `resolution_method` is `stored_coordinates` when the
UTF-8 byte slice and hash verify, `matching_text` for a legacy/fallback match,
or empty when no passage resolved. `status` is the contract: only `resolved` carries a
located passage; `no_provenance`, `source_deleted`, `source_changed`,
`unsupported_source` and `not_authorized` are each a stated answer rather than
an error. Authorisation is re-checked against the caller at read time — owning a
memory is not owning its source — and `not_authorized` reveals nothing about
whether the source exists.

`GET /api/sessions/{session_id}/sources` lists what the turns in one
conversation actually read — one entry per governed read call that returned
material, and per file the owner attached — carrying `source_id` (`s1`, `s2`, …,
the marker the model was handed), `kind`, `title`, `locator`, `tool_name`,
`detail`, `turn_id` and `openable`. It never carries the passage: a history load
must not ship a transcript's worth of read material. Optional `turn_id` narrows
it to one turn. Scoping is the row's own `principal_id`, so another account's
conversation answers an empty list rather than a refusal that would confirm it
exists.

`GET /api/sessions/{session_id}/turns/{turn_id}/sources/{source_id}/excerpt`
opens one of them at the passage that was used, answering in the same shape and
with the same `status` contract as the two provenance routes above.
`resolution_method` adds three values here: `answer_quote` when the optional
`quote` parameter — the answer sentence the citation marker terminated — was
found verbatim in the source and that run is marked; `whole_source` when the
turn read all of it, so marking every character would say nothing; and
`recorded_passage` for material Raiker holds no second copy of (a fetched page,
an email), shown as the exact text that reached the model. `quote` is used for
one thing only, finding an offset, so it can never surface text the source does
not already contain — and a paraphrase that matches nothing yields no highlight
rather than a confident mark in the wrong place.

The skill routes (`GET|POST /api/skills`, `POST /api/skills/verify`,
`POST /api/skills/import`, `POST /api/skills/build`,
`GET /api/skills/{skill_id}/download`, `PUT /api/skills/{skill_id}`,
`PUT /api/skills/{skill_id}/active`, `DELETE /api/skills/{skill_id}`) are
owner-scoped CRUD over validated instruction documents. A skill adds no
capability and executes nothing, so these are not a governed runtime path — but
each carries its own contract:

* **Upload** takes a base64 `SKILL.md` or `*.skill` and validates before storage
  (extension allowlist, 2 MB bundle cap, frontmatter contract, archive-member
  safety). Refusals answer `422` with a stable `reason_code`
  (`skill_missing_description`, `skill_invalid_name`, `skill_unsafe_member_path`,
  `skill_too_large`, …); `400` means the base64 itself was unreadable.
* **Verify** fetches a linked document through the sandbox egress boundary
  against the published-skill host allowlist and reports the document's real
  name, description, checksum, and whether that name is already installed —
  storing nothing. **Import** does the same and stores. An unsupported host is
  `skill_unsupported_source` *before* any request is made; a `.skill` archive URL
  is `skill_archive_url_unsupported`, because that path is deliberately
  text-only.
* **List** returns metadata and the owner's active choice, never the stored
  document or archive. **Download** returns an uploaded archive byte-for-byte,
  or packs a bare document into `<name>.skill` on demand.
* Re-installing under an existing name refreshes that row in place and preserves
  its `skill_id`, its created-at, and the owner's active/inactive choice, so an
  update never silently re-enables a skill the owner turned off.
* A row belonging to another principal answers `404`, the same as a missing one.

Every mutation appends a `skill_*` event carrying metadata only — name, source,
checksum, sizes — never the document text.

A persisted principal is resolved for each authenticated request. The durable
`runtime_mode_state` (one runtime, `raiker_runtime`, whose `status` is `active`
or `disabled`) and `capability_gate_state` records are the source of
runtime-control state. `/runtime-readiness` reports blockers and available
governance controls.

Requests that propose a mutation are subject to policy, decision mode, and
approval requirements. Approval resolution remains metadata-only unless a
supported action enters its separately governed execution path.

See [contracts](CONTRACTS.md) and [commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md).
