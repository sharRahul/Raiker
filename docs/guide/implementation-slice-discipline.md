# The Slice Discipline

> Implementation › Slice Discipline. Back to [Implementation](implementation.md).

Every capability lands as a self-contained slice, in order:

1. **Threat-model doc** — the boundary and non-goals, written first.
2. **Real executor** — fails closed on every missing precondition; never fakes
   success (`not_implemented` is an honest failure).
3. **Activation requirements** — risk tier, runtime mode, threat-ack, human
   confirmation.
4. **Validator + guard-test updates in lockstep**.
5. **Acceptance tests** — "executes when governed" AND "fails closed when
   disabled".
6. **Docs** — ledger, executor spec, handoff.
7. **Gates** — `pytest`, `ruff`, `mypy`, and all five `scripts/validate_*.py`
   pass before commit.
