# Raiker Web App (`apps/web`)

The local web app for Raiker's governed agent runtime — a professional, pastel-themed
view/controller over the existing governed backend, never a privileged interface. It is
single-user and loopback-only: `raiker-web` serves the built SPA and the governed API from one
`127.0.0.1` origin, and every read and mutation flows through the same contracts, policy engine,
RuntimeAuthority, and append-only audit log as the terminal client.

## Design

- **Pastel design system, dual theme** — light and dark themes built from one token set in
  `src/app.css` (iris/mint/peach/rose/sky accents). The default follows the OS
  (`prefers-color-scheme`); an explicit choice is applied via `data-theme` and persisted in
  `localStorage` (a UI preference, unlike the bearer token, which is memory-only).
- **Calm by default, audit on demand** — Chat is the front door and shows the conversation, not
  the machinery. Each turn's governed gather → plan → act → verify record sits behind a
  "How this turn was governed" disclosure, and the full event record lives on the Audit log page.
- **Honest, fail-closed UX** — badges/copy always state what is real (`metadata-only`,
  `deferred`, `fails closed`); unknown backend codes and capabilities are surfaced raw, never
  hidden; the UI adds no authority of its own.

## Shared shell

`ResponsivePage` wraps authenticated route content while preserving the existing
sidebar, topbar, skip link, and main landmark. On narrow screens the sidebar
becomes a labelled icon rail; route-body migrations are deliberately staged in
later Control Deck tasks.

## Surfaces

| Page | What it covers |
| --- | --- |
| Chat | Streaming governed turns (SSE), per-prompt options (provider + model picked from the provider's live catalogue, planning, tool budget), workspace path attachments (bounded, untrusted-labelled, workspace-scoped fail-closed), inline needs-approval hand-off |
| Approvals | Pending/approved/denied inbox, redacted diff/argument previews, metadata-only resolution |
| Tasks | Active tasks with progress + safe-boundary stop, task history |
| Sessions | Session browser → turns → per-turn governed events |
| Capabilities | All capability gates (per phase), friendly labels, gate enable/disable with step-up (reason, Tier-2 confirmation token, threat ack), per-capability decision modes (`ask`/`allow`/`auto`/`deny`) |
| Models | Model profiles with provider + model selection (each provider's model catalogue fetched on demand, gate-manager only writes), advisor-model picker for local-model turns, hosted/private gate + egress allowlist posture (no keys, no allowlist values) |
| Connections | Service catalogue with a governed **Connect via MCP** flow for a local starter or a remote HTTP endpoint; remote authentication stores only a token environment-variable reference |
| MCP Servers | Owner-scoped local and remote MCP profiles, with discovered tools, redacted recent-session telemetry, open findings, notifications, and pause/resume controls |
| Checkpoints | Rewind metadata per session (restore flags are metadata only) |
| Audit log | The append-only event record with session/type filters |
| Diagnostics | Readiness checks, configuration gaps, counts, config-derived provider status |
| Settings | Runtime mode activate/disable (step-up gated), appearance (light/dark/system), vault/MFA/session controls, and redacted credential lifecycle, bounded local scan, health, and opt-in breach posture |

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

Stack: Vite + Svelte 5 + TypeScript, Vitest + Testing Library for component tests; no runtime
dependencies beyond Svelte, no external fonts/CDNs (works fully offline). The JS toolchain is
isolated here and does not affect the Python package or its `ruff`/`mypy`/`pytest` gate.

The typed API client lives in `src/lib/api.ts` / `src/lib/apiTypes.ts`; the backend contract test
`tests/test_api_contract_schemas.py` guards the response keys the client reads.

Shared presentational primitives live in `src/lib/components/`: `PageState`,
`ResponsivePage`, `SessionMenu`, and `ToolControlBoard`. They only render server
truth and route callbacks to their consumers. `SessionMenu` shares only
loopback-origin hash links; its route integration is deferred to the Sessions
migration task.
