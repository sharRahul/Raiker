# Core Concepts

> Part of the Raiker documentation set. See also: [Getting Started](getting-started.md),
> [Capabilities](../RUNTIME_EXECUTORS_SPEC.md), [Security Architecture](../SECURITY_ARCHITECTURE.md).

Raiker is built around one idea: **an AI agent should be able to do a great deal,
but only what its human owner has explicitly, auditably allowed.** Everything
below is how that idea is enforced in code.

## The governed action path

Every action — whether proposed by a human, an AI principal, a model tool call,
a plugin, or a background task — passes through a single path:

```
Principal → RuntimeAuthority → PolicyEngine → ToolBroker → Executor → Event log
```

No component executes work off this path. If any stage returns a non-allow
decision, execution stops (strict non-allow blocking). Approval resolution is
metadata-only: resolving an approval records an immutable decision; it does not
itself execute the action.

## Principals and roles

A **principal** is whoever is acting: a `human`, an `ai_agent`, an `automation`,
or the `system`. Roles are split into **human-only** roles (`owner`, `admin`,
`runtime_gate_manager`) and AI-assignable roles. Safety-critical operations —
activating runtime modes, enabling capabilities, granting roles, approving one's
own action — are reserved for humans; an AI principal can never perform them.

## Runtime modes

The **runtime mode** sets the ceiling on what class of capabilities may run at
all — from `development_preview` (nothing executes) up through
`local_single_user_runtime` (a single local owner) and beyond. Only a human
`runtime_gate_manager` can activate a mode, and the choice is persisted and
audited.

## Capability gates (integrated-enabled, no-executor fail-closed)

Raiker's abilities are enumerated as ~53 **capabilities**, each with a **gate**.
Integrated capabilities — exactly the capabilities in `REAL_EXECUTOR_CAPABILITIES`
— default to `enabled_runtime`; capabilities without a real executor default to
`disabled` and fail closed rather than fabricating success. Disabling an
integrated gate is still owner/`runtime_gate_manager` controlled, persisted, and
audited. An enabled gate is not unrestricted execution: every AI-proposed action
still passes through the standing decision mode (default `ask`), PolicyEngine
hard-denies, risk floors, and executor-level allowlists/threat acknowledgements.

Capabilities are organized in tiers by blast radius: Tier 1 (local, reversible)
→ Tier 2 (sandboxed execution) → Tier 3 (code intelligence) → Tier 4 (plugins) →
Tier 5 (channels, containers, models) → Tier 6 (sensitive real-world domains).
See [Capabilities](../RUNTIME_EXECUTORS_SPEC.md) for the current, per-capability
truth.

## Decision modes

Enabling a gate says *whether* a capability may run; a **decision mode** says
*how* an AI-proposed action on it is treated. Each capability has one of four
owner-chosen modes:

- **`ask`** (default) — the action requires human approval before it runs.
- **`deny`** — the action is always blocked.
- **`allow`** — standing permission to run without prompting.
- **`auto`** — Raiker decides deterministically by risk (low runs, medium/high
  ask, critical always requires a human).

Two floors always hold regardless of mode: PolicyEngine hard-denies block first,
and **critical-risk actions always require a human** — `allow`/`auto` can
never let an AI take a critical action. Permissive modes (`allow`/`auto`)
can only be set on capabilities that have a real executor. Full detail:
[Decision Modes Spec](../DECISION_MODES_SPEC.md).

## Executors

An **executor** is the only thing that performs a capability's real work. The
default registry contains *exactly* the capabilities with genuine executors
(`REAL_EXECUTOR_CAPABILITIES`); everything else is absent and fails closed.
Executors return **metadata-only** artifacts — ids, counts, status — never raw
tool output or sensitive content, so the audit trail never leaks what it
governs.

## Policy engine and broker

The **PolicyEngine** classifies each action's risk and applies allow / deny /
needs-approval / needs-risk-acceptance rules. The **ToolBroker** is the guarded
gateway through which tools actually run, enforcing workspace confinement and
managed denies. Together they are the enforcement layer the decision modes sit
on top of.

## Events and audit

Every proposal, policy decision, approval, activation, and execution appends an
immutable record to the event log. The log is the system of record: capability
enablement, decision-mode changes, and every governed action are reconstructable
from it. Runtime artifacts stay metadata-only so the log is safe to retain.

## Threat-model acknowledgements

Higher-risk capabilities cannot be enabled until the owner records an
acknowledgement of that capability's threat-model document (`docs/threat-models/`).
This forces an explicit, logged "I understand the risk" step into the activation
path — it is not a formality the code can skip.

## Where to go next

- **[Getting Started](getting-started.md)** — install, bootstrap, first action.
- **[Capabilities](../RUNTIME_EXECUTORS_SPEC.md)** — the per-capability catalog.
- **[Security Architecture](../SECURITY_ARCHITECTURE.md)** — the deeper security
  posture and deferred-control gaps.

## In this section

- [The Governed Action Path](core-concepts-governed-action-path.md)
- [Principals & Roles](core-concepts-principals-and-roles.md)
- [Capability Gates](core-concepts-capability-gates.md)
- [Decision Modes](core-concepts-decision-modes.md)
- [Events & Audit](core-concepts-events-and-audit.md)
