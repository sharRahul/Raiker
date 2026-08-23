# Threat model — governed command execution (`shell_execution`)

`shell_execution` is the highest-consequence capability Raiker offers. It is the
capability behind the `shell` tool and the `run_command` / `background_run`
terminal surface, and it is one of the twelve in
[`EXECUTABLE_ON_APPROVAL`](../../raiker/approvals/execution.py) — **approving a
command really runs it**.

Read this before opening the gate.

## What the capability does

`raiker/runtime/executors/tier2_shell.py` → `ShellExecutor` parses the approved
command with `shlex.split(..., posix=True)` and hands the resulting **argv list**
to `CommandService.run_foreground`. The command is then run by the backend of the
owner's selected execution profile.

Two properties of that hand-off matter more than anything else here:

- **`shell=False`.** The argv list is executed directly. There is no shell
  interpreter in the path, so `;`, `&&`, `|`, backticks and `$(…)` are literal
  argument text rather than operators. A proposal that "chains" commands does not
  chain them.
- **Authority must be bound.** The executor refuses with
  `command_authority_missing` unless the action carries an `authority_kind` and
  `authority_id` — an approval or a standing grant. A command with no recorded
  human authority does not run, even with the gate on.

Defaults: 30-second timeout, 100 000 bytes of captured output.

## The execution boundary is a separate, owner-chosen control

`resolve_command_environment` picks the profile; an unavailable profile raises
rather than falling back. The kinds are `local`, `native`, `container`, `ssh` and
`daytona`.

| Profile | What the boundary really is |
|---|---|
| `local_native` (**default**) | Explicit host access with reduced isolation. Background execution, a POSIX terminal and restart reattachment are built here |
| `native_sandbox` | Windows AppContainer / Linux bubblewrap / macOS Seatbelt: no network capability, workspace reachable through a single grant, `.raiker` denied, `.git` read-only, a Job Object taking the whole process tree. **Foreground only** |
| `container_default` | Local container, `--network none`, no host mounts, persists for a session and can be reset |
| `ssh_default`, `daytona_default` | Owner-configured remote backends with host-key pin and cost ceiling |

**The boundary is measured, not declared.** `raiker-command-runner --probe`
builds the real boundary over the real workspace and runs six differential
observations, each also attempted *outside* the boundary as a control. Only
"worked outside, refused inside" counts; a failed control arm yields **not
proven** and nothing turns green on it.

There is deliberately **no escape hatch**. An unavailable environment is refused,
never rerouted to the host — see
[§4.2](../REFERENCE_PLATFORM_COMPATIBILITY.md#42-an-escape-hatch-out-of-the-sandbox).

## Assets

| Asset | Why it matters |
|---|---|
| The host filesystem and process table | A command is the broadest reach in the product |
| Credentials in the environment | A command that can read the environment can exfiltrate it |
| The workspace | `.raiker` holds the encrypted store; `.git` holds history |
| The audit record | A command whose output is unredacted leaks into evidence |

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| A model runs a command on its own initiative | Capability gate, decision mode, and an approval whose preview names the program; `critical` risk is human-only with step-up | `raiker/runtime/authority/` |
| Shell metacharacter injection chains a second command | `shell=False` and an argv list — the metacharacters are argument text | `raiker/execution/commands/service.py` |
| An approved command is quietly replaced before it runs | The relay verifies the arguments hash against the immutable intent snapshot | `tier1_approval.py` |
| A command runs twice | Atomic `pending → executing → executed` claim | `store.claim_approval_for_execution` |
| A command runs after the approving session was revoked | Posture check denies with `posture_degraded` | `raiker/runtime/authority/posture.py` |
| A command runs with no human behind it | `command_authority_missing` when `authority_kind`/`authority_id` are absent | `tier2_shell.py` |
| A crafted display string forges a log line | `command_safe_display_invalid` refuses CR, LF or NUL in the rendered command | `service.py` |
| Unparseable quoting silently changing meaning | `shlex.split` failure returns `invalid_argument:command` rather than guessing | `tier2_shell.py` |
| A command hangs or floods the log | Timeout and `max_output_bytes` bounds; `truncated` is reported rather than hidden | `service.py` |
| A process tree survives the timeout | The native sandbox's Job Object carries `KILL_ON_JOB_CLOSE` and takes the whole tree | `native/` |
| A lent credential appearing in output or a log | Incremental UTF-8 redaction at every split, exact loaned secrets, PEM blocks and stream boundaries; the git credential is passed in the child environment, never on a command line | `raiker/runtime/git_credential.py` |
| A repeatedly failing command burning a whole turn | Three consecutive failures pause that subject with a stated reason and a raised finding; after a minute one probe call is let through | `raiker/security/containment.py` |
| A run's evidence being disputable | Every run carries a `run_id`, a state machine, an isolation-evidence record and a **receipt digest** | `service.py` |

## Residual risk, stated plainly

- **`local_native` is the default profile, and it is not a sandbox.** It is
  explicit host access with reduced isolation. The stronger boundary is a
  deliberate opt-in because the sandbox is foreground-only.
- **Inside the native sandbox, several controls are absent rather than
  disabled.** PTY and raw input, background execution, persistent sessions,
  filtered domain egress, credential quarantine, SSH and Daytona are **not
  built** there; the capability set comes from the host probe. They are hidden
  rather than greyed out, because a disabled control implies it is one setting
  away. See BUG-194 in [`../plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md).
- **There is no command allowlist.** Governance is per-capability and
  per-approval, not per-argument: Raiker gates *the capability to run a command*
  and asks a human about the specific one, rather than matching a
  `Bash(git *)`-style rule. The reasoning is in
  [§3.1](../REFERENCE_PLATFORM_COMPATIBILITY.md#31-a-capability-gate-instead-of-a-tool-argument-rule).
- **Command output enters the turn.** `stdout` and `stderr` are returned in the
  artifacts. Output from a command is untrusted content like a fetched page: it
  is data, never instruction, but it *is* in context.
- **A standing `run_command` grant is a real widening.** It substitutes for a
  per-command approval for as long as it lasts. It is listed and revocable, and
  it is the one place where an approved command shape runs again without a fresh
  decision.

## Evidence

- `raiker/runtime/executors/tier2_shell.py`,
  `raiker/execution/commands/service.py`, `raiker/execution/profiles.py`,
  `native/`
- [`../EXECUTION_ENVIRONMENTS_SPEC.md`](../EXECUTION_ENVIRONMENTS_SPEC.md)
- [`container.md`](container.md), [`remote-cloud.md`](remote-cloud.md) — the other backends
- [`process-execution.md`](process-execution.md) — the sibling capability
- [`approval-execution-relay.md`](approval-execution-relay.md)
