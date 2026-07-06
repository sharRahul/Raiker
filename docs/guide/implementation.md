# Implementation

> Part of the Raiker documentation set. See also: [Capabilities](capabilities.md),
> [Core Concepts](core-concepts.md), [Best Practices](best-practices.md).

This section is for contributors and reviewers: how Raiker is built, how work is
sequenced, and where the authoritative status lives.

## Source of truth

- **[`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md)** — the control ledger.
  Every capability/feature is marked `implemented_verified`,
  `implemented_policy_gated`, `readiness_only`, `specified_not_implemented`, or
  `disabled_deferred`. If code and docs disagree, the ledger + the validators win.
- **[`GAP_AND_TODO_ANALYSIS.md`](../GAP_AND_TODO_ANALYSIS.md)** — what is still
  missing (missing docs vs. missing code), with the active backlog.
- **[`RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md)** — per-capability
  executor truth.
- **[`docs/threat-models/`](../threat-models/)** — one document per governed
  capability; a recorded acknowledgement of the relevant doc is required before a
  higher-risk capability can be enabled.

## The slice discipline

Every capability lands as a self-contained slice, in this order:

1. **Threat-model doc** — the boundary and non-goals, written first.
2. **Real executor** — fails closed on every missing precondition; never
   fabricates success (`not_implemented` is an honest failure).
3. **Activation requirements** — risk tier, runtime mode, threat-ack, human
   confirmation.
4. **Validator + guard-test updates in lockstep** — the fail-closed invariants
   are enforced by `scripts/validate_*.py` and guard tests, not just by intent.
5. **Acceptance tests** — proving both "executes when governed" *and* "fails
   closed when disabled".
6. **Docs** — update the ledger, the executor spec, and the handoff.
7. **Gates** — `pytest`, `ruff check .`, `mypy`, and all five
   `scripts/validate_*.py` must pass before commit.

## Local validation gate

`scripts/validate_*.py` encode the project's non-negotiable invariants
(default-disabled gates, registry-backed executor availability, no ungoverned
mutation, documentation truthfulness, command-catalog completeness). They run in
CI and locally; see [`LOCAL_VALIDATION_GATE.md`](../LOCAL_VALIDATION_GATE.md).

## Verification

[`VERIFICATION_PLAN.md`](../VERIFICATION_PLAN.md) describes how behavior is
exercised end-to-end. A capability is `implemented_unverified` until it has real
evidence (e.g. a hosted provider verified against a live key rather than a mock).

## Environment notes

- Python 3.11+. `pip install -e ".[dev]"` provides pytest / ruff / mypy.
- If Ed25519 plugin-signature verification panics on import, `pip install cffi`
  (a missing `_cffi_backend`); CI's fresh-runner install pulls it transitively.

## Where to go next

- **[Handoff](../HANDOFF.md)** — where the current build effort stands and what's
  next.
- **[Best Practices](best-practices.md)** — security and operational guidance.

## In this section

- [The Slice Discipline](implementation-slice-discipline.md)
- [The Validation Gate](implementation-validation-gate.md)
- [Verification](implementation-verification.md)
