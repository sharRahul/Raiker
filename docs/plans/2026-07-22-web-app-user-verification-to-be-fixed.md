# Raiker web app — To be fixed

Issues found while following the user guide against the current locally built
dashboard on 2026-07-22. The run used a disposable workspace, so no real API
key or user data was stored.

## TASK-01 — Instructions are required, but the task form allows an empty submission

> **Resolved 2026-07-23.** The task form now marks Instructions as required,
> presents an inline error for empty or whitespace-only input, and prevents a
> request until it contains text. The server contract remains authoritative.
> Covered by `TasksView.test.ts` (whitespace instructions issue no `POST`).

- **Severity:** Medium — blocks the most basic task-creation flow with an
  unhelpful error.
- **Evidence:** [screenshot](../guide/screenshots/not-working/2026-07-22-task-title-only-422.png)
- **Reproduction:** Open **Tasks**; choose **Task**; enter a title; leave
  **Instructions** empty; click **Create task**.
- **Actual:** The button is enabled, then the UI displays `Could not save task
  (422).`.
- **Expected:** Either disable the submit button until instructions contain
  text and mark the field required, or permit an empty objective consistently
  through the API and task contract.
- **Root cause:** `TaskCreateRequest.description` defaults to an empty string
  and the Svelte form only checks `title`, but `TaskRecord.__post_init__`
  enforces a non-empty `objective` using `_require`.
- **Minimal fix:** Make the frontend require a non-whitespace Instructions
  value, add a clear required marker and inline validation, and cover the
  title-only form state in `TasksView.test.ts`. Keep the backend contract as the
  source of truth.

## Verification refresh — 2026-07-26

The resolved task form was driven again against a disposable, live `raiker-web`
workspace. A task with instructions was created, the four work-kind controls
were selected, and both labelled task dropdowns were exercised. The current
capture is [the task-controls screenshot](../guide/screenshots/working/33-live-task-controls.png).

The same run found and fixed a separate control-contract mismatch in Chat:
**Never plan** had sent `never`, while the governed prompt contract accepts
`never_safe_only`. The selector now sends the valid safe-only mode; a live
Anthropic conversation completed with that mode selected.
