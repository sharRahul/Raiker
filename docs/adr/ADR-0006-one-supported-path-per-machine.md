# ADR-0006: One supported path per machine, safe defaults that can do the work

## Status

Accepted on 2026-11-16. Not built; delivered by the
[ready-to-use plan](../plans/READY_TO_USE_PLAN.md) (RU-01 to RU-14).

## Date

2026-11-16

## Context

Raiker's governed runtime is in place and tested, but the owner still cannot
simply start using it:

- **Nothing is published.** Installers exist only as CI artifacts.
- **Commands are refused by default on two of three desktop platforms.** The
  Windows AppContainer boundary fails a real `.git` ACL test, so Windows
  execution is unavailable — although the WSL2 boundary, built and packaged
  for the same purpose, measured every mandatory observation **enforced** on
  the owner's Windows 11 PC on 2026-11-08. On macOS the sandbox account is
  implemented and passed macOS 15 CI, but its one-time setup exists only as a
  `sudo` command.
- **The first day is a list of decisions.** Permissions opens on 80 rows over
  70 capabilities, Settings on 16 sections, and features the owner expects to
  work (commands in Build, search by meaning) each need a separate trip to
  Permissions.

The reference agents were read for how they reach "install and use" without
weakening isolation (sources in the [plan](../plans/READY_TO_USE_PLAN.md#what-the-reference-agents-do-and-what-raiker-takes-from-each)):

- **Claude Code** sandboxes with Seatbelt on macOS and Bubblewrap on Linux and
  **WSL2**, does not sandbox native Windows, and points Windows users at WSL2.
  It separates *whether* a tool may run (permission modes) from *what it can
  reach* (the sandbox), which lets sandboxed commands run without a prompt.
- **Hermes Agent** offers one installer, a setup wizard, a `doctor` command and
  a terminal backend chosen by one setting.
- **ChatGPT** and **Meta Muse** make the first minute a conversation, run agent
  work in an isolated machine, and hand control back to the person for
  credentials and money; coverage of Muse names trust as the barrier.
- **Cursor** keeps a few named modes and project rules in a file.

## Decision

### 1. Each desktop platform has one default command boundary

| Platform | Default boundary | Set up by | Alternatives (Advanced) |
|---|---|---|---|
| Linux | Bubblewrap + seccomp (unchanged) | Present on stock installs; Setup names the package if missing | — |
| Windows | **WSL2 `RaikerSandbox` distribution** running the Linux runner under Bubblewrap + seccomp, systemd on for the whole-run cgroup | **Raiker Setup › Set up the command sandbox** (no administrator rights; WSL2 itself may need enabling, which Windows asks for) | Restricted-account pool and AppContainer, both refused until each passes its own probe |
| macOS | Sandbox account `_raikersandbox` under Seatbelt | **Raiker Setup** runs `--setup-account` behind one administrator prompt | — |

The probe still decides availability: a boundary that does not measure every
mandatory observation as enforced is refused, exactly as today. Declining
setup leaves commands refused, said with the button that sets it up.

### 2. Postures are named bundles of existing decision modes

Permissions opens on three postures: **Ask first**, **Work in the sandbox**,
**Read-only**. Each is a fixed, documented mapping onto the decision modes
the runtime already enforces; changing posture uses the same step-up as
changing a mode. **Work in the sandbox** runs file edits and commands that stay
inside the disposable copy without a prompt (the sandbox bounds what they can
reach, as in Claude Code); anything that leaves the copy, leaves the machine,
writes durable memory or spends money still asks. The per-capability list
stays one click away as **Customise**.

### 3. The first run is four steps and ends in a working chat

*Account* → *Model* → *This machine* (command sandbox, local embedding model,
backups) → *Posture*. Every step except *Account* can be skipped; what was
skipped appears on **Health**.

### 4. Health diagnoses and routes to the fix

One page (and `raiker doctor` for the same checks) lists each readiness fact
with its fix. A fix is the page that already owns it; Health adds no authority
path.

### 5. Releases are published

Personal pre-releases are published from green `main` with one asset per
platform and `SHA256SUMS.txt`, unsigned under the
[personal beta scope](../plans/PERSONAL_BETA_SCOPE.md), and the app updates
from that channel.

### 6. Local search by meaning is offered as one choice

When the embedding model runs on loopback (Ollama or Raiker's managed
llama.cpp), first run may turn on Provider embeddings **scoped to that local
profile** with the owner's single consent. A hosted embedding model keeps
today's separate approval.

## Options considered

- **Keep AppContainer as Windows' only boundary and fix the ACL gap first.**
  Rejected for the default: the gap needs disposable-workspace and LPAC work
  with no measured path yet, while WSL2 already measures enforced.
- **Docker or Podman as a portable sandbox (Hermes Agent's choice).** Rejected:
  Raiker removed container backends in favour of native boundaries it can
  probe, and a container runtime is a heavier prerequisite than WSL2 on
  Windows or nothing on Linux and macOS.
- **A "trust this project" switch that allows everything.** Rejected: it would
  be a second permission system; postures reuse the one that exists.
- **Hide unready capabilities entirely.** Rejected: the owner cannot fix what
  is not shown; Health lists them with their reason.

## Consequences

- Windows Build needs WSL2. Machines that cannot run it (some managed or
  virtualised PCs) keep commands refused, and Health says why.
- Toolchains: Linux toolchains run inside the distribution; Windows-only
  toolchains (MSBuild, PowerShell scripts) are not reachable from it, because
  WSL interop is denied by the boundary. The restricted-account and
  AppContainer backends that would run them stay under Advanced and stay
  refused until each passes its own probe.
- Postures need a unit-tested mapping and documentation of exactly which modes
  each sets; drift between the two is a defect.
- Settings deep links must keep working when sections move.

## Not changed

Governed action flow, approvals, audit, encryption at rest, the probe's
mandatory observations, connection-bound model authorization (ADR-0004), and
persona narrowing (ADR-0005). No capability becomes available without its
gate, and nothing runs outside an enforced boundary.

## Residual risk

- **Work in the sandbox** trusts the boundary to contain in-copy actions; a
  boundary regression would turn into actions without a prompt. Mitigation:
  the probe runs before each session and refuses on any non-enforced
  observation; the posture falls back to *Ask first* when it does.
- Unsigned releases depend on the owner verifying `SHA256SUMS.txt`; the release
  page and Getting started say how.

## Acceptance criteria

The plan's P0 items (RU-01 to RU-05) pass their *done when* checks on clean
Windows 11, macOS 15 and Ubuntu 24.04 machines, and the beta plan's SB-1, SB-2,
SB-6, IN-4 and IN-5 rows carry that evidence.
