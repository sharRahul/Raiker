# Raiker-informed web experience - Phase 2 evidence

> **Verification date:** 2026-07-23
> **Decision:** Phase 2 (the daily work loop) is complete.

## Delivered flow

- Workbench summaries, the persistent Chat host, task cadence choices, session
  organization/bulk actions, and approval previews remain server-backed.
- Session detail now has direct, non-secret hash links to Chat, session-scoped
  Tasks, session-scoped Approvals, Audit log, and Checkpoints. A `session` hash
  parameter opens the named session detail rather than creating client state.
- Tasks accepts the route session scope as an API query. Approvals applies the
  same route scope only to the already owner-scoped approval response.
- The approval view receives the server-supplied `critical` fact. A critical
  decision is never sent to the normal resolution route: the UI requests a
  short-lived elevated API session using a password or MFA code, calls the
  dedicated critical resolver, and restores the ordinary in-memory token in all
  outcomes. The server independently requires the elevated scope and delegates
  the decision to `RuntimeAuthority.resolve_critical_approval`.

## Automated evidence

- `SessionsView.test.ts` covers the five session detail links and opening a
  session from a session deep link.
- `TasksView.test.ts` covers session-scoped task loading.
- `ApprovalsView.test.ts` covers session scoping/back-linking and a critical
  denial after server-backed step-up.
- `tests/test_api_approvals.py` proves a normal control session cannot resolve a
  critical approval, while an elevated session reaches the critical lifecycle.
- `tests/test_api_contract_schemas.py` guards the `critical` approval-view
  contract.
- The full web suite passed (219 tests, 1 skipped); the filtered Python suite
  passed (2,086 tests, 2 skipped). The unfiltered Windows run also exposed two
  pre-existing POSIX-only test assumptions (`sh` and `echo` executables), which
  are outside this Phase 2 change and remain covered by the Linux CI gate.

## Local browser E2E evidence

Against a production web build and a disposable loopback workspace, a real
browser created an owner account, opened a seeded session, and verified the
session detail links to Chat, Tasks, Approvals, Audit log, and Checkpoints. The
session-scoped Approvals route showed the matching critical proposal and its
redacted file-change preview. The browser required a decision note plus password
or MFA code before enabling the critical decision. A safe **deny** used fresh
elevation and produced the server-backed `Critical action was denied.` result.
The same step-up dialog supports an explicitly labelled critical approval path;
execution remains determined solely by the server's critical lifecycle.

The final browser console had zero errors and zero warnings. Browser snapshots,
logs, the temporary workspace, and the production build are verification-only
artifacts under ignored paths and are removed before commit.
