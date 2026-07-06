# Decision Modes

> Core Concepts › Decision Modes. Back to [Core Concepts](core-concepts.md).

Enabling a gate says *whether* a capability may run; a **decision mode** says
*how* an AI-proposed action on it is treated:

- **`ask`** (default) — requires human approval before running.
- **`deny`** — always blocked.
- **`always_allow`** — runs without prompting.
- **`auto`** — Raiker decides deterministically by risk (low runs; medium/high
  ask; critical always requires a human).

Two floors always hold: PolicyEngine hard-denies block first, and **critical-risk
actions always require a human** — `always_allow`/`auto` can never let an AI take
a critical action. Permissive modes (`always_allow`/`auto`) can only be set on
capabilities with a real executor. Full detail:
[Decision Modes Spec](../DECISION_MODES_SPEC.md).
