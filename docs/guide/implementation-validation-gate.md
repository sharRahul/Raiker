# The Validation Gate

> Implementation › Validation Gate. Back to [Implementation](implementation.md).

`scripts/validate_*.py` encode the project's non-negotiable invariants and run in
CI and locally (see [`LOCAL_VALIDATION_GATE.md`](../LOCAL_VALIDATION_GATE.md)):

- Gates default-disabled; high-risk capabilities stay disabled.
- Executor availability is **registry-backed**, not a static allowlist.
- No ungoverned CLI mutation paths.
- Documentation truthfulness and command-catalog completeness.

A change is not ready until all five validators, `ruff`, `mypy`, and the full
test suite pass.
