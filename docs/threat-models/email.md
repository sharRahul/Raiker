# Threat Model - Email Runtime (Tier 6, local drafts + human-gated send queue)

`email_runtime` is a real executor for local email drafts: creating, listing,
and **queuing** rows in the workspace `email_drafts` table. It **never transmits
email itself** — there is no SMTP/provider call. "Sending" is a human decision:
Raiker can only mark a draft ready and ask a human to send it.

## Boundaries enforced (fail-closed)

- Gate defaults disabled; enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and a
  confirmation token. AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- Actions: `draft` (default), `list`, and `send`; anything else →
  `unknown_action:<op>`.
- `draft` requires a non-empty `subject`; `recipients`/`body` are optional
  strings (body capped at 20000 chars). It writes one row with status `draft`.
- `send` does **not** deliver. It takes a `draft_id`
  (`missing_argument:draft_id`, `draft_not_found`, `already_queued`) and flips
  that draft's status to `queued_for_send` — a local marker meaning "a human may
  now send this". Because the capability defaults to the `ask` decision mode, an
  AI-proposed `send` first produces a human-approval request; the human then
  decides, and the human performs the actual transmission (from their own mail
  client, or via a future governed connector). The executor's summary states
  plainly that nothing was transmitted.
- **No delivery from Raiker.** Actual outbound send is an network action that
  requires a connector, an owner egress allowlist, and its own threat model — it
  stays out of scope and fail-closed. No SMTP/API call is ever made here.
- Artifacts are metadata only (`draft_id`, `status`, `transmitted=false`,
  `has_recipients`, `count`, `draft_ids`, `content_redacted=true`);
  subject/recipients/body never enter runtime events.

## Explicit non-goals

- No email transmission of any kind from Raiker (SMTP, provider API, or
  otherwise) — `send` only queues for a human.
- No inbox reading, no external mailbox integration.
- No edit/delete in this slice (draft + list + queue-send only).

## Acceptance evidence

`tests/test_phase_6_calendar_email_runtime.py`: real-executor registration,
local-draft-with-no-content-leak, `send` queues a draft `queued_for_send` with
`transmitted=false` (nothing transmitted), `send` requires a valid `draft_id`,
and missing-subject fail-closed.
