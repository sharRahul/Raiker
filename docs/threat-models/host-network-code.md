# Threat model — code with this machine's network (`host_network_code_execution`)

`host_network_code_execution` is not a new way to run anything. It is the name a
[`shell_execution`](shell-execution.md) or [`process_execution`](process-execution.md)
command is given when two things are both true: the program it starts runs code
the command line does not show — `python`, `node`, `npm`, `npx`, `pip` — and
that code would run on the host, with the host's network.

It exists because of [BUG-308](../plans/TO_BE_FIXED.md), the remainder of CR-05
and CR-09 of the 2026-09-05 security review: every argv check Raiker applies to
those commands passed, and none of them is a network boundary. A script in the
workspace can open a socket the egress policy never sees.

## What decides where the code runs

One rule, `raiker/execution/code_placement.py` → `place_code`, asked by the
router before a gate is read and by the command service before a run starts:

| Situation | Where the code runs | What governs it |
|---|---|---|
| The program runs no code (`ls`, `git`, `grep`) | Unchanged | `shell_execution` / `process_execution` |
| The owner chose a container or a remote environment | That environment | `shell_execution` / `process_execution` |
| No environment chosen, and this machine has the native sandbox | Inside the native sandbox — no network | `shell_execution` / `process_execution` |
| No environment chosen, and no native sandbox here | The host, with its network | **`host_network_code_execution`** |
| The owner chose the host (`local_native`) | The host, with its network | **`host_network_code_execution`** |
| A background run or a terminal, which the sandbox cannot host | The host, with its network | **`host_network_code_execution`** |

The owner's decision (2026-09-28) is the last three rows: the code still runs —
nothing that worked before starts refusing — but it runs under a capability that
says what it is, with its own switch in Permissions and a decision mode that,
like every capability's, starts at *Ask me*.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A script opening a connection no egress check sees | Where there is a sandbox, the code runs inside it with the network namespace removed; where there is none, the owner is asked, under a name that says so | `code_placement.py`, `execution/commands/service.py` |
| Turning shell off, and the agent running `python` instead | The router checks the gate and a *Never* of the command capability the action arrived through before reclassifying it; both must allow it | `RuntimeAuthority._place_code` |
| A command authorised only as an ordinary shell command running host-network code | The command service refuses host-placed code unless the caller says it was authorised under this capability (`host_network_code_not_authorized`); only `HostNetworkCodeExecutor` says so | `CommandService._place_code`, `tier2_shell.py` |
| A session command grant (`run_command`) bypassing the router's reclassification | The broker asks the same placement and applies this capability's switch and *Never*; the grant itself stands in for *Ask me*, as a standing grant does | `ToolBroker._host_network_code_refusal` |
| A sandbox probe that is stale by the time the command runs | Classification may reuse a probe for 30 seconds; the run always probes again, and a sandbox that fails at launch refuses rather than falling back to the host | `sandbox_available`, the native backend |
| Code the owner approved for the host finding a sandbox at run time | It runs inside the sandbox — only ever stricter than what was approved | `CommandService._place_code` |

## Nothing that worked starts refusing

On an account a capability with no stored row reads as off, which would have
refused a script for an owner who had turned *Shell commands* on. Two stored
rows prevent that, never an inference at read time: migration
`RAIKER-2072-host-network-code-carry-over` turns this capability on once for
every account and workspace table that already had shell or process on, and the
first time an owner turns either on it is turned on beside it
(`RuntimeAuthority._carry_command_enable_to_host_network_code`). Neither replaces
a row the owner wrote, and neither copies a decision mode.

## What the owner sees

- **Permissions** lists *Code with this machine's network* under Execution, and
  the rows for it, `shell_execution` and `process_execution` carry *On this
  machine* — measured by the same probe the command service uses — saying
  whether scripts run inside the sandbox or with the network.
- **The event log** records `code_placement_classified` for each reclassified
  action: the program, the reason, and both capability names.

## Residual risk, stated plainly

- **The program list is a list.** A code runner Raiker does not name — an
  interpreter added to the allowlist later — is not placed by this rule until it
  is added to `CODE_RUNNERS`.
- **An owner-chosen environment is the owner's boundary.** A container with a
  network, or a remote machine, is not second-guessed here.
- **A sandbox is only as strong as the host's.** The native runner measures its
  own boundary and refuses when egress is not enforced; see
  [`shell-execution.md`](shell-execution.md).
