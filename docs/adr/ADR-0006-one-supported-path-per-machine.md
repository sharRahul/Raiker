# ADR-0006: One supported path per machine, safe defaults that can do the work

## Status

Accepted on 2026-11-16 and revised the same day with the owner's direction
(native Windows sandbox without WSL2; always-on host; Pause that interrupts).
Not built; delivered by the [ready-to-use plan](../plans/READY_TO_USE_PLAN.md).

## Date

2026-11-16

## Context

The governed runtime is in place, but the owner cannot simply use Raiker every
day on a Windows or Linux desktop:

- Nothing is published.
- Commands are refused by default on Windows and macOS. Windows already has a
  native boundary that measured every observation enforced — the
  restricted-account sandbox — but its one-time administrator setup exists only
  as a command, and AppContainer, the older boundary, fails real tests.
- The first day is a list of decisions (80 permission rows, 16 Settings
  sections), and memory proposals, search by meaning and commands each need a
  separate trip.
- Goals run only while the window is open, and Pause cannot interrupt a step
  that is already running.

The reference review (sources in the
[plan](../plans/READY_TO_USE_PLAN.md#what-the-reference-agents-do)) found that
OpenAI Codex ships a native Windows sandbox and recommends it over WSL2. Its
`elevated` mode — dedicated lower-privilege sandbox users, filesystem
boundaries and firewall rules, behind one administrator-approved setup — is
the same design as Raiker's restricted-account boundary. Claude Code sandboxes
with Seatbelt and Bubblewrap and separates *whether* a tool runs from *what it
can reach*. Hermes Agent and Meta Muse keep working after the app closes.

## Decision

### 1. One default command boundary per platform, set up from Raiker

| Platform | Default | Setup | Options (Advanced) |
|---|---|---|---|
| Windows | **Restricted-account sandbox** (`RaikerSandbox` users, Job Object, outbound firewall rule, WFP loopback filter) — **no WSL2** | Raiker Setup › *Set up the command sandbox*: one UAC prompt | WSL2 (Linux toolchains); MXC after it passes the probe |
| Linux | Bubblewrap + seccomp | Present on stock installs; Setup names the package if missing | — |
| macOS | Sandbox account under Seatbelt | Raiker Setup, one administrator prompt | — |

AppContainer is retired as an execution boundary. The probe still decides: a
boundary that does not measure every mandatory observation enforced is
refused. A restricted token derived from the owner's own account (Codex's
`unelevated` mode) needs no administrator but cannot contain the network, so
it is not a default.

### 2. Strict and simple permissions

Ten named families group the capabilities, and three postures sit above them:
**Ask first**, **Work in the sandbox** (in-copy edits and commands run without a
prompt; leaving the copy or the machine, durable memory, messages and money
still ask), **Read-only**. A posture is a fixed bundle of the decision modes the
runtime already enforces, changed through the same step-up, and falls back to
*Ask first* whenever the probe is not fully enforced.

### 3. Memory is reviewed where it is proposed

A proposal is kept or declined under the answer; nothing is stored without the
owner's Keep. Memory opens on a readable summary with one switch; local search
by meaning is one choice, scoped to a loopback embedding profile.

### 4. The host can run without the window

The host registers as a per-user service on each platform; the desktop app is
a client of it, locally or through Remote access (two-step sign-in). Goals,
routines and background runs continue with the window closed.

### 5. Pause parks a running turn and Resume continues it

Pause takes effect at the next safe boundary — before a model call, between
tool calls, or by freezing a running command's process tree — and parks the
turn in the existing suspended-turn store. Resume re-checks permissions,
profile and budget before the next action. A frozen command past its limit is
stopped and reported.

### 6. Health diagnoses and routes to the fix; releases are published

Health adds no authority path. Personal pre-releases are published from green
`main` with `SHA256SUMS.txt`, unsigned under the owner scope.

## Options considered

- **WSL2 as Windows' default** (the first version of this ADR). Superseded by
  the owner's direction and by the finding that the restricted-account
  boundary already measures enforced natively; WSL2 remains an option.
- **AppContainer.** Rejected: it fails the `.git` ACL test and blocks Node, Git,
  MSYS and virtualenv Python.
- **Codex `unelevated` (restricted token, no admin).** Rejected as a default:
  network isolation is environmental, which fails Raiker's egress observation.
- **Docker or Podman.** Rejected: Raiker removed container backends in favour
  of native boundaries it can probe.
- **A classifier or a bypass mode to reduce prompts.** Rejected: postures reuse
  the decision modes, and the sandbox, not a model, bounds what runs unasked.

## Consequences

- Windows Build needs one UAC prompt. A managed PC that forbids local accounts
  or firewall changes keeps commands refused, and Health says why.
- The restricted-account gaps (per-task profile reset, logon-right denials,
  explicit-ACE scan under denied roots) become P0 before it is the default.
- Pause adds a *paused* turn state and a freeze path in the runner on each
  platform.
- An always-on host widens the time the runtime acts unattended; budgets,
  Stop, approvals and the audit record are what bound it, unchanged.

## Not changed

Governed action flow, approvals, audit, encryption at rest, the probe's
mandatory observations, connection-bound model authorization (ADR-0004) and
persona narrowing (ADR-0005).

## Acceptance criteria

The plan's P0 items pass their *done when* checks on clean Windows 11 and
Ubuntu 24.04 machines, and the regular-use journeys in
[TESTING.md](../plans/TESTING.md#regular-use-journeys) pass on the published
build.
