# ADR-0001: Personal autonomous agent on the governed runtime

## Status

Accepted documentation and product direction; staged implementation pending.

## Date

2026-10-07

## Context

The owner requested that architecture and `docs/**` guide Raiker towards a
personal autonomous agent, drawing ideas from Muse.ai, Claude.ai, OpenClaw and
Hermes Agent. Raiker already has task/routine execution, Chat/Build, governed
memory, connectors, approvals and audit. These do not by themselves establish
durable personal goals, proactive usefulness or reliable cross-service outcomes.

## Decision

Adopt the [personal-agent specification](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
and [delivery gates](../plans/PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md).
Add durable goal coordination around existing tasks and ordinary gateway turns.
Preserve owner-controlled models, local-first operation, machine identity,
policy/broker authority, monitored security and equal client status. Personal
context, proactivity and learning are governed capabilities, never grants.
Coding remains a first-class personal-agent workflow.

## Options considered

| Option | Assessment |
|---|---|
| Rename current features without new contracts | Rejected: does not establish goal persistence, safe retries or verified outcomes |
| Copy another agent's execution and permission model | Rejected: conflicts with Raiker's existing authority and deployment choices |
| Add a separate always-on agent with its own tools | Rejected: duplicates authority, identities, leases and audit |
| Extend the current runtime with staged goal coordination | Accepted: reuses working execution paths and makes completion measurable |

## Consequences

The target needs versioned goal/step/envelope/effect contracts, durable leases,
aggregate budgets, privacy lifecycle, recovery, UI references and scenario
verification. API, storage and event additions require reviewed schemas and
migrations when implemented. Proposed names in the spec are not shipped routes
or events. PAA records own new work; existing ADD/BUG/DEC records keep their
scope, including browser ADD-23, off-machine ADD-11 and quiet-hours DEC-21a.

## Review checklist

- Tool execution and policy: one broker; no new permission defaults.
- Memory and storage: owner scope, provenance, retention and migration tests.
- Events: metadata-only correlations; no credentials or private reasoning.
- Connectors/browser: concrete effects, receipts, isolation and safe ambiguity.
- Host/UI: truthful availability, visible decisions, pause/resume/stop.
- Evidence: component, end-to-end and competitive claims remain separate.

This is an architecture decision, not activation of any proposed executor,
remote service, financial domain or model-authored skill.
