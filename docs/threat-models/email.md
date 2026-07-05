# Threat Model - Email Runtime (Tier 6, local-only drafts)

`email_runtime` is a real executor **only** for local email drafts: creating or
listing rows in the workspace `email_drafts` table. It **never sends**.

## Boundaries enforced (fail-closed)

- Gate defaults disabled; enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and a
  confirmation token. AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- Actions: `draft` (default) and `list`. A `send` action is explicitly refused
  with `send_not_supported:local_draft_only`; anything else → `unknown_action:<op>`.
- `draft` requires a non-empty `subject`; `recipients`/`body` are optional
  strings (body capped at 20000 chars). It writes one row with status `draft`.
- **No delivery.** Sending an email is an outbound-network action that requires a
  connector, an owner egress allowlist, and its own threat model — it stays
  out of scope and fail-closed here. No SMTP/API call is ever made.
- Artifacts are metadata only (`draft_id`, `status`, `has_recipients`, `count`,
  `draft_ids`, `content_redacted=true`); subject/recipients/body never enter
  runtime events.

## Explicit non-goals

- No email delivery of any kind (SMTP, provider API, or otherwise).
- No inbox reading, no external mailbox integration.
- No edit/delete in this slice (draft + list only).

## Acceptance evidence

`tests/test_phase_6_calendar_email_runtime.py`: real-executor registration,
local-draft-with-no-content-leak, `send` refusal, and missing-subject
fail-closed.
