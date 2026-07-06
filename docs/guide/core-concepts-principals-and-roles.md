# Principals & Roles

> Core Concepts › Principals & Roles. Back to [Core Concepts](core-concepts.md).

A **principal** is whoever is acting: `human`, `ai_agent`, `automation`, or
`system`. Roles split into **human-only** (`owner`, `admin`,
`runtime_gate_manager`) and AI-assignable roles.

Safety-critical operations — activating runtime modes, enabling capabilities,
changing decision modes, granting roles, approving one's own action — are
reserved for humans. An AI principal can never perform them; attempts fail closed
(e.g. `ai_cannot_manage_runtime_gates`).

Decision modes primarily govern **AI-proposed** actions: a human owner running
the CLI self-authorizes, while an AI's proposal is subject to the capability's
mode. See [Decision Modes](core-concepts-decision-modes.md).
