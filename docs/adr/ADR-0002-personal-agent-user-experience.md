# ADR-0002: Outcome-led personal-agent user experience

## Status

Accepted design/documentation direction; implementation and usability validation pending.

## Date

2026-10-08

## Context

The owner requested implementable UI/UX documentation with detailed reasons and
decisions for every task. Personal-agent work spans conversations, persistent
goals, approvals, schedules, context and results; exposing runtime complexity
on every screen would make ordinary delegation difficult. Existing shared shell,
Chat/Build, task threads and governance logic provide working foundations.

## Decision

Adopt [the personal-agent UX specification](../architecture/PERSONAL_AGENT_UX_SPEC.md)
and [UX-01–UX-12 plan](../plans/PERSONAL_AGENT_UX_IMPLEMENTATION_PLAN.md).
Use outcome-based intake, a useful Home overview, linked goal/task detail,
concrete effect approvals, accessible results, inspectable personal context and
preserved-progress recovery. Retain existing work modes/navigation roles and
shared lifecycle/security contracts. Apply progressive disclosure to technical
configuration while keeping consequential facts visible.

## Alternatives considered

| Option | Reason for disposition |
|---|---|
| Cosmetic redesign alone | Rejected: does not solve delegation, blockers, finding results or recovery |
| Separate personal-agent mode with independent controls | Rejected: fragments history and creates competing authority/state interpretations |
| Replace shell/navigation wholesale | Rejected: discards working tested behavior and risks existing workflows |
| Extend existing surfaces through typed backend contracts | Accepted: keeps continuity and makes availability, effects and outcomes verifiable |

## Consequences and boundaries

New goal/profile/aggregate read models may need PAA backend work, generated
contracts and migration/deep-link compatibility. A frontend must not invent state
or authority when fields are missing. Older Control Deck conceptual screen flows
are superseded only where they conflict with this target interaction contract;
implemented visual tokens and ADD-26 shell remain. Existing permission defaults,
Ask/Allow/Auto/Deny, critical approvals, quiet hours and model/host choices do not
change. Source-based reasoning is not proof of current visual/usability defects.

## Verification and rollback

Each UX task carries reasons, decision/alternatives, concrete work, dependencies,
state/failure rules and RR/CR acceptance evidence. Release requires keyboard/
screen-reader/responsive checks and observed first-use task completion. Roll back
presentation safely without losing records or restoring revoked authority; goal
records remain readable through a supported view. No new UX task is marked done
until implementation and evidence land.
