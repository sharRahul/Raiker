# Windows restricted-account sandbox (design)

Status: **implemented and measured on Windows 11 (2026-10-31); hosted CI
evidence pending.** Replaces AppContainer for build execution on Windows after real runs showed AppContainer blocks ordinary toolchains (see
`NATIVE_SANDBOX_MIGRATION.md`, *Windows toolchain compatibility*).

## Why a separate account

An AppContainer is denied metadata on `C:\`, so Node, Git, MSYS tools and
virtualenv interpreters fail before doing any work. A dedicated, unprivileged
local account is an ordinary principal: it can traverse the drive and run
system-installed toolchains, while the owner's profile and data stay out of
reach because Windows does not grant one standard user another's files.

## Components

| Piece | What it is | Created by |
| --- | --- | --- |
| `RaikerSandbox` local user | Standard user, no group memberships beyond the sandbox group, random 64-character password, "deny interactive and remote logon" rights | One-time elevated setup |
| `RaikerSandboxUsers` local group | The only principal granted the task copies | One-time elevated setup |
| `C:\RaikerSandbox` base | Task copies live here (not under the owner's profile, which the account cannot traverse). DACL: SYSTEM, Administrators, owner, `RaikerSandboxUsers` | One-time elevated setup |
| Outbound firewall rule | Blocks all outbound traffic for the account's SID, loopback included | One-time elevated setup |
| Credential | Password sealed with DPAPI for the owner's user, stored in Raiker's data directory | Setup |

## Launch path (no elevation at run time)

1. `CreateProcessWithLogonW` as `RaikerSandbox`, `CREATE_SUSPENDED`, with the
   command's argv, the task copy as working directory and a constructed
   environment (no owner variables, `TEMP`/`TMP` inside the copy).
2. Assign the suspended process to a Job Object (kill-on-close, active-process,
   memory and CPU limits, UI restrictions), then resume. Failure terminates it.
3. Per-run ACL: the copy grants `RaikerSandboxUsers` modify; nothing else does.
4. Stdio over pipes created by the runner; no inherited owner handles.

`CreateProcessWithTokenW`/`CreateProcessAsUserW` need privileges a standard
user does not hold, so a custom restricted token is not available without a
privileged helper service; that is a possible later hardening step.

## What it protects, and what it does not

* **Owner profile and other users' files:** denied by default ACLs.
* **Writable data outside profiles** (for example a second drive whose root
  grants `Authenticated Users` modify): *readable and writable* by any standard
  user. Setup must add an inheritable deny for `RaikerSandboxUsers` on each
  such root the owner names; the probe measures it. Until then this is an open
  data-protection gap and the probe reports it.
* **Network:** blocked by the firewall rule; the probe measures it with a
  control arm, and the firewall service being off makes it unenforced.
* **Process tree:** Job Object, as today.

## Approvals the owner must give

All are one-time, require administrator rights (UAC), and are reversible by
an uninstall/reset step that removes them:

1. Create the `RaikerSandbox` account and `RaikerSandboxUsers` group.
2. Create `C:\RaikerSandbox` with its ACL.
3. Add the outbound firewall block for the account.
4. Add deny entries on any data roots readable by all users that the owner
   wants protected (for example `F:\`).

## Verification plan

Probe with control arms, as on other platforms: workspace write, escape write
to the owner's profile and to a world-writable root, masked read, egress,
descendant reaping. Toolchain runs: Node, Git, Python, MSYS tools in a task
copy. CI: hosted `windows-2025` runners allow elevated setup in the job.

## Implementation (2026-10-31)

`native/raiker-command-runner/src/account_windows.rs`:
`--setup-account` / `--reset-account` (elevated, idempotent) and
`--account-status`. Launches use `CreateProcessWithLogonW` with the account's
own profile environment (no owner variables), a per-run Modify grant on that
run's copy only (the base grants the account nothing but read-attributes;
revoked when the run ends), a Job Object with UI
restrictions (handles, clipboard, desktop, system parameters, exit Windows)
and pipes for stdio. A policy whose workspace is under `C:\RaikerSandbox` runs
as the account; any other workspace keeps the AppContainer boundary.
`--probe` measures the account boundary when it is configured;
`--probe --boundary appcontainer` still measures the AppContainer.

Python: `task_workspace_registry()` places copies under the account base when
configured and keeps registry records in Raiker's own state
(`.raiker/task-workspaces`), because the account can write the whole base and
must not be able to rewrite a record's `source` (where promotion writes).
Copies are created with normal ACL inheritance: Python 3.13's
`tempfile.mkdtemp` sets an owner-only ACL on Windows, which made copies
unreadable to the account (measured).

## Evidence on the owner's PC (Windows 11, after setup)

Probe, each observation against an owner control arm: relay, workspace write,
escape write (owner profile and D:, E:, F:, H: roots), masked read of an
owner-only file, egress (firewall rule), descendant reaping — **all enforced**.
Toolchains as the account inside a copy: Node script, `git init` / `status`,
Git-for-Windows MSYS `echo`, system Python 3.13 — all ran. Writes to the owner
profile and F:, reads of the owner's `.gitconfig` and the repository on F:, and
an outbound TCP connection were refused. A full run through `CommandService`
used a copy under `C:\RaikerSandbox`, recorded the change in the diff, and left
the project unchanged. `tests/windows_account.rs` covers the probe, toolchains
and the profile-escape refusal; CI's Windows job now runs setup and requires it.

## Known gaps (tracked in TO_BE_FIXED.md)

* **Loopback:** Windows Firewall does not filter loopback; local services are
  reachable from the sandbox until a WFP filter is added.
* **Explicit grants under denied drives:** an explicit allow on a folder below a
  denied root outranks the inherited deny; such folders stay reachable.
* **Persistent account profile:** `C:\Users\RaikerSandbox` persists between
  tasks (caches, user environment), so one task can leave state for the next.
  It stays inside the boundary; resetting it per task is open.
* **Logon rights:** the account is not yet denied network or remote-desktop
  logon by policy; its random password is known only to Raiker.

