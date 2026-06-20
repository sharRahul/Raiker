# Phase 3 Slice B — Approval Planning Preview Spec

Status: implemented_verified

## Purpose

Create metadata-only approval planning previews from saved proposal lifecycle records.
This is a preview/planning feature only. It does not execute approvals, execute proposals,
apply fixes, modify files, run tests, or call shell/process/network.

## Commands

- `/proposal <proposal_id> --approval-preview`
- `/proposal <proposal_id> --approval-preview --json`
- `/approval-previews [--json]`
- `/approval-previews --status <preview_created|needs_human_review|blocked|ready_for_planning|superseded>`
- `/approval-previews --limit <number>`
- `/approval-preview <preview_id> [--json]`

## Data model

`ProposalApprovalPreview` dataclass in `raiker/review/models.py`:

- preview_id (apv_ prefix)
- proposal_id (rap_ prefix)
- review_id
- finding_id
- proposal_status
- action_type
- risk_level
- requires_approval
- would_modify_files
- files (metadata only)
- required_human_decision
- required_safety_checks
- blocking_conditions
- recommended_next_action
- status (preview statuses only)
- created_at
- source

## Preview statuses

- `preview_created`: preview was generated from a saved proposal lifecycle record
- `needs_human_review`: human must inspect the proposal and safety checklist
- `blocked`: preview cannot proceed due to blocking conditions
- `ready_for_planning`: safe to consider in planning (not execution approval)
- `superseded`: replaced by a newer preview or proposal

Execution-approval statuses (`approved`, `approved_for_execution`, `ready_to_apply`,
`ready_to_execute`, `execute`, `executed`, `applied`, `merged`) are explicitly rejected.

## Persistence

- Table: `proposal_approval_previews` in local SQLite
- Indexes: proposal_id, status, created_at
- Preview ID is stable: `apv_<proposal_id_without_rap_ prefix>`
- Re-generating updates the existing preview (upsert by preview_id)

## Events

- `proposal_approval_preview_created`: metadata-only payload
- `proposal_approval_preview_listed`: status filter, limit, result count
- `proposal_approval_preview_viewed`: preview_id, status

Event payloads never contain raw diff, file contents, secrets, reasoning, patch content,
or executable commands.

## Safety

- preview-only
- no approval execution
- no proposal execution
- no auto-fix
- no patch application
- no file mutation
- no staging/unstaging
- no test execution
- no GitHub PR automation
- no UI/API/IDE/dashboard/mobile
- no shell/process/network
- no Phase 4
- disabled runtime flags remain false

## Source files

- `raiker/review/models.py` - ProposalApprovalPreview model
- `raiker/review/approval_preview.py` - preview generation and store
- `raiker/review/__init__.py` - exports
- `raiker/cli/commands.py` - CLI handlers
- `raiker/storage/migrations.py` - table migration SQL
- `raiker/storage/sqlite.py` - migration application
- `raiker/contracts/models.py` - event type additions
- `raiker/contracts/ids.py` - apv_ prefix

## Tests

- `tests/test_phase_3_slice_b_approval_preview_models.py`
- `tests/test_phase_3_slice_b_approval_preview_storage.py`
- `tests/test_phase_3_slice_b_approval_preview_cli.py`
- `tests/test_phase_3_slice_b_approval_preview_safety.py`
- `tests/test_phase_3_slice_b_docs_truthfulness.py`

## Validation

### Phase 3 Slice B final validation (2026-06-19)

| Check | Result |
|---|---|
| ruff | All checks passed |
| mypy | Success, 209 source files |
| pytest | 477+ passed, 2 skipped |
| validate_phase_status.py | passed |
| validate_repo_truthfulness.py | passed |
