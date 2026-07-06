# Threat Model - Calendar Runtime (Tier 6, local-only)

`calendar_runtime` is a real executor **only** for a local calendar: creating or
listing rows in the workspace `calendar_events` table. It is promoted alongside
`reminder_runtime` because local calendar state has no network, no external
calendar sync, no invites, and no notifications.

## Boundaries enforced (fail-closed)

- Gate defaults disabled; enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and a
  confirmation token. AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- Actions: `create` (default) and `list`. Anything else → `unknown_action:<op>`.
- `create` requires a non-empty `title`; `starts_at`/`ends_at`/`location`/`notes`
  are optional strings. It writes one row with status `scheduled`.
- **No external side effects:** no Google/Microsoft/CalDAV sync, no invite
  emails, no notifications, no OS calendar/alarm registration. The summary says
  so explicitly.
- Artifacts are metadata only (`event_id`, `status`, `has_start`, `count`,
  `event_ids`, `content_redacted=true`); titles/locations/notes never enter
  runtime events.

## Explicit non-goals

- No external calendar integration or two-way sync (needs a connector + egress
  allowlist + its own threat model).
- No invites, reminders delivery, or notifications.
- No edit/delete in this slice (create + list only).

## Acceptance evidence

`tests/test_phase_6_calendar_email_runtime.py`: real-executor registration,
gate-disabled blocking, create-writes-a-row with no content leak, and
missing-title / unknown-action fail-closed.
