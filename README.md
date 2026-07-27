# Raiker

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first AI-agent runtime. Every model interaction and tool
action passes through policy, capability gates, approvals, and audit records, so
local automation stays under your control.

The launchable local UIs are the plain local terminal client and the local web dashboard — `raiker` and `raiker-web`, the latter on `127.0.0.1`; Phase 8 deferred clients are not available. Approving a proposed file change performs it once, under a fresh gate, policy and posture check, with the previous contents checkpointed; every other approval records a decision only. Durable memory mutation is broker-governed, and strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

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

To connect a hosted model, open **Models**, press **Connect** on the provider,
and paste your API key. That is the whole flow — see
[Connecting a model](docs/guide/connecting-a-model.md).

## Owner-authoritative and monitored

Raiker is **owner-authoritative and monitored, not prevention-by-restriction**.
Security here is not restricting you; it is letting you operate without having
your own access taken away.

**Configuring something is permission for it.** Saving a provider's credential
is the authorization to use that provider, and the endpoint you configured is
authorised with it. You are not then asked to satisfy a separate switch, a
separate host allowlist, and a separate encryption key before the thing you just
set up will run.

That consent is scoped and revocable, never a blanket opening: configuring
Anthropic authorises `api.anthropic.com` and nothing else, a provider you have
not configured still fails closed, and a capability you *explicitly* turn off
stays off whatever is configured.

Controls that stand between an AI-proposed action and it happening:

| Control | Where | What it decides |
|---|---|---|
| **Runtime mode** | Settings → General | How far *any* capability may be enabled |
| **Capability gate** | Permissions | Whether this capability exists for you at all |
| **Decision mode** | Permissions, or the Chat composer | Ask / Allow / Auto / Deny before each action |
| **Approval** | Approvals | A human decision on the specific proposed action |

Opening a higher-risk gate is a governed step-up: a human `runtime_gate_manager`,
a reason, a short phrase they type to record their intent, and a threat-model
acknowledgement — all recorded against your principal. The phrase is not a
credential. Owner **recovery** is governed and audited.

A human `runtime_gate_manager` alone may change runtime modes and capability
gates.

Approving does one of two things, and the approval detail says which **before**
you decide. A proposed **file change** is performed once, through the governed
approval execution relay — re-governed at execution time, with the previous
contents checkpointed so it can be rewound, and never into `.raiker/` or
`.git/`. **Everything else** — shell, network, process — records your decision
and executes nothing. Disabling either the `approval_execution_relay` or
`file_write_execution` capability returns file approvals to record-only, and a
critical approval always uses the human-only, step-up-verified lifecycle
instead.

Deferred dangerous domains — remote and cloud execution, finance, medical, CCTV, home security, and hardware actions — have no governed executor
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

- **Markdown is not rendered in Chat**, and there is no export, download, or PDF
  control anywhere.
- **MCP servers cannot be used by the agent** — create, connect, and monitor all
  work; their tools are not offered to the model in Chat.
- **Approved shell, network, and process actions still do not run** — approval
  resolution executes file changes only. This is deliberate, not an oversight:
  a file write is local, checkpointed, and reversible, and the other three are
  not. Resolving any of them still continues the parked turn, with an honest
  "approved, but not executed" result the agent can react to.
- **A model proposing several tool calls at once gets one of them.** The
  orchestrator takes the first and drops the rest without telling the model.
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
