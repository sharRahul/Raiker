# Threat Model - Reminder Runtime (Tier 6, local-only)

`reminder_runtime` is the first Tier-6 domain promoted to a real executor. It is
promoted precisely because a reminder is **purely local state** — creating or
listing rows in the workspace `reminders` table — with no network, no external
notification, and no device/hardware access. Every other Tier-6 domain (email,
calendar, finance, investment, medical, pregnancy/baby, cctv, home security,
hardware) still requires a real external integration plus its own threat model
and therefore stays fail-closed (`not_implemented`).

## Boundaries enforced (fail-closed)

- Gate defaults disabled. Enabling requires a HUMAN `runtime_gate_manager`,
  `local_single_user_runtime`, a `threat_model_acks` row for this document, and a
  confirmation token. AI-proposed actions are further governed by the capability
  decision mode (default `ask`).
- Supported `action` values are `create` (default) and `list`; anything else
  fails closed with `unknown_action:<op>`.
- `create` requires a non-empty `title` (`missing_argument:title`), caps title at
  500 chars and notes at 4000, and validates `due_at`/`notes` types. It writes a
  single row to the local `reminders` table with status `active`.
- **No external side effects.** The executor never sends an email/SMS/push, never
  opens the network, and never schedules an OS-level alarm — it only records
  local state. The summary explicitly says no external notification was sent.
- **Metadata-only artifacts.** Runtime artifacts contain ids/counts/flags only
  (`reminder_id`, `status`, `has_due_at`, `count`, `reminder_ids`,
  `content_redacted=true`) — reminder titles and notes are never emitted into
  runtime events.

## Explicit non-goals

- No outbound notification/delivery of any kind (that would be channel/runtime
  work with its own egress allowlist and threat model).
- No OS scheduler / alarm / cron registration (see `scheduled_routines`).
- No calendar, email, or device integration (those Tier-6 domains stay
  fail-closed).
- No editing or deletion of reminders in this slice (create + list only).

## Acceptance evidence

- `tests/test_phase_6_reminder_runtime.py` proves disabled-gate blocking,
  threat-model-ack activation, create-writes-a-row, missing-title fail-closed,
  unknown-action fail-closed, list-returns-count, and that titles/notes never
  appear in runtime event payloads.
- `tests/test_executor_default_registry.py` proves `reminder_runtime` is present
  in `REAL_EXECUTOR_CAPABILITIES` while the other Tier-6 domains are not.
