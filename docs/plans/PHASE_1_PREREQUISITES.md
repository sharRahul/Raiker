# Raiker-informed web experience — Phase 1 prerequisites

> **Audit date:** 2026-07-23
> **Decision:** Phase 0 is complete. These prerequisites enabled Phase 1; Phase
> 1 completion evidence now lives in `RAIKER_PHASE_1_EVIDENCE.md`.

## Contract boundaries

The browser is a local presentation client. It consumes typed DTOs through
`apps/web/src/lib/api.ts` and `apiTypes.ts`; it does not store credentials,
decide risk, or represent a mutation as completed until the API response confirms
it. The allowed fragment path is one `NAV_ITEMS` route. `routeStateFromHash`
parses only the non-secret keys `project`, `session`, `record`, `filter`, and
`tab`; unknown keys are ignored and empty/oversized values are dropped. The
current shell consumes `session` for `new-chat`, `activity`, and `checkpoints`;
the other parsed keys are reserved for route consumers and grant no authority.

### UI event contract

| Event | Producer → consumer | Required result |
|---|---|---|
| `hashchange` | browser navigation → `App.svelte` | Restores the allowed route and session selection; focus moves to `main`. |
| `raiker:chats-changed` | Chat/Projects/Sidebar → Sidebar | Refreshes the recent-session list without carrying prompt content. |

Events are UI semantics, not a client-side audit log. Authoritative audit events
remain server-owned and are viewed through Activity.

## Route and surface inventory

| Destination | Current route | Read model / governed mutations | Intentional state coverage |
|---|---|---|---|
| Workbench | `home` | sessions, tasks, pending approvals | loading, empty sessions, recoverable error |
| Chat / search / sessions | `new-chat`, `search-chat`, `sessions` | prompt stream; session organization/deletion | loading, empty, API error |
| Tasks / projects | `tasks`, `projects` | task create/stop; project selection | loading, empty, API error |
| Knowledge | `memory`, `brain`, `checkpoints` | memory controls; checkpoint operations | loading, empty, API error |
| Control | `approvals`, `capabilities`, `models`, `connections`, `mcp` | approval, gate, model, connector, MCP governed endpoints | loading, empty, denied/error where supplied |
| Observe / utilities | `activity`, `diagnostics`, `work`, `settings` | read models and settings mutations | loading, empty, API error |

The complete call and mutation inventory is intentionally maintained beside the
typed client in `apps/web/src/lib/api.ts`; component tests fail loudly for an
unrouted fetch via `stubFetch`. This avoids a second hand-maintained endpoint
list drifting from the contract.

## Representative journey baseline

The following journeys are the release baseline and were recorded on 2026-07-23
in `Raiker_PHASE_0_EVIDENCE.md`. They must be re-run after Phase 1. They are not
population usability-study measurements; Phase 1 still needs its supported
viewport, keyboard, and visual-regression evidence.

1. Unlock, select/create project context, submit the first prompt, and observe a
   completed, denied, approval-required, or truthful unavailable server result.
2. Resume a session, search it, alter its project/filter selection, and use
   browser back/forward.
3. Review a normal approval, including denial, and inspect the required critical
   step-up before any mutation is committed.
4. Select a hosted model and confirm egress acknowledgement/fallback facts.
5. Inspect a connector or MCP failure and follow its server-provided remediation.

## Missing read-only models and Phase 1 blockers

No new read-only endpoint is a prerequisite for shell/navigation work. The
following are required before their respective later Phase 2–4 experiences can
be claimed: session-detail cross-link aggregate, project work/file provenance
summary, extension lifecycle/readiness aggregate, observability correlation
aggregate, and support-bundle export contract.

## Threat-model review

Phase 1 does not add authority or network access. Route state contains no secret
material; the API remains the authority for project selection, runtime status,
approvals, stop, models, extensions, and every mutation. Any future deep link
must use the allowlisted selection schema above and must not contain tokens,
arguments, policy decisions, or secret references.
