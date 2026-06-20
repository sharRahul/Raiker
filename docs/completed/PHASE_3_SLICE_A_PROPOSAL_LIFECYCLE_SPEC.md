# Phase 3 Slice A — Proposal Lifecycle Foundation Spec

## Status

Phase 3 Slice A proposal lifecycle foundation: `implemented_verified` for local metadata-only
proposal lifecycle tracking of review action proposals.

This slice is the first Phase 3 slice. It does **not** implement Phase 3 runtime execution. It
builds on Phase 2.6 (`/review --propose-fixes` in-memory proposal generation) by adding local
metadata-only persistence and lifecycle tracking for those proposals.

## Scope

This slice is metadata-only; proposal-only; no proposal execution; no auto-fix; no patch
application; no file mutation; no staging/unstaging; no test execution; no GitHub PR automation;
no UI/API/IDE/dashboard/mobile; no approval execution; no Phase 4. `approval_execution_enabled`
remains false. Disabled runtime flags remain false.

## Follow-on

Phase 3 Slice B approval planning preview is now implemented_verified. See
`docs/PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SPEC.md`.

## Commands

```text
/review --propose-fixes --save-proposals
/proposals
/proposals --json
/proposals --status <proposed|acknowledged|deferred|rejected|superseded>
/proposals --limit <number>
/proposal <proposal_id>
/proposal <proposal_id> --json
/proposal <proposal_id> --mark <proposed|acknowledged|deferred|rejected|superseded>
```

### `/review --propose-fixes --save-proposals`

- Runs the existing Phase 2.6 review proposal generation.
- Saves generated proposals as local `ProposalLifecycleRecord` rows (status `proposed`) in the
  local SQLite `proposal_lifecycle_records` table.
- Returns normal review/proposal output and includes `saved_proposal_count` and
  `saved_proposal_ids` in `ReviewResult.event_metadata`.
- Emits a `proposal_lifecycle_created` metadata-only event per saved record.
- If no proposals exist, no records are created.
- Never applies, mutates, stages/unstages, commits, runs tests, or calls network.

### `/proposals`

- Lists saved proposal lifecycle records newest first.
- Default limit is 20; `--limit <number>` adjusts the limit (must be >= 0).
- `--json` returns a parseable JSON array of records.
- `--status <status>` filters by lifecycle status.
- Text output shows proposal id, status, title, finding id, and risk level only.
- No raw diff, file contents, secrets, or private reasoning.

### `/proposal <proposal_id>`

- Shows one proposal lifecycle record.
- `--json` returns a parseable JSON object.
- `--mark <status>` transitions the record's status (metadata only). Emits a
  `proposal_lifecycle_status_changed` event with `previous_status` and `new_status`.
- Unknown proposal ids fail safely with "Proposal not found."
- Invalid statuses fail safely with usage text.
- `--mark` never executes, applies, mutates files, stages/unstages, commits, runs tests, or calls
  network.

## Lifecycle statuses

Allowed statuses:

```text
proposed
acknowledged
deferred
rejected
superseded
```

Status meaning:

```text
proposed: generated and saved for review
acknowledged: user reviewed it as a valid planning item; not executable
deferred: user postponed it
rejected: user rejected it
superseded: replaced by a newer proposal
```

No status implies execution approval. The following are deliberately excluded and must never be
added: `approved`, `approved_for_execution`, `ready_to_apply`, `execute`.

## Model

```python
@dataclass(frozen=True)
class ProposalLifecycleRecord:
    proposal_id: str          # rap_ prefix
    review_id: str
    finding_id: str
    title: str
    action_type: str
    risk_level: str
    requires_approval: bool
    would_modify_files: bool
    status: str
    files: list[str]
    summary: str
    created_at: str
    updated_at: str
    source: str
```

Rules:

- No raw diff.
- No raw file contents.
- No secrets.
- No private reasoning.
- No prompt text.
- No chain-of-thought.
- No raw tool output.
- No patch body.
- Proposal IDs keep `rap_` prefix.

## Persistence

Local SQLite table `proposal_lifecycle_records` (metadata only):

```text
proposal_id, review_id, finding_id, title, action_type, risk_level,
requires_approval, would_modify_files, status, files_json, summary,
created_at, updated_at, source
```

No background workers, schedulers, watchers, daemons, cleanup execution, rollback execution, or
approval execution are added by this slice.

## Events

Metadata-only events:

```text
proposal_lifecycle_created
proposal_lifecycle_status_changed
proposal_lifecycle_listed
proposal_lifecycle_viewed
```

Allowed payload examples:

```json
{
  "proposal_id": "rap_...",
  "review_id": "rev_...",
  "finding_id": "secret-introduced",
  "action_type": "secret_removal_proposal",
  "risk_level": "high",
  "requires_approval": true,
  "would_modify_files": true,
  "status": "proposed"
}
```

```json
{
  "proposal_id": "rap_...",
  "previous_status": "proposed",
  "new_status": "deferred"
}
```

Forbidden event payload content:

```text
raw diff
raw file contents
secrets
prompt text
private reasoning
chain-of-thought
raw tool output
patch content
executable commands
```

## Safety and truthfulness

- metadata-only
- proposal-only
- no proposal execution
- no auto-fix
- no patch application
- no file mutation
- no staging/unstaging
- no test execution
- no GitHub PR automation
- no UI/API/IDE/dashboard/mobile
- no approval execution
- no Phase 4
- disabled runtime flags remain false

This slice does not claim Phase 3 runtime activation. It does not enable any
disabled runtime flag. `approval_execution_enabled` remains false.
