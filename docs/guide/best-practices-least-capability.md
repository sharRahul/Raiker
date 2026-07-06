# Grant the Least Capability

> Best Practices › Least Capability. Back to [Best Practices](best-practices.md).

- Enable only the capabilities a task needs. For integrated capabilities, keep
  unused or high-risk gates disabled deliberately; no-executor capabilities
  remain disabled/fail-closed by design.
- Keep the **decision mode** as tight as the task allows. `ask` (the default) is
  the safe choice; move to `auto` for low-risk, well-scoped capabilities; reserve
  `allow` for capabilities you fully trust — and remember it still can't
  bypass the critical-risk human floor.
- Prefer `deny` to leaving a capability enabled-but-unused.
- Keep humans on the critical path: never wire an automation to enable gates or
  change decision modes.
