# Credential lifecycle and bounded security monitoring

## Scope

Control Deck Task 5 monitors credential age, verified replacement, configured
workspace files, an explicitly opted-in breach range check, and vault health.
It is not a universal host-security scanner.

## Assets and boundaries

Raw connector credentials remain encrypted in `connector_credentials`; lifecycle
rows retain provider and timestamps only. A browser password is transient to one
breach request. A local scan accepts no browser path: its roots come from the
owner-configured, workspace-relative `RAIKER_SECURITY_SCAN_PATHS`. HIBP egress
requires both the UI/API opt-in and `RAIKER_SECURITY_BREACH_EGRESS_ALLOWLIST`
containing `api.pwnedpasswords.com`.

## Controls

- Lifecycle is owner-scoped; status is derived at 75 and 90 days. Replacement
  cannot be marked verified without encrypted credential metadata.
- Local detection uses the existing sensitivity classifier and stores only the
  configured relative path and sensitivity label. It never stores content or a
  line number.
- Breach comparison sends only a five-character SHA-1 prefix. The password,
  suffix, full hash, response body, and match corpus do not persist.
- Health/local/breach state changes create a redacted `security_findings` row and
  one `security_alert`; repeated open observations deduplicate. A clear state
  resolves the finding and produces one `security_recovered` notification.
- All dashboard routes authenticate the owner and return redacted DTOs.

## Residual risk and follow-up

Task 5 only sees configured paths and explicitly invoked checks. It cannot prove
the absence of secrets or compromise elsewhere. Add bounded detectors by source:
dependency/OS advisories, auth/session anomalies, audit-policy violations,
configuration drift, secret exposure, runtime egress, and integrity checks.
Each must have a redacted finding, deduplicated notification, remediation, and
tests for alert, recovery, isolation, and redaction.
