# Personal autonomous-agent target threat model

Status: target design, 2026-10-07; no new capability gate or executor is enabled.
[Architecture](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md) and
[delivery gates](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md) own scope.

## Assets and adversaries

Protect owner identity, credentials, private context, goal/plan integrity,
external accounts/effects, budgets and accurate outcome evidence. Attackers
include malicious webpages/documents, connector responses, spoofed channel
senders, poisoned memory/skills and compromised or faulty workers. Model output
is an untrusted proposal. The owner retains legitimate configuration choices.

## Target controls and required tests

| Threat | Required control | Acceptance evidence |
|---|---|---|
| Stale or broader-than-intended delegation | Versioned scope/expiry/revocation; current policy and capability intersection | PAA-02: expired/revoked/changed envelope refuses before effect |
| Goal or personal-memory poisoning | Provenance, candidate review, confidence/freshness, correction/purge | PAA-03: untrusted instruction cannot become authority; derived data disappears after purge |
| Trigger spoof, replay or cost amplification | Authenticated source, freshness, deduplication, cooldown and aggregate reservations | PAA-04: invalid/duplicate event starts no additional work; polling budget holds |
| Browser prompt injection or private-network reach | Isolated session, typed effect classification, shared egress guarantees | PAA-06: injection, redirects and private addresses tested at every hop |
| Wrong-account or wrong-recipient effect | Account/destination bound action, concrete approval preview, execution-time checks | PAA-05: changed account/recipient invalidates the proposal |
| Credential theft in context, screenshots or output | Vault references, secret-safe sign-in handoff, bounded redaction | PAA-05/06: no raw secret in model payload, logs, receipts or artifact |
| Duplicate effect after timeout or restart | Intent journal, provider idempotency/status reconciliation; unknown parks | PAA-08: provider commits before timeout; retry does not resend |
| Parent success while children remain open | Durable dependency states and independent criterion validation | PAA-02/08: unresolved/failed child blocks full completion |
| Stop race or worker duplication | Atomic leases, durable cancellation, no new claims after Stop | PAA-02/10: race, restart and descendant-stop traces |
| Learned workflow grants itself authority | Proposed versioned skill, reviewed permission diff, owner activation/revoke | PAA-09: poisoned/new-permission skill cannot self-activate |
| Misleading availability or receipt | Host/model/service readiness, confirmed vs unknown vs partial evidence | PAA-07/11: offline/unsupported flow cannot show completion |

These controls are requirements to implement and verify, not a claim that every
target threat is already mitigated. Existing gateway, identity and authority
controls remain mandatory on new entry paths.

## Residual risks and operating limits

External services may lack idempotency, cancellation or reliable status. Leave
ambiguous effects unknown for owner review. Safe-boundary Stop cannot reverse
already committed external actions. Model judgements can be wrong; artifact and
provider checks must independently validate consequential claims. Local work
requires an awake host. An always-on remote profile increases exposure and needs
its own explicit configuration, authentication and tests. Audit logs remain
local records and are not claimed to be tamper-proof.
