# Events & Audit

> Core Concepts › Events & Audit. Back to [Core Concepts](core-concepts.md).

Every proposal, policy decision, approval, activation, decision-mode change, and
execution appends an immutable record to the event log. The log is the system of
record — capability enablement and every governed action are reconstructable from
it.

**Runtime artifacts are metadata-only** (ids, counts, status) — never raw tool
output or sensitive content — so the audit trail is safe to retain and never
leaks what it governs. Provider keys and allowlist values are never displayed.
