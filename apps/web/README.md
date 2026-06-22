# Raiker Web UI (`apps/web`)

Local-first "mission control" web UI for Raiker's governed agent runtime — a view/controller over
the existing governed backend, never a privileged interface. See the plan and contracts under
[`docs/UI-implementation/`](../../docs/UI-implementation/).

## Status: Milestone 1 (skeleton)

This is the **M1 skeleton only**: app shell, left-nav for every IA section, the runtime status
banner, the STOP switch (a no-op placeholder until M3), and the status-badge system. It renders
**clearly-labelled fixture data** and makes **no backend calls** — nothing here reflects a real
runtime. Backend wiring lands in later milestones (M2+).

## Develop

```bash
npm install
npm run dev      # local dev server on http://127.0.0.1:5174
npm run lint     # eslint
npm run check    # svelte-check / tsc type-check
npm run test     # vitest
npm run build    # production build to dist/
```

Stack: Vite + Svelte 5 + TypeScript, Vitest + Testing Library for component tests. The JS toolchain
is isolated here and does not affect the Python package or its `ruff`/`mypy`/`pytest` gate.
