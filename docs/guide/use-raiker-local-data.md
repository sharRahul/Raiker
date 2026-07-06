# Reminders, Calendar & Email

> Use Raiker › Local Data. Back to [Use Raiker](use-raiker.md).

The local Tier-6 executors let the agent keep personal data locally with **no
external side effects**:

- **`reminder_runtime`** — `create` / `list` reminders. No notification is sent.
- **`calendar_runtime`** — `create` / `list` local calendar events. No external
  sync, no invites.
- **`email_runtime`** — `draft` / `list` locally, and `send` **queues** a draft
  for a human to send (Raiker never transmits; in the default `ask` mode it asks
  you first). A `send` marks the draft `queued_for_send` and reports
  `transmitted=false`.

All three keep titles, notes, subjects, recipients, and bodies out of runtime
events (metadata-only artifacts).
