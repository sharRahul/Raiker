# Raiker

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

Raiker is a local-first AI-agent runtime. Model interactions and tool actions
pass through policy, capability gates, approvals, and audit records so local
automation remains controllable.

The launchable local UIs are the plain local terminal client and the local web dashboard; Phase 8 deferred clients are not available. Approval resolution is metadata-only, durable memory mutation is broker-governed, and strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

## Goal

Enable useful AI-assisted work on a local machine without surrendering control:
every action must be attributable, policy-governed, reviewable, and reversible
where the underlying operation supports it.

## What it provides

- `raiker`: a local terminal client.
- `raiker-web`: a loopback web dashboard at `127.0.0.1`.
- Configurable local and explicitly policy-gated hosted model profiles.

## Safety model

First run uses **owner bootstrap** to create the local **owner principal**.
Every request resolves an **acting-principal**. A human
`runtime_gate_manager` alone may change runtime modes and capability gates;
owner **recovery** is governed and audited. Approval resolution is metadata
only by default. The separately governed approval execution relay never turns
ordinary approval resolution into implicit execution.

Deferred dangerous domains—remote/cloud execution and sensitive finance,
medical, pregnancy, CCTV, home-security, and hardware actions—remain disabled
and fail closed.

Raiker is frictionless for safe local work: the user remains in control, while
zero-trust verification is applied at every authority boundary.

Read the [security philosophy and policy](docs/SECURITY_AND_POLICY.md) before
enabling any governed capability.

## Quick start

Requirements: Python 3.11+, Git, and Node 20+ for the dashboard.

```powershell
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
raiker
```

To run the dashboard:

```powershell
npm --prefix apps/web ci
npm --prefix apps/web run build
raiker-web --workspace .
```

## Documentation

Start with [the documentation index](docs/README.md). It links the architecture,
security model, commands, API contracts, current capability status, and
validation guidance.

For contribution and vulnerability reporting, see [CONTRIBUTING.md](CONTRIBUTING.md)
and [SECURITY.md](SECURITY.md).
