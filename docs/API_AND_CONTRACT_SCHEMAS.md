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

### Prompt input provenance

`POST /api/prompts`, `/api/prompts/stream`, and `/api/prompts/background` accept
optional `input_mode: "typed" | "dictated" | "mixed"`, defaulting to `typed`
for existing clients. The value is revalidated when the HTTP request becomes a
`PromptEnvelope` and again at the Agent Gateway, so an internal or external
client cannot invent another provenance class. It is metadata only: Raiker does
not accept or retain microphone audio and does not store a second transcript.
Voice-created prompts use the same authenticated prompt route, session scope,
policy, model selection, approval and audit path as keyboard-created prompts.

### Composer surface

The same three routes accept optional `surface: "chat" | "build"`, defaulting to
`chat` so a REST client that has never heard of the field gets the conservative
surface rather than the coding one. Like `input_mode` it is revalidated when the
request becomes a `PromptEnvelope` and again at the Agent Gateway, which records
it on `prompt_received`; an unrecognised value is refused as
`invalid_prompt_surface` rather than coerced.

It selects **the operating protocol the turn runs under and nothing else**: a
Build turn receives the protocol in `docs/RAIKER_BUILD_PROCESS.md` as a second
system message, a Chat turn does not, and every field that decides authority —
capability modes, approval mode, planning mode, tool-call budget, and the tool
set offered to the model — is identical on both.

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

## Knowledge Map source API

The graph's sources are addressed **within a named root**, as
`<root_id>/<relative path>`. There is no path meaning "the workspace", which is
what stops a request asking for one (FIXED-152).

`GET /api/brain/sources/roots` — the boundary for this owner: each project's
files, `generated-files`, `approved-memory`, the non-browsable
`raiker-database` root (which states that Chat, Build, Tasks, Schedules and
uploads are already in the graph), and every folder this owner granted. A
granted root reports its absolute path so the owner can recognise it; Raiker's
own roots are described, not disclosed.

`GET /api/brain/sources/browse?path=` — an **empty** path answers with the roots
and no children. A non-empty path lists inside one root. Resolution happens
before containment, so a `..` segment or a symlink cannot leave the root it
claims to be in; anything outside is `brain_source_outside_scope`, and the
database root is `brain_source_root_not_browsable`.

`POST /api/brain/sources/grants` takes an **absolute** directory path and
records the owner granting it. The folder is read where it is — granting copies
nothing. `brain_grant_requires_absolute_path`, `brain_grant_not_found`,
`brain_grant_not_a_directory` and `brain_grant_is_runtime_directory` are the
refusals. `DELETE /api/brain/sources/grants?root_id=` revokes it **and** removes
every source recorded under it, because leaving them would keep reading a folder
the owner just closed.

`POST /api/brain/sources/upload` takes `{filename, content_base64, store_copy}`.
It duplicates the file into the workspace, so `store_copy` has no default: a
request without an explicit `true` is `brain_upload_copy_not_authorised` and
nothing is written. Copies land in `.raiker/artifacts/knowledge-uploads/` under
a name that never overwrites an existing one, capped at 5 MB
(`brain_upload_too_large`) and limited to the text and source extensions the
indexer reads (`brain_upload_unsupported_file_type`).

`POST /api/brain/sources/review` returns the bounded indexing plan for a scoped
path before it is added, and `POST|DELETE /api/brain/sources` add and remove
one.

`GET /api/health` is the only unauthenticated read. It reports liveness **and**
whether the encrypted store opens: `status` is `ok` only when both hold, and
`store`, `reason`, `detail`, `cipher_memory_security` and
`memory_security_reason` say which is which. It answers `200` either way — the
server is answering; it is the store that may be degraded — and a request that
cannot open the store answers `503` with `store_memory_lock_unavailable`
(FIXED-150).

A persisted principal is resolved for each authenticated request. The durable
`runtime_mode_state` (one runtime, `raiker_runtime`, whose `status` is `active`
or `disabled`) and `capability_gate_state` records are the source of
runtime-control state. `/runtime-readiness` reports blockers and available
governance controls.

Requests that propose a mutation are subject to policy, decision mode, and
approval requirements. Approval resolution remains metadata-only unless the
action's capability is one of the twelve in `EXECUTABLE_ON_APPROVAL`
(`raiker/approvals/execution.py`), in which case the separately governed relay
revalidates and executes it once. The API tells a client which of the two an
approval is **before** the decision, not after, so a surface never offers a
button whose effect it cannot describe.

See [contracts](CONTRACTS.md) and [commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md).


## Model readiness and acquisition API

`GET /api/model-readiness` returns persisted, expiring exact-model evidence;
`POST /api/model-readiness/check` performs the owner-triggered check. A
readiness record is one of `not_configured`, `checking`, `ready`,
`runtime_missing`, `runtime_stopped`, `model_missing`, `policy_blocked`,
`authentication_failed`, `quota_exhausted`, `unreachable`, `unsupported`, or
`stale`. `quota_exhausted` is distinct on purpose: the provider is reachable and
the credential is valid, and only credit or a higher quota fixes it. The
submission gate judges the whole resolved chain — the selected model followed by
the owner's fallback sequence — and refuses with `model_not_ready` only when no
entry in it is ready.
`GET/PUT /api/model-setup` records first-run progress. `GET/PUT
/api/surface-models` holds a default model per work surface (`chat`, `build`,
`tasks`, `schedule`); an empty `profile_id` clears one, and the value is a
preference that never grants readiness. `GET /api/hugging-face/trending` returns
the most-downloaded GGUF repositories so the Hub surface opens with somewhere to
start. Model operations expose
preview/list/start/cancel/retry/cleanup records. Local-library roots, rescans and
deployments are under `/api/model-library`; Ollama pulls use `/api/ollama/pull`;
Hugging Face search, immutable variants and confirmed downloads use
`/api/hugging-face`; conversion preview/start uses `/api/model-conversion`.
Credentials and tokens are write-only, paths are redacted in operation views,
and every mutating route requires an authenticated human owner.

### Provider usage and context compaction API

`GET /api/models/weekly-usage` returns connected profiles only. Each row keeps
two sources separate: `observed` is Raiker's rolling-seven-day ledger (token
components, requests, turns, compactions, known cost and unpriced models), while
`native` is a normalized provider report with `status`, numeric metrics, scope,
period and optional limit/remaining values. `refresh_native=true` explicitly
contacts supported providers; ordinary reads use the five-minute owner-scoped
cache. Raw provider responses, account identifiers and credentials are never in
this contract.

`PUT /api/models/{profile_id}/weekly-budget` accepts
`{"token_budget": 500000}`. `null` clears the budget. The profile must be
connected and a non-null value must be a positive integer. This is an advisory
owner control, not provider quota or billing data.

`GET /api/sessions/{session_id}/context-usage` includes
`latest_compaction` when automatic compaction has been attempted. Its bounded
metadata is `status`, `created_at`, `source_turn_count`,
`estimated_input_tokens_before`, `estimated_summary_tokens`, and a safe
`reason_code`. Summary text is never returned by this status route.
