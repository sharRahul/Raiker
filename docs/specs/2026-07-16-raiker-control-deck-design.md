# Raiker Control Deck Redesign

## Scope

Rebuild every Raiker web route on one responsive Control Deck visual system while preserving the governed API as the only authority. The redesign covers login, navigation, chat, search, memory, projects, approvals, tasks, brain, work, sessions, models, connections, checkpoints, activity, diagnostics, settings, and capabilities.

It also adds:

- Complete recent-chat actions: local-link share, rename, project move, pin, archive, and delete.
- Session archive and rename persistence with additive database migration.
- Tool-oriented capability controls that render decision selectors only for executable, governed tools.
- Real MCP builder and connector operations routed through the existing authority, decision-mode, egress, and audit paths.
- Provider credential lifecycle management: inventory, 75-day warning, 90-day rotation status, and verified manual replacement for every currently configured provider. The design leaves a provider-automation adapter boundary for a future provider with explicit credential-management authorization.
- Private hybrid credential breach monitoring: local exposure scans plus opt-in k-anonymous HIBP password checks.
- Self-monitoring health checks, failure/breach detection, and in-app notifications.
- A fix for existing accounts that lack the runtime gate-manager role and therefore receive `not_authorized_gate_manager` during local Ollama selection.
- A settings integrity contract: every displayed setting either changes verified runtime/UI behavior, persists with visible save/error state, or is omitted as unavailable.
- One user per local instance: the login action creates a new user in a new isolated Raiker instance rather than adding a second account to the current instance.
- A local password-recovery screen that permits reset only with an enrolled TOTP authenticator or one-time recovery code; accounts without either recovery factor remain fail-closed.

## Non-goals

- No fake remote sharing. Chat sharing copies or invokes native sharing for a loopback-only session URL and never grants another principal access.
- No fabricated MCP, provider rotation, breach, or health status. Unsupported provider lifecycle APIs remain manual and visibly marked as such.
- No raw password, API key, or credential value leaves the device for breach checks. The HIBP integration sends only a SHA-1 range prefix after explicit opt-in.
- No decision control for built-in, read-only, deferred, or non-executable capabilities.

## Architecture

### Web UI

The web application keeps Svelte routes and typed API clients. Shared page primitives, status treatment, responsive layouts, and the login wordmark style become the common Control Deck language. Each data-dependent route provides loading, error, empty, and degraded states.

Settings is rebuilt as an applied-preferences surface rather than a storage form. Theme, spacing, font choice, startup route, notifications, history/retention, attachment limits, trusted contacts, security controls, and account data each require an active consumer and an observable result. Writes are serialized and use optimistic state only until the API confirms them; a rejection restores server truth and reports an inline error. Voice, emergency-access, cache-clearing, cloud, export, and other unsupported controls are removed from the interactive settings flow instead of appearing as inert inputs.

Conversation surfaces share a sidebar action menu and session detail model. The sidebar exposes all six requested actions. Rename and archive call governed session endpoints; pin and project move reuse existing endpoints; share stays local-only; delete remains confirmed and destructive.

Capabilities are grouped by executable tool domain rather than implementation phase. A row gets Ask, Allow, Auto, and Deny only when a real executor exists and the server allows the current principal to change that mode. Built-in and unavailable entries are omitted from the control board.

### Backend

Session lifecycle additions use additive, idempotent SQLite migrations and preserve current sessions. Archive is reversible and excludes sessions from recent-chat navigation by default. The existing role backfill runs during account service initialization/login so legacy human accounts receive their required runtime-gate-manager role before model selection.

MCP builder and connector operations are registered as real executor capabilities. Builder requests create validated local MCP server configurations; connector requests create validated MCP endpoint configurations. Every invocation passes the same capability gate, decision-mode, runtime policy, egress allowlist, and audit-event path as other governed tools. Credentials stay in the encrypted vault and never enter events or responses.

Credential lifecycle records track provider, owner, rotation timestamp, verification status, and due date. Current providers use an owner-driven replacement flow because no provider key-management authorization is configured. A future provider adapter may automate rotation only after explicit credential-management authorization. At 75 days Raiker warns; at 90 days it records an overdue security alert while retaining service until the owner replaces the credential.

Breach monitoring combines local, redacted scans of configured workspace/runtime locations with an opt-in HIBP password range check. Only the first five characters of a SHA-1 password hash are sent to HIBP; comparison occurs locally. API keys are never sent to a third party. A detected exposure creates a redacted security finding and notification with remediation guidance.

Self-monitoring periodically evaluates local API health, database access, configured provider reachability where explicitly enabled, failed audit events, stale credentials, and local exposure findings. It records deduplicated status transitions and presents them through existing in-app notification surfaces without claiming health that was not checked.

## Security and Resilience

Security prioritizes resilient, frictionless enablement: default-safe controls, progressive escalation only for sensitive actions, actionable remediation, and no secret leakage. Policy remains server-enforced; the UI never supplies authority.

Every active local account receives the administrator, approver, and runtime-gate-manager roles for its isolated data. Model selection, fallback/advisor preferences, capability gates, and decision modes are stored and enforced per principal, never globally shared between accounts. Existing global control state migrates to the original owner only; other accounts start from the fail-closed defaults. Routine model selection, capability decisions, and normal application use require no extra authentication. Elevated password confirmation is reserved for sensitive Settings changes; an MFA code is requested only when that account has voluntarily enrolled MFA and the affected Settings control requires it.

The lock screen exposes `Create new user and separate instance`, which creates a separate local workspace, database, vault, connectors, files, and login before opening it in a new tab. It does not add another account to the current instance. `Forgot password` opens a recovery form that verifies the username plus a current TOTP code or a one-time backup recovery code before allowing a new password. The form never states whether the username exists, and accounts without an enrolled recovery factor must use the documented local-owner recovery path.

All external requests require an enabled runtime capability and an owner egress allowlist. MCP connections are reject-by-default, validate endpoint identity before persistence, and audit redacted metadata only. Automated rotation is enabled only per provider adapter after a successful capability and authorization check.

## Verification

- Tests are added before each new backend and UI behavior.
- Unit and API tests cover archive/rename, legacy-role repair, MCP authorization and egress enforcement, credential rotation states, breach-check privacy, and health-alert deduplication.
- Vitest covers the reworked route behavior and decision-control filtering.
- Playwright exercises login, all routes, responsive layouts, session actions, model selection, capability controls, settings, checkpoints, MCP, security alerts, and failure states.
- Python CI, web CI, phase validation, local runtime validators, lint, type-check, build, and static serving checks run before commit.

## Failure-Mode Check

- Critical: An MCP connector could bypass policy. Mitigation: executor registration, authority routing, egress enforcement, and audit coverage are required before exposure in the UI.
- Critical: A database migration could hide or lose existing conversations. Mitigation: additive idempotent migrations, existing-data regression fixtures, and archive-only default filtering.
- Critical: A breach check could leak secrets. Mitigation: local scanning, redacted findings, k-anonymous password ranges only, and no API-key transmission.
- Minor: Current providers have no configured key-management authorization. Limitation: Raiker presents a verified manual rotation flow and never reports automated rotation for those providers.
