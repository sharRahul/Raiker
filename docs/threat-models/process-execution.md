# Threat model — direct process execution (`process_execution`)

`process_execution` is the sibling of [`shell_execution`](shell-execution.md):
the same governed command lifecycle, entered with an **executable and an argument
list** rather than with a command string to be split.

It differs from its sibling in one governance-relevant way, and the difference is
the reason it has its own capability: **`process_execution` is deliberately
excluded from [`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py)**.
Approving a `process` action records the decision and executes nothing.

## What the capability does

`raiker/runtime/executors/tier2_shell.py` → `ProcessExecutor` requires
`executable`, takes an optional `args` list, and hands `[executable, *args]` to
`CommandService.run_foreground` — the identical path `shell_execution` uses, with
the same profile resolution, the same backends, the same measured boundary, the
same receipts and the same redaction.

Defaults are looser than the shell path's: **60-second timeout, 200 000 bytes**
of captured output.

Like its sibling, it refuses with `command_authority_missing` unless the action
carries an `authority_kind` and `authority_id`.

## Reachability today

| Question | Answer |
|---|---|
| Has a real executor? | **Yes** — registered in `REAL_EXECUTOR_CAPABILITIES` |
| Reachable by a model? | **No.** `CAPABILITY_GATE_MAP` maps the action type `process` to it, but there is no `process` tool in `TOOL_DEFINITIONS` |
| Executed on approval? | **No.** Not in `EXECUTABLE_ON_APPROVAL` — resolution is metadata-only, and the approval detail says so |

The owner-facing consequence: the gate is real, policy-reviewed and audited,
and enabling it does not by itself give the agent a way to start a process. The
command the agent actually runs answers to `shell_execution`. This is now the
**only** capability in that position — `network_execution`, which shared it, was
deleted in BUG-232 because its executor also enforced weaker controls than the
path it duplicated. `process_execution` was kept because it does not: it enters
the same `CommandService` lifecycle `shell_execution` does, with the same
profile resolution, boundary, receipts and redaction.

## Threats and what stops them

Everything in [`shell-execution.md`](shell-execution.md#threats-and-what-stops-them)
applies unchanged, because the lifecycle is the same one. What is specific here:

| Threat | Mitigation | Where |
|---|---|---|
| The split-versus-argv difference being used to smuggle an operator | There is no split to smuggle through: `argv` arrives already separated, and `shell=False` means no interpreter sees it either way | `raiker/execution/commands/service.py` |
| An approval performing a process start | `process_execution` is excluded from `EXECUTABLE_ON_APPROVAL`; `executable_capability()` returns `None`, and the approval detail's notice states resolution is metadata-only | `raiker/approvals/execution.py`, `raiker/control/dashboard.py` |
| Looser bounds being mistaken for the shell path's | The defaults are stated above and carried on the run row; `truncated` is reported | `tier2_shell.py` |
| A non-list `args` value | `list(...)` over a non-iterable raises before anything starts, and the run is never created | `tier2_shell.py` |

## Residual risk, stated plainly

- **`args` is not type-validated element-by-element.** `list(action.arguments.get("args", []))`
  accepts whatever the caller supplies and the elements reach `argv`. The
  downstream `safe_display` check refuses CR, LF and NUL, and `shell=False` means
  no element is interpreted — but the executor does not itself assert that every
  element is a string.
- **Two capabilities, one lifecycle.** `shell_execution` and `process_execution`
  differ only in how the argv list is arrived at. The separate gate is defensible
  (an owner may want the parsing path and not the raw path, or the reverse), but
  an owner who turns off one and not the other has not halved their exposure —
  the one they left on runs commands.
- **Unreachable today, registered anyway.** This is a registered executor with
  no product caller — the last one left after BUG-232 removed
  `network_execution`. It survived that cut on the merits: it enforces exactly
  what `shell_execution` enforces, so it is not a weaker second path, only an
  unused one. Whether it should be consolidated into `shell_execution` is
  tracked in
  [the prioritised backlog](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

## Evidence

- `raiker/runtime/executors/tier2_shell.py`,
  `raiker/execution/commands/service.py`
- `raiker/approvals/execution.py` (not relayed),
  `raiker/models/tool_registry.py` (no `process` tool)
- [`shell-execution.md`](shell-execution.md) — the reachable sibling
