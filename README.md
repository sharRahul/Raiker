# Raiker

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first AI-agent runtime. Every model interaction and tool
action passes through policy, capability gates, approvals, and audit records, so
local automation stays under your control.

The launchable local UIs are the plain local terminal client and the local web dashboard — `raiker` and `raiker-web`, the latter on `127.0.0.1`; Phase 8 deferred clients are not available. Approval resolution is metadata-only, durable memory mutation is broker-governed, and strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

## Quick start

Python 3.11+, Node 20+, Git.

```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
. .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

npm --prefix apps/web ci
npm --prefix apps/web run build

raiker-web --workspace . --no-browser   # then open http://127.0.0.1:8765
```

First run uses **owner bootstrap** to create your local **owner principal** — a
username and password held on this machine. There is no cloud account. Every
request thereafter resolves an **acting-principal**.

To connect a hosted model, start the server with the provider's host allowlisted:

```bash
RAIKER_MODEL_EGRESS_ALLOWLIST='api.anthropic.com' raiker-web --workspace . --no-browser
```

Then follow [Connecting a model](docs/guide/connecting-a-model.md) — four steps,
about ten minutes.

## Raiker fails closed, and that is the point

On a fresh account **every one of Raiker's 62 capability gates is off**, no model
provider is reachable, and no credential can be stored. Nothing is broken; you
have not opened anything yet.

Four independent controls stand between an AI-proposed action and it happening:

| Control | Where | What it decides |
|---|---|---|
| **Runtime mode** | Settings → General | How far *any* capability may be enabled |
| **Capability gate** | Permissions | Whether this capability exists for you at all |
| **Decision mode** | Permissions, or the Chat composer | Ask / Allow / Auto / Deny before each action |
| **Egress allowlist** | `RAIKER_MODEL_EGRESS_ALLOWLIST` (process configuration) | Which hosts may be reached |

Opening a higher-risk gate is a governed step-up: a human `runtime_gate_manager`,
a reason, a confirmation token, and a threat-model acknowledgement — all recorded
against your principal. Owner **recovery** is governed and audited.

A human `runtime_gate_manager` alone may change runtime modes and capability
gates. Approval resolution is **metadata only by default**: recording a decision
does not execute the action. The separately governed approval execution relay
never turns ordinary approval resolution into implicit execution.

Deferred dangerous domains — remote and cloud execution, finance, medical,
pregnancy, CCTV, home security, and hardware actions — have no governed executor
and therefore offer no enable path at all. They fail closed and are listed under
Observability → Diagnostics.

Raiker stays frictionless for safe local work: you remain in control, while
zero-trust verification is applied at every authority boundary.

## What is in the dashboard

| Group | Destinations |
|---|---|
| Home | **Workbench** — resume work, see what needs attention |
| Work | **Chat**, **Build**, **Search Chat**, **Tasks**, **Projects**, **Sessions** |
| Knowledge | **Memory**, **Brain** |
| Control | **Approvals**, **Permissions**, **Models**, **Extensions** |
| Observe | **Observability** — readiness, audit log, checkpoints, live work, notifications |
| Utilities | **Settings** |

Highlights, each verified against a live instance:

- **Chat** — streamed turns against local or hosted models, image and document
  attachments, a recent-chat list with rename/pin/archive/move, and full-text
  search across titles and message bodies.
- **Tasks** — four work types: run now, schedule once, daily routine, and a
  persistent background agent; nestable, prioritised, and stoppable at a safe
  boundary.
- **Models** — local, home-lab, hosted, and advanced providers; live provider
  catalogues; an encrypted per-instance credential vault; a user-owned fallback
  sequence with no silent hosted fallback; and per-provider token and API-cost
  accounting with each figure's source named.
- **Extensions** — governed service connectors and Model Context Protocol
  servers you can build, connect, monitor, and contain.
- **Observability** — an append-only audit log, metadata-only checkpoints, and
  an honest readiness report derived from stored state, never a probe.

The layout adapts live: a bottom bar plus drawer below 640 px, a menu trigger
plus drawer to 1023 px, and the full sidebar at 1024 px and above.

## Known limits

Raiker's documentation does not run ahead of its code. As of 2026-07-26:

- **Chat has no conversation memory.** Prior turns render on screen but are not
  sent to the model.
- **Markdown is not rendered in Chat**, and there is no export, download, or PDF
  control anywhere.
- **MCP servers cannot be used by the agent** — create, connect, and monitor all
  work; their tools are not offered to the model in Chat.
- **Approved file writes do not create files**, because approval is
  metadata-only.
- Automatic context compaction at 90 %, weekly quota display, and the view-only
  file inspector are specified but not shipped.
- **Shipped list prices are unverified defaults.** `config/model-profiles.json`
  seeds prices only for the models whose published rate is recorded there, each
  stamped with an `as_of` date. Check them against your provider's current
  pricing page and override anything that has moved; an unpriced model reports
  its cost as unknown rather than as zero.

Each is written up with a reproduction and a proposed fix in
[docs/plans/TO_BE_FIXED.md](docs/plans/TO_BE_FIXED.md).

## Documentation

- **[User guide](docs/guide/README.md)** — install, connect a model, permissions,
  Chat, tasks, extensions, troubleshooting.
- **[Documentation index](docs/README.md)** — architecture, security model,
  commands, API contracts, capability status, verification.
- **[Live manual test plan](docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md)** — a
  repeatable end-to-end plan and the recorded result of the last round.
- **[Security philosophy and policy](docs/SECURITY_AND_POLICY.md)** — read this
  before enabling any governed capability.

For contribution and vulnerability reporting see
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
