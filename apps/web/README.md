# Raiker Web App (`apps/web`)

The local web app for Raiker's governed agent runtime — a professional, pastel-themed
view/controller over the existing governed backend, never a privileged interface. It is
single-user and loopback-only: `raiker-web` serves the built SPA and the governed API from one
`127.0.0.1` origin, and every read and mutation flows through the same contracts, policy engine,
RuntimeAuthority, and append-only audit log as the terminal client.

## Design

- **Control Deck design system, dual theme** — light and dark themes built from one token set in
  `src/app.css` (semantic surfaces, text, borders, and status colors). The default follows the OS
  (`prefers-color-scheme`); an explicit choice is applied via `data-theme` and persisted in
  `localStorage` (a UI preference, unlike the bearer token, which is memory-only).
- **Calm by default, audit on demand** — Chat is the front door and shows the conversation, not
  the machinery. Each turn's governed gather → plan → act → verify record sits behind a
  "How this turn was governed" disclosure, and the full event record lives on the Audit log page.
- **Honest, fail-closed UX** — badges/copy always state what is real (`metadata-only`,
  `deferred`, `fails closed`); unknown backend codes and capabilities are surfaced raw, never
  hidden; the UI adds no authority of its own. A label never names an act that did not happen:
  `Ready` means a readiness check passed, `Connection saved` means a credential is stored and
  nothing more, and no surface reports a reaction, a thought, or a connection it did not observe.
- **The page shows state; the guide explains it** — a component carries the state, the next
  action, and a failure's reason with its remediation. Everything else lives in
  [`docs/guide/`](../../docs/guide) and is reached from the page's own **How … works** link.
  The rule, and the test that makes it usable, are in
  [`VISUAL_DESIGN_SPEC.md`](../../docs/architecture/VISUAL_DESIGN_SPEC.md) §2b.

### Composer model picker

Chat and Build share a compact model picker: a provider mark for every
configured provider, a provider header followed by that provider's concise
model labels (for example, `Haiku 4.5`, `Gemma 4:31B Cloud`, or `Gemini 2.5
Pro`), and the model's effort control.
Provider and model identifiers remain unchanged at the API boundary.
The picker and Models page use the published provider assets recorded in
[`public/provider-logos/`](public/provider-logos/); assets subject to a
provider's brand terms remain governed by those terms.

## Shared shell

`ResponsivePage` wraps authenticated route content while preserving the existing
sidebar, topbar, skip link, and main landmark. At tablet sizes the sidebar becomes
a focus-safe drawer; below 640px, a labelled bottom navigation keeps the primary
destinations available. The closed compact drawer is inert, so it cannot intercept
keyboard navigation.

## Surfaces

| Page | What it covers |
| --- | --- |
| Workbench | The live board and the default screen: cycles in flight, agents standing on a repeating cadence, and runs scheduled and not yet fired, each with a safe-boundary stop. It carries no composer — starting work is a link to the surface that owns one |
| Chat | Streaming governed turns (SSE), per-prompt options (provider + model picked from the provider's live catalogue, planning, tool budget), workspace path attachments (bounded, untrusted-labelled, workspace-scoped fail-closed), inline needs-approval hand-off |
| Build | Coding workspace: a Plan/Edit/Auto **Mode** menu backed by per-capability decision modes (`deny`/`ask`/`auto`) plus the per-turn planning option, repository references (workspace-contained folder, or a GitHub `owner/repo` coordinate read through the governed connector), inline accept/reject for pending changes, a collapsible background-work rail, scheduled agents, and filing the chat into a project |
| Approvals | Pending/approved/denied inbox, redacted diff/argument previews, metadata-only resolution |
| Tasks | Active tasks with progress + safe-boundary stop, runs parked on an approval shown as blocked (not failed) with the reason and a link to the decision, and a finished list that states how each run ended |
| Sessions | Session browser → turns → per-turn governed events |
| Knowledge Map | Full-workspace Raiker-themed force graph over governed records; global/local scopes, relationship-depth traversal, neighbour highlighting, search-driven colour groups, node inspector, zoom/pan/pin, source action, and adjustable display, physical-force, and motion controls |
| Capabilities | All capability gates (per phase), friendly labels, gate enable/disable with step-up (reason, Tier-2 confirmation token, threat ack), per-capability decision modes (`ask`/`allow`/`auto`/`deny`) |
| Models | Model profiles with provider + model selection (each provider's model catalogue fetched on demand, gate-manager only writes), advisor-model picker for local-model turns, hosted/private gate + egress allowlist posture (no keys, no allowlist values) |
| Connections | Service catalogue with a governed **Connect via MCP** flow for a local starter or a remote HTTP endpoint; remote authentication stores only a token environment-variable reference |
| MCP Servers | Owner-scoped local and remote MCP profiles, with discovered tools, redacted recent-session telemetry, open findings, notifications, and pause/resume controls. A connected, uncontained server's tools are offered to the model as `mcp__<server>__<tool>` once the owner raises the `mcp_connector_runtime` decision mode above the default `ask` |
| Checkpoints | Rewind metadata per session (restore flags are metadata only) |
| Audit log | The append-only event record with session/type filters |
| Diagnostics | Readiness checks, configuration gaps, counts, config-derived provider status |
| Settings | Runtime mode activate/disable (step-up gated), appearance (light/dark/system), vault/MFA/session controls, and redacted credential lifecycle, bounded local scan, health, and opt-in breach posture |
| Guide | The user guide, served read-only from the install and rendered with the same Markdown component the transcript uses. Seven sections in reading order, deep-linkable as `#/guide?section=…`, and reachable from each page's own **How … works** link. A build that shipped no guide says so rather than showing an empty list |

A top-bar **STOP** switch requests safe-boundary cancellation of all active tasks via the governed
interrupt path.

## Develop

```bash
npm install
npm run dev      # local dev server on http://127.0.0.1:5174 (proxies /api to raiker-web)
npm run lint     # eslint
npm run check    # svelte-check / tsc type-check
npm run test     # vitest
npm run build    # production build to dist/ (served by raiker-web)
```

Stack: Vite + Svelte 5 + TypeScript, D3 Force for the Knowledge Map simulation,
Vitest + Testing Library for component tests; no external fonts/CDNs (works fully
offline). The JS toolchain is isolated here and does not affect the Python package
or its `ruff`/`mypy`/`pytest` gate.

The typed API client lives in `src/lib/api.ts` / `src/lib/apiTypes.ts`; the backend contract test
`tests/test_api_contract_schemas.py` guards the response keys the client reads.

The Build workspace's mode mapping and cadence list are pure modules
(`src/lib/buildModes.ts`, `src/lib/agentCadence.ts`) so the posture a label
promises is unit-tested apart from the view. See
[docs/architecture/BUILD_WORKSPACE_SPEC.md](../../docs/architecture/BUILD_WORKSPACE_SPEC.md).

Shared presentational primitives live in `src/lib/components/`: `PageState`,
`ResponsivePage`, `SessionMenu`, and `ToolControlBoard`. They only render server
truth and route callbacks to their consumers. `SessionMenu` shares only
loopback-origin hash links; its route integration is deferred to the Sessions
migration task.
